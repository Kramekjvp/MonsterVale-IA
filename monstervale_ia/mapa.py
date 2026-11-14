"""Mapa de uma fase do Monstervale: grid, células construíveis e rotas.

Lê os JSONs gerados por ``ferramentas/exportar_mapas.gd``. Coordenadas seguem o
jogo: ``(x, y)`` com x = coluna e y = linha, origem no canto superior esquerdo.
Posições em pixels usam float32, como o ``Vector2`` do Godot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
PASTA_MAPAS = RAIZ / "dados" / "mapas"

Celula = tuple[int, int]


@dataclass(frozen=True)
class Mapa:
    id: str
    tamanho_celula: int
    colunas: int
    linhas: int
    construiveis: frozenset[Celula]
    decoracao: frozenset[Celula]
    rotas: tuple[np.ndarray, ...]  # cada rota: array (n_pontos, 2) float32, em pixels
    vila: tuple[float, float]

    @classmethod
    def carregar(cls, id_fase: str, pasta: Path = PASTA_MAPAS) -> "Mapa":
        dados = json.loads((pasta / f"{id_fase}.json").read_text(encoding="utf-8"))
        return cls(
            id=dados["id"],
            tamanho_celula=dados["cell_size"],
            colunas=dados["columns"],
            linhas=dados["rows"],
            construiveis=frozenset(tuple(c) for c in dados["buildable"]),
            decoracao=frozenset(tuple(c) for c in dados["decor"]),
            rotas=tuple(np.asarray(r, dtype=np.float32) for r in dados["routes"]),
            vila=tuple(dados["village"]),
        )

    def celula_de(self, x: float, y: float) -> Celula:
        """Célula que contém o ponto (x, y) em pixels (como world_to_cell do jogo)."""
        return int(np.floor(x / self.tamanho_celula)), int(np.floor(y / self.tamanho_celula))

    def celulas_da_rota(self, indice: int = 0, passo: float = 4.0) -> list[Celula]:
        """Células do grid por onde a rota passa, na ordem do caminho.

        Percorre cada segmento em passos pequenos (em pixels) e anota as células
        dentro do grid. Pontos fora do mapa (a entrada começa em x = -16) são
        ignorados.
        """
        pontos = self.rotas[indice]
        celulas: list[Celula] = []
        for a, b in zip(pontos[:-1], pontos[1:]):
            comprimento = float(np.linalg.norm(b - a))
            n = max(1, int(np.ceil(comprimento / passo)))
            for t in np.linspace(0.0, 1.0, n + 1):
                p = a + (b - a) * t
                c = self.celula_de(float(p[0]), float(p[1]))
                if self.dentro(c) and (not celulas or celulas[-1] != c):
                    if c not in celulas:
                        celulas.append(c)
        return celulas

    def celulas_junto_a_estrada(self) -> list[Celula]:
        """Células construíveis coladas na estrada, começando pelo trecho mais perto da vila.

        Com duas rotas, intercala as células das duas para cobrir ambas.
        """
        celulas: list[Celula] = []
        for i in range(len(self.rotas)):
            for x, y in reversed(self.celulas_da_rota(i)):
                for c in [(x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)]:
                    if c in self.construiveis and c not in celulas:
                        celulas.append(c)
        if len(self.rotas) > 1:
            meio = len(celulas) // 2
            a, b = celulas[:meio], celulas[meio:]
            celulas = [c for par in zip(a, b) for c in par] + a[len(b):] + b[len(a):]
        return celulas

    def dentro(self, celula: Celula) -> bool:
        x, y = celula
        return 0 <= x < self.colunas and 0 <= y < self.linhas

    def desenho(self) -> str:
        """Desenho do mapa em texto: '#' construível, '1'/'2' rota, '*' decoração, 'V' vila."""
        grade = [["." for _ in range(self.colunas)] for _ in range(self.linhas)]
        for x, y in self.construiveis:
            grade[y][x] = "#"
        for x, y in self.decoracao:
            if grade[y][x] == ".":
                grade[y][x] = "*"
        for i in range(len(self.rotas)):
            for x, y in self.celulas_da_rota(i):
                grade[y][x] = str(i + 1) if grade[y][x] in ".*#" else "+"
        vx, vy = self.celula_de(*self.vila)
        grade[vy][vx] = "V"
        cabecalho = "   " + "".join(str(x % 10) for x in range(self.colunas))
        corpo = [f"{y:2d} " + "".join(linha) for y, linha in enumerate(grade)]
        return "\n".join([cabecalho, *corpo])
