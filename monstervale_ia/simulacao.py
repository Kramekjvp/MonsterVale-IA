"""Regras do jogo, sem tela. Port de ``jogo/src/core/simulation.gd``.

A cada ``passo(delta)`` (o ``tick`` do jogo, sempre 1/60 s) a simulação:
conta o tempo da próxima onda → faz surgir monstros → move monstros (andar,
bloquear, bater) → humanos atacam → fogo queima → ondas limpas dão bônus →
confere vitória/derrota.

A ordem das etapas e a ordem dos laços são as mesmas do GDScript: num jogo
determinístico, quem age primeiro muda o resultado.

Os textos de estado ("playing", "won", "lost") e os tipos de evento
("unit_placed", "monster_killed"...) ficam iguais aos do jogo, para comparar
com os relatórios de partida do Godot.
"""

from __future__ import annotations

import math
from typing import Any

from monstervale_ia.godot import maxf, maxi, ordenar_como_godot, roundi
from monstervale_ia.humano import Humano
from monstervale_ia.mapa import Celula
from monstervale_ia.monstro import Monstro
from monstervale_ia.rota import Rota
from monstervale_ia.vetor import (
    Vetor,
    MARGEM_PREFILTRO,
    dentro_do_raio,
    direcao_para,
    distancia,
    distancia_aprox,
    escalar,
    ponto_mais_proximo_do_segmento,
    somar,
    vetor,
)

LIMIARES_ESTRELAS_PADRAO = [0.5, 0.9]
ESPALHAMENTO_DIVISAO = 8.0  # pixels entre os filhotes de um slime que se divide
# Tipo sem resistência em nenhum monstro: o crítico acha o ponto fraco de qualquer armadura.
DANO_CRITICO = "critical"


