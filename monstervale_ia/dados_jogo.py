"""Carrega o balanceamento do jogo (jogo/data/*.json) e o mapa de cada fase.

Port da parte de leitura de ``jogo/src/core/game_data.gd`` e da junção feita
por ``jogo/src/game/level_reader.gd`` (balanceamento + mapa exportado).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from monstervale_ia.mapa import PASTA_MAPAS, Mapa

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "jogo" / "data"
IDS_FASES = ["level_01", "level_02", "level_03", "level_04", "level_05"]


def _ler(caminho: Path) -> dict[str, Any]:
    return json.loads(caminho.read_text(encoding="utf-8"))


def carregar_catalogo(pasta: Path = PASTA_DADOS) -> dict[str, Any]:
    """Unidades (humanos) e monstros, como GameData.load_catalog()."""
    return {
        "units": _ler(pasta / "units.json"),
        "monsters": _ler(pasta / "monsters.json"),
    }


def carregar_fase(id_fase: str, pasta: Path = PASTA_DADOS, pasta_mapas: Path = PASTA_MAPAS) -> dict[str, Any]:
    """Balanceamento da fase + mapa, no mesmo formato que LevelReader.read() monta.

    Chaves vindas do mapa: cell_size, routes (listas de pontos), route
    (a primeira) e buildable (conjunto de células).
    """
    fase = _ler(pasta / "levels" / f"{id_fase}.json")
    mapa = Mapa.carregar(id_fase, pasta_mapas)
    fase["cell_size"] = mapa.tamanho_celula
    fase["routes"] = [r.tolist() for r in mapa.rotas]
    fase["route"] = fase["routes"][0]
    fase["buildable"] = set(mapa.construiveis)
    return fase
