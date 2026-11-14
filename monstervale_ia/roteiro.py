"""Roteiros de teste: sequências fixas de ações, quadro a quadro, para comparar
a simulação em Python com a do Godot (ferramentas/executar_roteiro.gd).

Um roteiro é uma lista de ``[quadro, ação, argumentos...]``. Em cada quadro, as
ações daquele quadro são aplicadas e depois a simulação avança 1/60 s. Ações
que falham (sem ouro, célula ocupada) falham igual nos dois lados, e isso
também é testado.

Ações:
  ["place", tipo, x, y]       posicionar
  ["upgrade", x, y]           melhorar o humano da célula
  ["dismiss", x, y]           dispensar o humano da célula
  ["priority", x, y]          trocar a prioridade de alvo (cycle_priority)
  ["call"]                    chamar a próxima onda
  ["gold", quantia]           só para teste: soma ouro (como o "ouro infinito" do modo dev)
"""

from __future__ import annotations

import hashlib
import struct

from monstervale_ia.mapa import Mapa
from monstervale_ia.simulacao import Simulacao

PASSO = 1.0 / 60.0
QUADROS_ENTRE_IMPRESSOES = 30
_ESTADOS = {"playing": 0, "won": 1, "lost": 2}


def gerar_roteiro(
    id_fase: str,
    classes: list[str],
    quadros: int = 54_000,
    intervalo_onda: int = 240,
    max_humanos: int = 22,
    ouro_extra: int = 0,
) -> list[list]:
    """Roteiro determinístico que usa todas as classes da fase.

    Escolhe as células construíveis mais perto da estrada, alterna as classes,
    tenta melhorar em rodízio, troca algumas prioridades e chama uma onda a
    cada `intervalo_onda` quadros (240 = 4 s, agressivo; 1500 = 25 s, calmo).
    """
    mapa = Mapa.carregar(id_fase)
    celulas = mapa.celulas_junto_a_estrada()
    acoes: list[list] = [[5, "gold", ouro_extra]] if ouro_extra else []
    proxima_celula = 0
    usadas: list[tuple[int, int]] = []
    for quadro in range(0, quadros):
        if quadro % 150 == 10 and proxima_celula < min(max_humanos, len(celulas)):
            tipo = classes[proxima_celula % len(classes)]
            x, y = celulas[proxima_celula]
            acoes.append([quadro, "place", tipo, x, y])
            usadas.append((x, y))
            proxima_celula += 1
        if quadro % 100 == 50 and usadas:
            x, y = usadas[(quadro // 100) % len(usadas)]
            acoes.append([quadro, "upgrade", x, y])
        if quadro % 900 == 400 and usadas:
            x, y = usadas[(quadro // 900) % len(usadas)]
            acoes.append([quadro, "priority", x, y])
        if quadro % 3000 == 2999 and len(usadas) > 4:
            x, y = usadas[(quadro // 3000) % len(usadas)]
            acoes.append([quadro, "dismiss", x, y])
        if quadro % intervalo_onda == intervalo_onda // 2:
            acoes.append([quadro, "call"])
    return acoes


def aplicar(sim: Simulacao, acao: list) -> bool:
    nome = acao[1]
    if nome == "place":
        return sim.posicionar(acao[2], (acao[3], acao[4])) is not None
    if nome == "call":
        return sim.chamar_onda()
    if nome == "gold":
        sim.ouro += acao[2]
        return True
    humano = sim.humano_em((acao[2], acao[3]))
    if humano is None:
        return False
    if nome == "upgrade":
        return sim.melhorar(humano)
    if nome == "dismiss":
        sim.dispensar(humano)
        return True
    if nome == "priority":
        humano.trocar_prioridade()
        return True
    raise ValueError(f"ação desconhecida: {nome}")


def impressao_digital(sim: Simulacao, tipos_monstro: list[str]) -> str:
    """SHA-1 do estado completo, em bytes exatos (mesmo formato do executar_roteiro.gd)."""
    b = bytearray()
    i32 = lambda v: b.extend(struct.pack("<i", int(v)))  # noqa: E731
    f64 = lambda v: b.extend(struct.pack("<d", float(v)))  # noqa: E731
    f64(sim.tempo)
    i32(sim.ouro)
    i32(sim.vidas)
    i32(_ESTADOS[sim.estado])
    i32(sim.ondas_iniciadas())
    f64(sim.contagem_proxima_onda)
    i32(len(sim.monstros))
    for m in sim.monstros:
        i32(tipos_monstro.index(m.tipo))
        f64(m.distancia)
        i32(m.vida)
        f64(m.recarga)
        f64(m.tempo_lentidao)
        f64(m.fator_lentidao)
        f64(m.tempo_raiz)
        f64(m.tempo_atordoado)
        i32(sim.humanos.index(m.bloqueador) if m.bloqueador is not None else -1)
    i32(len(sim.humanos))
    for h in sim.humanos:
        i32(h.nivel)
        i32(h.vida)
        f64(h.recarga)
        f64(h.tempo_caido)
        i32(h.ataques_feitos)
        i32(len(h.bloqueados))
    i32(len(sim.fogos))
    for f in sim.fogos:
        f64(f["remaining"])
        f64(f["timer"])
    return hashlib.sha1(bytes(b)).hexdigest()


def executar(
    sim: Simulacao, acoes: list[list], tipos_monstro: list[str], quadros: int, invencivel: bool = False
) -> dict:
    """Executa o roteiro e devolve o resultado das ações e as impressões digitais."""
    sim.invencivel = invencivel
    por_quadro: dict[int, list[list]] = {}
    for acao in acoes:
        por_quadro.setdefault(acao[0], []).append(acao)
    resultados: list[bool] = []
    impressoes: list[list] = []
    for quadro in range(quadros):
        for acao in por_quadro.get(quadro, []):
            resultados.append(aplicar(sim, acao))
        sim.passo(PASSO)
        if quadro % QUADROS_ENTRE_IMPRESSOES == 0 or sim.estado != "playing":
            impressoes.append([quadro, sim.ouro, sim.vidas, len(sim.monstros), impressao_digital(sim, tipos_monstro)])
        if sim.estado != "playing":
            break
    return {"results": resultados, "prints": impressoes, "state": sim.estado}
