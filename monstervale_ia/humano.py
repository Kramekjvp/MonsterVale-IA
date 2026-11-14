"""Estado de um humano posicionado. Port de ``jogo/src/core/unit.gd``."""

from __future__ import annotations

from typing import Any

from monstervale_ia.godot import div_int, mini
from monstervale_ia.mapa import Celula
from monstervale_ia.vetor import Vetor

NIVEL_MAXIMO = 3
PRIORIDADES = ["first", "last", "strongest", "closest"]


class Humano:
    def __init__(self, tipo: str, dados: dict[str, Any], celula: Celula, centro: Vetor) -> None:
        self.tipo = tipo
        self.celula = celula
        self.posicao = centro
        self.nivel: int = 1
        self.gasto: int = 0
        self.prioridade: str = "first"
        self.recarga: float = 0.0
        self.vida: int = 0
        self.tempo_caido: float = 0.0
        self.bloqueados: list = []  # monstros que ele segura
        self.olhando: int = 1
        self.tempo_sem_dano: float = 0.0
        self.ataques_feitos: int = 0

        self._dados = dados
        self._recuperando: float = 0.0
        self.gasto = int(self.atributos()["cost"])
        self.vida = int(self.atributos().get("hp", 0))

    def atributos(self) -> dict[str, Any]:
        """Os números do nível atual (dano, alcance, recarga...)."""
        return self._dados["levels"][self.nivel - 1]

    def corpo_a_corpo(self) -> bool:
        return self._dados["attack"] == "melee"

    def tipo_dano(self) -> str:
        return self._dados["damage_type"]

    def esta_caido(self) -> bool:
        return self.tempo_caido > 0.0

    def pode_melhorar(self) -> bool:
        return self.nivel < NIVEL_MAXIMO

    def custo_melhoria(self) -> int:
        return int(self._dados["levels"][self.nivel]["cost"]) if self.pode_melhorar() else 0

    def reembolso(self) -> int:
        return div_int(self.gasto, 2)  # `spent / 2` entre ints no GDScript

    def tem_espaco_para_bloquear(self) -> bool:
        return (
            self.corpo_a_corpo()
            and not self.esta_caido()
            and len(self.bloqueados) < int(self.atributos().get("block", 0))
        )

    def subir_nivel(self) -> None:
        self.gasto += self.custo_melhoria()
        vida_anterior = int(self.atributos().get("hp", 0))
        self.nivel += 1
        # Ganha a diferença de vida máxima, mantendo o dano que já levou.
        self.vida += int(self.atributos().get("hp", 0)) - vida_anterior

    def recuperar(self, delta: float) -> None:
        """Recupera vida depois de um tempo sem levar dano, nos níveis que têm regen."""
        self.tempo_sem_dano += delta
        taxa = float(self.atributos().get("regen", 0.0))
        if taxa <= 0.0 or self.tempo_sem_dano < float(self.atributos().get("regen_delay", 0.0)):
            return
        # Acumula frações de vida e só soma os pontos inteiros.
        self._recuperando += taxa * delta
        ganho = int(self._recuperando)
        self._recuperando -= ganho
        self.vida = mini(self.vida + ganho, int(self.atributos()["hp"]))

    def trocar_prioridade(self) -> None:
        self.prioridade = PRIORIDADES[(PRIORIDADES.index(self.prioridade) + 1) % len(PRIORIDADES)]
