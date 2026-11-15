"""Rota dos monstros: uma linha de pontos percorrida por distância.

Port de ``jogo/src/core/route.gd``. Um monstro guarda só "quantos pixels já
andou" (a distância, um float de 64 bits); a rota converte isso em posição no
mapa (float32, como o Vector2 do Godot).
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence

import numpy as np

from monstervale_ia.vetor import CMP_EPSILON, Vetor, comprimento, distancia, mover_em_direcao, vetor


class Rota:
    def __init__(self, pontos: Sequence[Sequence[float]]) -> None:
        self.pontos: list[Vetor] = [vetor(x, y) for x, y in pontos]
        # _starts: distância (float64) em que cada segmento começa
        self.inicios: list[float] = []
        self.comprimento: float = 0.0
        for a, b in zip(self.pontos[:-1], self.pontos[1:]):
            self.inicios.append(self.comprimento)
            # distance_to devolve float32; a soma acontece em float64 (float do GDScript)
            self.comprimento += float(distancia(a, b))
        # Pré-cálculo por segmento (otimização): as mesmas contas que move_toward faz a
        # cada chamada, feitas uma vez só. Mesmos valores float32, mesma ordem.
        self._tamanhos = [float(distancia(a, b)) for a, b in zip(self.pontos[:-1], self.pontos[1:])]
        self._seg = []
        for a, b in zip(self.pontos[:-1], self.pontos[1:]):
            vd = (b[0] - a[0], b[1] - a[1])
            tam = comprimento(vd)
            self._seg.append((a, b, tam, vd[0] / tam if tam else None, vd[1] / tam if tam else None))
        self._direcoes = [int(b[0] > a[0]) - int(b[0] < a[0]) for a, b in zip(self.pontos[:-1], self.pontos[1:])]

    def posicao_e_direcao_em(self, d: float) -> tuple[Vetor, int]:
        """posicao_em(d) e direcao_horizontal_em(d) numa busca só (otimização)."""
        if not self.inicios:
            return self.posicao_em(d), 0
        i = self._segmento_em(d)
        return self._posicao_no_segmento(i, d), self._direcoes[i]

    def posicao_em(self, d: float) -> Vetor:
        """Ponto da rota a `d` pixels da entrada, preso entre o início e o fim."""
        if not self.inicios:
            return self.pontos[0] if self.pontos else vetor(0.0, 0.0)
        return self._posicao_no_segmento(self._segmento_em(d), d)

    def _posicao_no_segmento(self, i: int, d: float) -> Vetor:
        ao_longo = min(max(d - self.inicios[i], 0.0), self._tamanhos[i])  # clampf
        # Igual a mover_em_direcao(a, b, ao_longo), com vd/len já calculado.
        a, b, tam, qx, qy = self._seg[i]
        passo = np.float32(ao_longo)
        if tam <= passo or tam < CMP_EPSILON:
            return b
        return a[0] + qx * passo, a[1] + qy * passo

    def posicao_em_referencia(self, d: float) -> Vetor:
        """Versão direta (sem pré-cálculo), mantida para conferir a otimizada nos testes."""
        if not self.inicios:
            return self.pontos[0] if self.pontos else vetor(0.0, 0.0)
        i = self._segmento_em(d)
        a, b = self.pontos[i], self.pontos[i + 1]
        tamanho_segmento = float(distancia(a, b))
        ao_longo = min(max(d - self.inicios[i], 0.0), tamanho_segmento)
        return mover_em_direcao(a, b, ao_longo)

    def direcao_horizontal_em(self, d: float) -> int:
        """1 ou -1 em trechos horizontais (para espelhar o sprite), 0 em verticais."""
        if not self.inicios:
            return 0
        i = self._segmento_em(d)
        dx = self.pontos[i + 1][0] - self.pontos[i][0]
        return int(dx > 0) - int(dx < 0)  # signi(signf(dx))

    def _segmento_em(self, d: float) -> int:
        # O GDScript percorre do último segmento para o primeiro e devolve o maior i
        # com d >= início[i] (ou 0). A busca binária dá o mesmo i, em O(log n).
        return max(bisect_right(self.inicios, d) - 1, 0)
