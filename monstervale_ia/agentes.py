"""Agentes simples, sem rede neural: linhas de base (M4) e geradores de partidas de teste.

Cada agente é uma função ``agente(env, rng) -> ação``, que só pode escolher
ações permitidas pela máscara.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from monstervale_ia.ambiente import (
    ACAO_CHAMAR,
    CELULAS,
    CLASSES,
    TIPO_MELHORAR,
    AmbienteMonstervale,
    indice_acao,
)

Agente = Callable[[AmbienteMonstervale, np.random.Generator], int]


def aleatorio(chance_chamar: float = 0.3) -> Agente:
    """Sorteia entre as ações válidas; chama a onda com probabilidade `chance_chamar`."""

    def agir(env: AmbienteMonstervale, rng: np.random.Generator) -> int:
        mascara = env.action_masks()
        validas = np.flatnonzero(mascara)
        construir = validas[validas != ACAO_CHAMAR]
        if mascara[ACAO_CHAMAR] and (len(construir) == 0 or rng.random() < chance_chamar):
            return ACAO_CHAMAR
        melhorias = construir[(construir // CELULAS) == TIPO_MELHORAR]
        if len(melhorias) and rng.random() < 0.5:
            return int(rng.choice(melhorias))
        return int(rng.choice(construir))

    return agir


def heuristico(classes: list[str] | None = None) -> Agente:
    """Melhora quem for mais barato de melhorar; senão, posiciona colado na estrada
    (perto da vila primeiro), alternando as classes liberadas; senão, chama a onda.

    Com `classes`, só usa essas (ex.: ["archer"] imita o robô "só arqueiros" dos
    testes de balanceamento do jogo).
    """
    estado = {"compras": 0}

    def agir(env: AmbienteMonstervale, rng: np.random.Generator) -> int:
        mascara = env.action_masks()
        sim = env.sim
        melhorias = [
            (h.custo_melhoria(), h.celula) for h in sim.humanos
            if mascara[indice_acao(TIPO_MELHORAR, *h.celula)]
        ]
        if melhorias:
            return indice_acao(TIPO_MELHORAR, *min(melhorias)[1])
        liberadas = [
            k for k, c in enumerate(CLASSES)
            if c in sim.classes_disponiveis() and (classes is None or c in classes)
        ]
        if not liberadas:
            return ACAO_CHAMAR
        inicio = estado["compras"] % len(liberadas)
        for k in liberadas[inicio:] + liberadas[:inicio]:
            for celula in env.mapa.celulas_junto_a_estrada():
                acao = indice_acao(k, *celula)
                if mascara[acao]:
                    estado["compras"] += 1
                    return acao
        return ACAO_CHAMAR

    return agir


def jogar(env: AmbienteMonstervale, agente: Agente, semente: int = 0) -> dict:
    """Joga uma partida inteira e devolve o resumo."""
    env.reset(seed=semente)
    rng = np.random.default_rng(semente)
    retorno = 0.0
    while True:
        _, recompensa, terminou, truncou, info = env.step(agente(env, rng))
        retorno += recompensa
        if terminou or truncou:
            return {**{k: v for k, v in info.items() if k != "mascara"}, "retorno": retorno, "truncou": truncou}
