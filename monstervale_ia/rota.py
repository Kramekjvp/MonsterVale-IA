"""Rota dos monstros: uma linha de pontos percorrida por distância.

Port de ``jogo/src/core/route.gd``. Um monstro guarda só "quantos pixels já
andou" (a distância, um float de 64 bits); a rota converte isso em posição no
mapa (float32, como o Vector2 do Godot).
"""

from __future__ import annotations

from collections.abc import Sequence

from monstervale_ia.vetor import Vetor, distancia, mover_em_direcao, vetor


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

    def posicao_em(self, d: float) -> Vetor:
        """Ponto da rota a `d` pixels da entrada, preso entre o início e o fim."""
        if not self.inicios:
            return self.pontos[0] if self.pontos else vetor(0.0, 0.0)
        i = self._segmento_em(d)
        a, b = self.pontos[i], self.pontos[i + 1]
        tamanho_segmento = float(distancia(a, b))
        ao_longo = min(max(d - self.inicios[i], 0.0), tamanho_segmento)  # clampf
        return mover_em_direcao(a, b, ao_longo)

    def direcao_horizontal_em(self, d: float) -> int:
        """1 ou -1 em trechos horizontais (para espelhar o sprite), 0 em verticais."""
        if not self.inicios:
            return 0
        i = self._segmento_em(d)
        dx = self.pontos[i + 1][0] - self.pontos[i][0]
        return int(dx > 0) - int(dx < 0)  # signi(signf(dx))

    def _segmento_em(self, d: float) -> int:
        # Mesmo laço do GDScript: do último segmento para o primeiro.
        for i in range(len(self.inicios) - 1, -1, -1):
            if d >= self.inicios[i]:
                return i
        return 0
