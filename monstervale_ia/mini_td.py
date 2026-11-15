"""Mini-TD: um tower defense de brinquedo 5×5 para validar o PPO (M5, decisão 9).

Tem a mesma "forma" do AmbienteMonstervale (grid + vetor global, ações
``tipo × células + chamar``, máscara, recompensa por onda + estrelas), mas é
pequeno o bastante para calcular a estratégia ÓTIMA por força bruta
(``retorno_otimo``). Se o PPO não chegar perto do ótimo aqui, o bug está no
PPO, não no Monstervale.

Regras
------
- 4 traçados de caminho; um é sorteado a cada partida (a rede precisa ler o mapa).
- Torre: custa 3; acerta o monstro mais adiantado nas 8 células em volta
  (dano 1 por tique; nível 2 dá dano 2, a melhoria custa 3).
- Começa com 6 de ouro e ganha 3 depois de cada onda. 3 ondas, 10 vidas.
- Monstros andam 1 célula por tique e entram a cada 2 tiques.
- Recompensa: por onda −(vidas perdidas ÷ 10); no fim, vitória +1 e +0,5 por
  estrela (3★ = ≥ 90% das vidas); derrota −1.
"""

from __future__ import annotations

import itertools
from functools import lru_cache

import gymnasium as gym
import numpy as np
from gymnasium import spaces

LADO = 5
CELULAS = LADO * LADO
TIPO_TORRE, TIPO_MELHORAR = 0, 1
TIPOS_POR_CELULA = 2
ACAO_CHAMAR = TIPOS_POR_CELULA * CELULAS  # 50
N_ACOES = ACAO_CHAMAR + 1  # 51

TRACADOS = [
    [(x, 2) for x in range(5)],  # reta horizontal
    [(2, y) for y in range(5)],  # reta vertical
    [(0, 1), (1, 1), (2, 1), (3, 1), (3, 2), (3, 3), (2, 3), (1, 3), (0, 3)],  # U
    [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2), (3, 2), (3, 3), (4, 3), (4, 4)],  # escada
]
ONDAS = [(4, 4), (5, 6), (6, 8)]  # (quantidade, vida) de cada onda
OURO_INICIAL, OURO_POR_ONDA, CUSTO = 6, 3, 3
VIDAS = 10
ESPACAMENTO = 2
CANAIS = ["construivel", "caminho", "progresso", "torre", "nivel"]
N_GLOBAL = 4


# Calculado por retorno_otimo() (leva ~100 s; conferido em testes/test_mini_td.py).
RETORNO_OTIMO = {0: 2.5, 1: 2.5, 2: 2.5, 3: 2.5}


def simular_onda(tracado: int, torres: tuple[tuple[int, int, int], ...], onda: int) -> int:
    """Roda uma onda e devolve quantos monstros passaram. torres = ((x, y, nível), ...)."""
    caminho = TRACADOS[tracado]
    quantidade, vida = ONDAS[onda]
    alcance = [
        [i for i, (cx, cy) in enumerate(caminho) if abs(cx - x) <= 1 and abs(cy - y) <= 1]
        for x, y, _ in torres
    ]
    monstros: list[list[int]] = []  # [posição no caminho, vida]
    passaram = surgidos = 0
    tique = 0
    while surgidos < quantidade or monstros:
        if surgidos < quantidade and tique % ESPACAMENTO == 0:
            monstros.append([-1, vida])
            surgidos += 1
        for m in monstros:
            m[0] += 1
        passaram += sum(1 for m in monstros if m[0] >= len(caminho))
        monstros = [m for m in monstros if m[0] < len(caminho)]
        for (_, _, nivel), cobertas in zip(torres, alcance):
            alvos = [m for m in monstros if m[0] in cobertas]
            if alvos:
                max(alvos, key=lambda m: m[0])[1] -= nivel
                monstros = [m for m in monstros if m[1] > 0]
        tique += 1
    return passaram


def _estrelas(vidas: int) -> int:
    razao = vidas / VIDAS
    return 3 if razao >= 0.9 else 2 if razao >= 0.5 else 1


def _recompensa_final(vidas: int) -> float:
    return (1.0 + 0.5 * _estrelas(vidas)) if vidas > 0 else -1.0