class Simulacao:
    def __init__(self, catalogo: dict[str, Any], fase: dict[str, Any]) -> None:
        self._catalogo = catalogo
        self._fase = fase
        self.ouro: int = int(fase["start_gold"])
        self.vidas: int = int(fase["lives"])
        self._vidas_iniciais: int = int(fase["lives"])
        self.invencivel = False
        self.estado: str = "playing"
        self.humanos: list[Humano] = []
        self.monstros: list[Monstro] = []
        self.fogos: list[dict] = []
        self.rotas = [Rota(pontos) for pontos in fase.get("routes", [fase["route"]])]
        self.rota = self.rotas[0]
        self.contagem_proxima_onda: float = float(fase["wave_interval"])
        self.tempo: float = 0.0
        self._proxima_onda: int = 0
        self._ondas_ativas: list[dict] = []
        self._eventos: list[dict] = []
        # Os eventos servem à interface e aos relatórios; no treino podem ser desligados.
        self.registrar_eventos = True

    # --- Consultas --------------------------------------------------------------

    def vidas_iniciais(self) -> int:
        return self._vidas_iniciais

    def classes_disponiveis(self) -> list[str]:
        return self._fase["classes"]

    def custo_humano(self, tipo: str) -> int:
        return int(self._catalogo["units"][tipo]["levels"][0]["cost"])

    def tipo_dano_humano(self, tipo: str) -> str:
        return self._catalogo["units"][tipo]["damage_type"]

    def pode_posicionar(self, tipo: str, celula: Celula) -> bool:
        return (
            tipo in self._fase["classes"]
            and celula in self._fase["buildable"]
            and self.humano_em(celula) is None
            and self.ouro >= self.custo_humano(tipo)
        )

    def humano_em(self, celula: Celula) -> Humano | None:
        for humano in self.humanos:
            if humano.celula == celula:
                return humano
        return None

    def centro_da_celula(self, celula: Celula) -> Vetor:
        tamanho = int(self._fase["cell_size"])
        return vetor((celula[0] + 0.5) * tamanho, (celula[1] + 0.5) * tamanho)

    def chefe(self) -> Monstro | None:
        for monstro in self.monstros:
            if monstro.chefe:
                return monstro
        return None

    def ondas_iniciadas(self) -> int:
        return self._proxima_onda

    def total_ondas(self) -> int:
        return len(self._fase["waves"])

    def pode_chamar_onda(self) -> bool:
        return self.estado == "playing" and self._proxima_onda < self.total_ondas() and not self._surgindo()

    def bonus_chamada_antecipada(self) -> int:
        return roundi(self.contagem_proxima_onda * float(self._fase["early_call_gold_per_second"]))

    def previa_proxima_onda(self) -> dict[str, int]:
        previa: dict[str, int] = {}
        if self._proxima_onda >= self.total_ondas():
            return previa
        for grupo in self._fase["waves"][self._proxima_onda]["groups"]:
            previa[grupo["monster"]] = previa.get(grupo["monster"], 0) + int(grupo["count"])
        return previa

    def rotas_proxima_onda(self) -> list[int]:
        """Entradas usadas pela próxima onda, para o jogador saber de onde ela vem."""
        usadas: list[int] = []
        if self._proxima_onda >= self.total_ondas():
            return usadas
        for grupo in self._fase["waves"][self._proxima_onda]["groups"]:
            indice = int(grupo.get("route", 0))
            if indice not in usadas:
                usadas.append(indice)
        return sorted(usadas)

    def fraquezas_proxima_onda(self) -> list[str]:
        fracos: list[str] = []
        if self._proxima_onda >= self.total_ondas():
            return fracos
        for grupo in self._fase["waves"][self._proxima_onda]["groups"]:
            resistencia = self._catalogo["monsters"][grupo["monster"]]["resist"]
            for tipo_dano, fator in resistencia.items():
                if float(fator) > 1.0 and tipo_dano not in fracos:
                    fracos.append(tipo_dano)
        return sorted(fracos)

    def estrelas(self) -> int:
        limiares = self._fase.get("stars", LIMIARES_ESTRELAS_PADRAO)
        razao = float(self.vidas) / self._vidas_iniciais
        if razao >= limiares[1]:
            return 3
        if razao >= limiares[0]:
            return 2
        return 1

    def campo_limpo(self) -> bool:
        """Nenhuma onda em andamento e nenhum monstro em campo (não existe no jogo; usado pelo ambiente)."""
        return not self._ondas_ativas and not self.monstros

    def esvaziar_eventos(self) -> list[dict]:
        eventos, self._eventos = self._eventos, []
        return eventos

    # --- Ações do jogador -------------------------------------------------------

    def posicionar(self, tipo: str, celula: Celula) -> Humano | None:
        if not self.pode_posicionar(tipo, celula):
            return None
        humano = Humano(tipo, self._catalogo["units"][tipo], celula, self.centro_da_celula(celula))
        self.ouro -= humano.gasto
        self.humanos.append(humano)
        self._emitir({"type": "unit_placed", "unit": humano})
        return humano

    def melhorar(self, humano: Humano) -> bool:
        if not humano.pode_melhorar() or self.ouro < humano.custo_melhoria():
            return False
        self.ouro -= humano.custo_melhoria()
        humano.subir_nivel()
        self._emitir({"type": "unit_upgraded", "unit": humano})
        return True

    def dispensar(self, humano: Humano) -> None:
        self._soltar_bloqueados(humano)
        self.ouro += humano.reembolso()
        self.humanos.remove(humano)
        self._emitir({"type": "unit_dismissed", "unit": humano})

    def chamar_onda(self) -> bool:
        if not self.pode_chamar_onda():
            return False
        bonus = self.bonus_chamada_antecipada()
        self.ouro += bonus
        self._iniciar_proxima_onda(bonus, True)
        return True

    def surgir_monstro(self, tipo: str, indice_rota: int = 0) -> Monstro:
        monstro = Monstro(tipo, self._catalogo["monsters"][tipo], self.rotas[indice_rota], indice_rota)
        self.monstros.append(monstro)
        self._emitir({"type": "monster_spawned", "monster": monstro})
        return monstro

    # --- O passo da simulação ---------------------------------------------------

    def passo(self, delta: float) -> None:
        if self.estado != "playing":
            return
        self.tempo += delta
        self._atualizar_contagem(delta)
        self._atualizar_surgimento(delta)
        self._atualizar_monstros(delta)
        self._atualizar_humanos(delta)
        self._atualizar_fogos(delta)
        self._atualizar_ondas_limpas()
        self._atualizar_fim()

    def _emitir(self, evento: dict) -> None:
        if not self.registrar_eventos:
            return
        evento["time"] = self.tempo
        evento["gold"] = self.ouro
        evento["lives"] = self.vidas
        evento["waves_started"] = self._proxima_onda
        self._eventos.append(evento)

    # --- Ondas ------------------------------------------------------------------

    def _surgindo(self) -> bool:
        return any(onda["spawners"] for onda in self._ondas_ativas)

    def _iniciar_proxima_onda(self, bonus_antecipado: int = 0, chamada_cedo: bool = False) -> None:
        definicao = self._fase["waves"][self._proxima_onda]
        geradores = [
            {
                "monster": grupo["monster"],
                "remaining": int(grupo["count"]),
                "interval": float(grupo["interval"]),
                "timer": float(grupo["delay"]),
                "route": int(grupo.get("route", 0)),
            }
            for grupo in definicao["groups"]
        ]
        self._proxima_onda += 1
        self._ondas_ativas.append(
            {"number": self._proxima_onda, "spawners": geradores, "alive": 0, "bonus": int(definicao["bonus"])}
        )
        self.contagem_proxima_onda = float(self._fase["wave_interval"])
        self._emitir({
            "type": "wave_started", "number": self._proxima_onda,
            "early_bonus": bonus_antecipado, "called_early": chamada_cedo,
        })

    def _atualizar_contagem(self, delta: float) -> None:
        """As ondas só começam quando o jogador chama; a contagem só mede o bônus."""
        if self._proxima_onda >= self.total_ondas() or self._surgindo():
            return
        self.contagem_proxima_onda = maxf(self.contagem_proxima_onda - delta, 0.0)

    def _atualizar_surgimento(self, delta: float) -> None:
        for onda in self._ondas_ativas:
            for gerador in onda["spawners"]:
                gerador["timer"] -= delta
                while gerador["timer"] <= 0.0 and gerador["remaining"] > 0:
                    monstro = self.surgir_monstro(gerador["monster"], gerador["route"])
                    monstro.onda = onda
                    onda["alive"] += 1
                    gerador["remaining"] -= 1
                    gerador["timer"] += gerador["interval"]
            onda["spawners"] = [g for g in onda["spawners"] if g["remaining"] > 0]

    def _atualizar_ondas_limpas(self) -> None:
        for onda in list(self._ondas_ativas):
            if not onda["spawners"] and onda["alive"] <= 0:
                self.ouro += onda["bonus"]
                self._ondas_ativas.remove(onda)
                self._emitir({"type": "wave_cleared", "number": onda["number"], "bonus": onda["bonus"]})

    def _atualizar_fim(self) -> None:
        if self.vidas <= 0:
            self.estado = "lost"
            self._emitir({"type": "level_lost"})
        elif (
            self._proxima_onda >= self.total_ondas()
            and not self._ondas_ativas
            and not self.monstros
            and self.total_ondas() > 0
        ):
            self.estado = "won"
            self._emitir({"type": "level_won", "stars": self.estrelas()})

    # --- Monstros ---------------------------------------------------------------

    def _atualizar_monstros(self, delta: float) -> None:
        for monstro in list(self.monstros):  # monsters.duplicate()
            monstro.atualizar_efeitos(delta)
            if monstro.esta_atordoado():
                continue
            if monstro.bloqueador is None and monstro.pode_ser_bloqueado():
                self._tentar_bloquear(monstro)
            if monstro.bloqueador is not None:
                self._atacar_bloqueador(monstro, delta)
            else:
                self._andar(monstro, delta)
                if monstro in self.monstros:
                    self._atacar_de_passagem(monstro, delta)

    def _tentar_bloquear(self, monstro: Monstro) -> None:
        mx, my = monstro.posicao_f()
        for humano in self.humanos:
            if not humano.tem_espaco_para_bloquear():
                continue
            hx, hy = humano.posicao_f
            if self._no_raio((hx - mx) ** 2 + (hy - my) ** 2, humano.alcance_bloqueio, humano, monstro):
                monstro.bloqueador = humano
                humano.bloqueados.append(monstro)
                monstro.recarga = 0.0
                return

    def _atacar_bloqueador(self, monstro: Monstro, delta: float) -> None:
        monstro.recarga -= delta
        if monstro.recarga <= 0.0:
            self._golpear(monstro, monstro.bloqueador)

    def _atacar_de_passagem(self, monstro: Monstro, delta: float) -> None:
        """Quem não está bloqueado segue andando e bate no humano mais próximo ao alcance."""
        monstro.recarga -= delta
        if monstro.recarga > 0.0:
            return
        mais_proximo = None
        menor_distancia = monstro.alcance
        mx, my = monstro.posicao_f()
        limite2 = (menor_distancia + MARGEM_PREFILTRO) ** 2
        for humano in self.humanos:
            if humano.tempo_caido > 0.0:
                continue
            # Pré-filtro (conta inline, sem chamar função): longe demais com certeza.
            hx, hy = humano.posicao_f
            if (hx - mx) ** 2 + (hy - my) ** 2 > limite2:
                continue
            d = float(distancia(humano.posicao, monstro.posicao()))
            if d <= menor_distancia:  # <=: no empate, o último da lista vence
                menor_distancia = d
                mais_proximo = humano
        if mais_proximo is not None:
            self._golpear(monstro, mais_proximo)

    def _golpear(self, monstro: Monstro, humano: Humano) -> None:
        monstro.recarga = monstro.intervalo_ataque
        sofrido = maxi(1, roundi(monstro.dano * float(humano.atributos().get("damage_taken", 1.0))))
        humano.vida -= sofrido
        humano.tempo_sem_dano = 0.0
        self._emitir({"type": "unit_hit", "unit": humano, "monster": monstro, "damage": sofrido})
        if humano.vida <= 0:
            self._cair(humano)

    def _cair(self, humano: Humano) -> None:
        humano.vida = 0
        humano.tempo_caido = float(humano.atributos()["respawn"])
        self._soltar_bloqueados(humano)
        self._emitir({"type": "unit_down", "unit": humano})

    def _soltar_bloqueados(self, humano: Humano) -> None:
        for monstro in humano.bloqueados:
            monstro.bloqueador = None
        humano.bloqueados.clear()

    def _andar(self, monstro: Monstro, delta: float) -> None:
        # velocidade_atual(), inline (otimização): parado se preso ou atordoado.
        if monstro.tempo_raiz > 0.0 or monstro.tempo_atordoado > 0.0:
            velocidade = 0.0
        else:
            velocidade = monstro.velocidade * (monstro.fator_lentidao if monstro.tempo_lentidao > 0.0 else 1.0)
        monstro.distancia += velocidade * delta
        direcao = monstro.direcao_horizontal()
        if direcao != 0:
            monstro.olhando = direcao
        if monstro.distancia >= monstro.comprimento_rota():
            self._escapar(monstro)

    def _escapar(self, monstro: Monstro) -> None:
        if not self.invencivel:
            self.vidas = maxi(0, self.vidas - monstro.vidas)
        self._remover(monstro)
        self._emitir({"type": "monster_escaped", "monster": monstro})

    def _remover(self, monstro: Monstro) -> None:
        self.monstros.remove(monstro)
        if monstro.bloqueador is not None:
            monstro.bloqueador.bloqueados.remove(monstro)
            monstro.bloqueador = None
        if monstro.onda is not None:
            monstro.onda["alive"] -= 1

    # --- Humanos ----------------------------------------------------------------

    def _atualizar_humanos(self, delta: float) -> None:
        for humano in self.humanos:
            if humano.esta_caido():
                humano.tempo_caido -= delta
                if not humano.esta_caido():
                    humano.vida = int(humano.atributos()["hp"])
                    self._emitir({"type": "unit_up", "unit": humano})
                continue
            humano.recuperar(delta)
            humano.recarga -= delta
            if humano.recarga > 0.0:
                continue
            alvo = self._escolher_alvo(humano)
            if alvo is not None:
                humano.recarga = humano.intervalo
                self._atacar(humano, alvo)

    def _escolher_alvo(self, humano: Humano) -> Monstro | None:
        if humano.bloqueados:
            return humano.bloqueados[0]
        melhor = None
        melhor_nota = -math.inf
        alcance = humano.alcance
        prioridade = humano.prioridade
        hx, hy = humano.posicao_f
        for monstro in self.monstros:
            mx, my = monstro.posicao_f()
            if not self._no_raio((hx - mx) ** 2 + (hy - my) ** 2, alcance, humano, monstro):
                continue
            # A distância exata só entra na nota da prioridade "closest".
            d = float(distancia(humano.posicao, monstro.posicao())) if prioridade == "closest" else 0.0
            nota = self._nota_alvo(prioridade, monstro, d)
            if nota > melhor_nota:  # >: no empate, o primeiro da lista vence
                melhor_nota = nota
                melhor = monstro
        return melhor

    @staticmethod
    def _no_raio(d2: float, raio: float, humano: Humano, monstro: Monstro) -> bool:
        """distancia(humano, monstro) <= raio, igual ao Godot, a partir da distância² em float64.

        Mesmo pré-filtro de vetor.dentro_do_raio, com a conta feita no laço de quem chama.
        """
        if d2 < (raio - MARGEM_PREFILTRO) ** 2:
            return True
        if d2 > (raio + MARGEM_PREFILTRO) ** 2:
            return False
        return float(distancia(humano.posicao, monstro.posicao())) <= raio

    @staticmethod
    def _nota_alvo(prioridade: str, monstro: Monstro, d: float) -> float:
        if prioridade == "last":
            return -monstro.distancia
        if prioridade == "strongest":
            return float(monstro.vida)
        if prioridade == "closest":
            return -d
        return monstro.distancia  # "first": o mais adiantado na rota

    def _atacar(self, humano: Humano, alvo: Monstro) -> None:
        atingidos = [alvo]
        atributos = humano.atributos()
        if "pierce_extra" in atributos:  # flecha do arqueiro nível 3
            atingidos += self._proximos(alvo, float(atributos["pierce_radius"]), int(atributos["pierce_extra"]))
        if "splash_radius" in atributos:  # explosão do mago
            atingidos += self._proximos(alvo, float(atributos["splash_radius"]), int(atributos["splash_targets"]) - 1)
        if "line_width" in atributos:  # lanceiro nível 3
            atingidos += self._em_linha(humano, alvo, float(atributos["line_width"]))
        posicao_alvo = alvo.posicao()
        if posicao_alvo[0] != humano.posicao[0]:
            humano.olhando = 1 if posicao_alvo[0] > humano.posicao[0] else -1
        critico = "crit" in atributos and (humano.ataques_feitos + 1) % int(atributos["crit"]["every"]) == 0
        if critico:
            quantidade = roundi(float(atributos["damage"]) * float(atributos["crit"]["multiplier"]))
        else:
            quantidade = int(atributos["damage"])
        tipo_dano = DANO_CRITICO if critico else humano.tipo_dano()
        self._emitir({"type": "attack", "unit": humano, "target": alvo, "position": posicao_alvo, "crit": critico})
        for monstro in atingidos:
            self._ferir(monstro, quantidade, tipo_dano, humano.tipo, int(atributos.get("kill_gold", 0)))
        if "fire" in atributos:
            self._iniciar_fogo(humano, posicao_alvo, atributos["fire"])
        self._aplicar_controle(humano, alvo, atributos)

    def _em_linha(self, humano: Humano, alvo: Monstro, largura: float) -> list[Monstro]:
        """Quem está no segmento que sai do humano, passa pelo alvo e vai até o alcance."""
        direcao = direcao_para(humano.posicao, alvo.posicao())
        fim = somar(humano.posicao, escalar(direcao, float(humano.atributos()["range"])))
        resultado = []
        for monstro in self.monstros:
            if monstro is alvo:
                continue
            posicao = monstro.posicao()
            mais_proximo = ponto_mais_proximo_do_segmento(posicao, humano.posicao, fim)
            if float(distancia(mais_proximo, posicao)) <= largura:
                resultado.append(monstro)
        return resultado

    def _aplicar_controle(self, humano: Humano, alvo: Monstro, atributos: dict) -> None:
        humano.ataques_feitos += 1
        if "slow" in atributos:
            lentos = [alvo] + self._proximos(alvo, float(atributos["slow"].get("radius", 0.0)), len(self.monstros))
            for monstro in lentos:
                monstro.aplicar_lentidao(float(atributos["slow"]["factor"]), float(atributos["slow"]["seconds"]))
        if "root" in atributos and humano.ataques_feitos % int(atributos["root"]["every"]) == 0:
            alvo.aplicar_raiz(float(atributos["root"]["seconds"]))
        if "stun" in atributos and humano.ataques_feitos % int(atributos["stun"]["every"]) == 0:
            alvo.aplicar_atordoamento(float(atributos["stun"]["seconds"]))

    def _proximos(self, alvo: Monstro, raio: float, quantidade: int) -> list[Monstro]:
        """Até `quantidade` monstros a até `raio` do alvo, do mais perto ao mais longe."""
        centro, centro_f = alvo.posicao(), alvo.posicao_f()
        perto = [
            m for m in self.monstros
            if m is not alvo and dentro_do_raio(m.posicao(), m.posicao_f(), centro, centro_f, raio)
        ]
        # As distâncias exatas não mudam durante a ordenação: calcula uma vez por monstro.
        d = {id(m): distancia(m.posicao(), centro) for m in perto}
        ordenar_como_godot(perto, lambda a, b: d[id(a)] < d[id(b)])
        return perto[:max(quantidade, 0)]

    def _ferir(self, monstro: Monstro, base: int, tipo_dano: str, origem: str, ouro_abate: int = 0) -> None:
        quantidade = monstro.dano_recebido(base, tipo_dano)
        monstro.vida -= quantidade
        self._emitir({
            "type": "monster_hit", "monster": monstro, "damage": quantidade,
            "source": origem, "effect": self._efeito_golpe(monstro, tipo_dano),
        })
        if monstro.vida <= 0:
            self.ouro += monstro.ouro + ouro_abate
            self._remover(monstro)
            self._emitir({"type": "monster_killed", "monster": monstro, "position": monstro.posicao(), "bonus_gold": ouro_abate})
            self._dividir(monstro)
        else:
            self._soltar_filhotes(monstro)

    @staticmethod
    def _efeito_golpe(monstro: Monstro, tipo_dano: str) -> str:
        fator = float(monstro.resistencia.get(tipo_dano, 1.0))
        if fator > 1.0:
            return "weak"
        return "resisted" if fator < 1.0 else "normal"

    def _dividir(self, monstro: Monstro) -> None:
        divisao = self._catalogo["monsters"][monstro.tipo].get("split")
        if divisao is None:
            return
        self._gerar_filhotes(monstro, divisao["into"], int(divisao["count"]))

    def _soltar_filhotes(self, monstro: Monstro) -> None:
        """O chefe solta monstros cada vez que perde mais uma fração da vida."""
        soltar = self._catalogo["monsters"][monstro.tipo].get("shed")
        if soltar is None:
            return
        devidos = math.floor((monstro.vida_maxima - monstro.vida) / (monstro.vida_maxima * float(soltar["every_fraction"])))
        if devidos <= monstro.soltos:
            return
        for _ in range(devidos - monstro.soltos):
            self._gerar_filhotes(monstro, soltar["into"], int(soltar["count"]))
        monstro.soltos = devidos
        self._emitir({"type": "monster_split", "monster": monstro})

    def _gerar_filhotes(self, monstro: Monstro, tipo: str, quantidade: int) -> None:
        for i in range(quantidade):
            filhote = self.surgir_monstro(tipo, monstro.indice_rota)
            filhote.distancia = maxf(0.0, monstro.distancia + ESPALHAMENTO_DIVISAO * (i - (quantidade - 1) / 2.0))
            filhote.olhando = monstro.olhando
            filhote.onda = monstro.onda
            if monstro.onda is not None:
                monstro.onda["alive"] += 1

    # --- Fogo do mago nível 3 ---------------------------------------------------

    def _iniciar_fogo(self, humano: Humano, em: Vetor, dados: dict) -> None:
        self.fogos.append({
            "position": em,
            "radius": float(dados["radius"]),
            "damage": int(dados["damage"]),
            "damage_type": humano.tipo_dano(),
            "source": humano.tipo,
            "interval": float(dados["interval"]),
            "timer": float(dados["interval"]),
            "remaining": float(dados["seconds"]),
        })

    def _atualizar_fogos(self, delta: float) -> None:
        for fogo in self.fogos:
            fogo["remaining"] -= delta
            fogo["timer"] -= delta
            while fogo["timer"] <= 0.0:
                fogo["timer"] += fogo["interval"]
                self._queimar(fogo)
        self.fogos = [f for f in self.fogos if f["remaining"] > 0.0]

    def _queimar(self, fogo: dict) -> None:
        centro = fogo["position"]
        centro_f = (float(centro[0]), float(centro[1]))
        for monstro in list(self.monstros):
            if dentro_do_raio(monstro.posicao(), monstro.posicao_f(), centro, centro_f, fogo["radius"]):
                self._ferir(monstro, fogo["damage"], fogo["damage_type"], fogo["source"])
