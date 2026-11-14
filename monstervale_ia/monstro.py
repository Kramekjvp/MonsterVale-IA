"""Estado de um monstro em campo. Port de ``jogo/src/core/monster.gd``."""

from __future__ import annotations

from typing import Any

from monstervale_ia.godot import maxf, maxi, roundi
from monstervale_ia.rota import Rota
from monstervale_ia.vetor import Vetor


class Monstro:
    def __init__(self, tipo: str, dados: dict[str, Any], rota: Rota, indice_rota: int = 0) -> None:
        self.tipo = tipo
        # O Godot lê números do JSON como float; `var hp: int` converte para int.
        self.vida: int = int(dados["hp"])
        self.vida_maxima: int = int(dados["hp"])
        self.velocidade: float = float(dados["speed"])
        self.ouro: int = int(dados["gold"])
        self.dano: int = int(dados["damage"])
        self.intervalo_ataque: float = float(dados["attack_cooldown"])
        self.alcance: float = float(dados["reach"])
        self.vidas: int = int(dados["lives"])  # vidas da vila que ele tira ao passar
        self.resistencia: dict[str, float] = dados["resist"]
        self.chefe: bool = bool(dados.get("boss", False))
        self.imune: list[str] = list(dados.get("immune", []))

        self.distancia: float = 0.0  # pixels já andados na rota (float64)
        self.olhando: int = 1
        self.recarga: float = 0.0
        self.bloqueador = None  # Humano que o segura, ou None
        self.onda = None
        self.indice_rota = indice_rota
        self.fator_lentidao: float = 1.0
        self.tempo_lentidao: float = 0.0
        self.tempo_raiz: float = 0.0
        self.tempo_atordoado: float = 0.0
        self.soltos: int = 0  # quantas vezes já soltou filhotes (Rei Slime)

        self._rota = rota

    def posicao(self) -> Vetor:
        return self._rota.posicao_em(self.distancia)

    def dano_recebido(self, quantidade: int, tipo_dano: str) -> int:
        """Dano depois da resistência; nunca menos que 1."""
        return maxi(1, roundi(quantidade * float(self.resistencia.get(tipo_dano, 1.0))))

    def comprimento_rota(self) -> float:
        return self._rota.comprimento

    def direcao_horizontal(self) -> int:
        return self._rota.direcao_horizontal_em(self.distancia)

    def velocidade_atual(self) -> float:
        if self.esta_preso() or self.esta_atordoado():
            return 0.0
        return self.velocidade * (self.fator_lentidao if self.esta_lento() else 1.0)

    def esta_lento(self) -> bool:
        return self.tempo_lentidao > 0.0

    def esta_preso(self) -> bool:
        return self.tempo_raiz > 0.0

    def esta_atordoado(self) -> bool:
        return self.tempo_atordoado > 0.0

    def aplicar_lentidao(self, fator: float, segundos: float) -> None:
        """Um efeito mais fraco não substitui um mais forte que ainda está valendo."""
        if self.esta_lento() and fator > self.fator_lentidao:
            return
        self.fator_lentidao = fator
        self.tempo_lentidao = segundos

    def pode_ser_bloqueado(self) -> bool:
        return "block" not in self.imune

    def aplicar_raiz(self, segundos: float) -> None:
        if "root" in self.imune:
            return
        self.tempo_raiz = maxf(self.tempo_raiz, segundos)

    def aplicar_atordoamento(self, segundos: float) -> None:
        if "stun" in self.imune:
            return
        self.tempo_atordoado = maxf(self.tempo_atordoado, segundos)

    def atualizar_efeitos(self, delta: float) -> None:
        self.tempo_lentidao = maxf(0.0, self.tempo_lentidao - delta)
        self.tempo_raiz = maxf(0.0, self.tempo_raiz - delta)
        self.tempo_atordoado = maxf(0.0, self.tempo_atordoado - delta)