@lru_cache(maxsize=None)
def retorno_otimo(tracado: int) -> float:
    """Melhor retorno possível no traçado, por força bruta (programação dinâmica).

    Uma configuração (torres e níveis) só cresce entre as ondas, e o resultado de
    cada onda só depende da configuração daquele momento. Então basta testar
    todas as sequências crescentes de configurações que cabem no ouro.
    """
    construiveis = [(x, y) for y in range(LADO) for x in range(LADO) if (x, y) not in TRACADOS[tracado]]

    def configuracoes(ouro: int):
        itens_max = ouro // CUSTO
        for n in range(itens_max + 1):
            for celulas in itertools.combinations(construiveis, n):
                for melhorias in range(min(n, itens_max - n) + 1):
                    for subir in itertools.combinations(celulas, melhorias):
                        yield frozenset((x, y, 2 if (x, y) in subir else 1) for x, y in celulas)

    ouro_por_onda = [OURO_INICIAL + OURO_POR_ONDA * k for k in range(len(ONDAS))]
    todas = list(configuracoes(ouro_por_onda[-1]))

    def custo(c) -> int:
        return CUSTO * sum(n for _, _, n in c)

    def contem(maior, menor) -> bool:
        niveis = {(x, y): n for x, y, n in maior}
        return all(niveis.get((x, y), 0) >= n for x, y, n in menor)

    @lru_cache(maxsize=None)
    def passaram(c, onda):
        return simular_onda(tracado, tuple(sorted(c)), onda)

    # melhor[k][(c, vidas)] = melhor retorno das ondas k.. em diante
    def melhor(k: int, c: frozenset, vidas: int) -> float:
        if k == len(ONDAS):
            return _recompensa_final(vidas)
        resultado = -np.inf
        for nova in todas:
            if custo(nova) > ouro_por_onda[k] or not contem(nova, c):
                continue
            perdidas = min(passaram(nova, k), vidas)
            r = -perdidas / VIDAS
            if vidas - perdidas <= 0:
                resultado = max(resultado, r + _recompensa_final(0))
            else:
                resultado = max(resultado, r + melhor(k + 1, nova, vidas - perdidas))
        return resultado

    melhor = lru_cache(maxsize=None)(melhor)
    return float(melhor(0, frozenset(), VIDAS))


class MiniTD(gym.Env):
    """Mesma interface do AmbienteMonstervale: obs {"grid", "global"}, action_masks()."""

    def __init__(self, tracados: list[int] | None = None, max_acoes_por_construcao: int = 6) -> None:
        self.tracados = tracados if tracados is not None else list(range(len(TRACADOS)))
        self.max_acoes_por_construcao = max_acoes_por_construcao
        self.action_space = spaces.Discrete(N_ACOES)
        self.observation_space = spaces.Dict({
            "grid": spaces.Box(0.0, 1.0, shape=(len(CANAIS), LADO, LADO), dtype=np.float32),
            "global": spaces.Box(0.0, np.inf, shape=(N_GLOBAL,), dtype=np.float32),
        })

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self.tracado = int(self.np_random.choice(self.tracados))
        self.caminho = TRACADOS[self.tracado]
        self.torres: dict[tuple[int, int], int] = {}
        self.ouro = OURO_INICIAL
        self.vidas = VIDAS
        self.onda = 0
        self.acoes = 0
        return self._obs(), self._info()

    def action_masks(self) -> np.ndarray:
        m = np.zeros(N_ACOES, dtype=bool)
        if self.onda >= len(ONDAS) or self.vidas <= 0:
            return m
        m[ACAO_CHAMAR] = True
        if self.acoes >= self.max_acoes_por_construcao or self.ouro < CUSTO:
            return m
        for y in range(LADO):
            for x in range(LADO):
                i = y * LADO + x
                if (x, y) in self.caminho:
                    continue
                nivel = self.torres.get((x, y), 0)
                m[TIPO_TORRE * CELULAS + i] = nivel == 0
                m[TIPO_MELHORAR * CELULAS + i] = nivel == 1
        return m

    def step(self, acao: int):
        acao = int(acao)
        assert self.action_masks()[acao], f"ação inválida: {acao}"
        if acao != ACAO_CHAMAR:
            tipo, i = divmod(acao, CELULAS)
            y, x = divmod(i, LADO)
            self.torres[(x, y)] = 1 if tipo == TIPO_TORRE else 2
            self.ouro -= CUSTO
            self.acoes += 1
            return self._obs(), 0.0, False, False, self._info()
        torres = tuple(sorted((x, y, n) for (x, y), n in self.torres.items()))
        perdidas = min(simular_onda(self.tracado, torres, self.onda), self.vidas)
        self.vidas -= perdidas
        self.onda += 1
        self.ouro += OURO_POR_ONDA
        self.acoes = 0
        recompensa = -perdidas / VIDAS
        terminou = self.vidas <= 0 or self.onda >= len(ONDAS)
        if terminou:
            recompensa += _recompensa_final(self.vidas)
        return self._obs(), recompensa, terminou, False, self._info()

    def _obs(self) -> dict[str, np.ndarray]:
        grid = np.zeros((len(CANAIS), LADO, LADO), dtype=np.float32)
        grid[0] = 1.0
        for j, (x, y) in enumerate(self.caminho):
            grid[0, y, x] = 0.0
            grid[1, y, x] = 1.0
            grid[2, y, x] = j / (len(self.caminho) - 1)
        for (x, y), n in self.torres.items():
            grid[3, y, x] = 1.0
            grid[4, y, x] = n / 2
        globais = np.array([
            self.ouro / 12, self.vidas / VIDAS, self.onda / len(ONDAS),
            (self.max_acoes_por_construcao - self.acoes) / self.max_acoes_por_construcao,
        ], dtype=np.float32)
        return {"grid": grid, "global": globais}

    def _info(self) -> dict:
        return {"tracado": self.tracado, "vidas": self.vidas, "onda": self.onda}
