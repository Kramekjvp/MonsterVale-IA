"""Rota: os mesmos testes do jogo + paridade bit a bit com o Godot."""

import json
from pathlib import Path

import numpy as np
import pytest

from monstervale_ia.mapa import Mapa
from monstervale_ia.rota import Rota

REFERENCIAS = Path(__file__).parent / "referencias" / "rota.json"


# --- Port de jogo/tests/unit/test_route.gd -------------------------------------

def _rota() -> Rota:
    return Rota([(0, 0), (100, 0), (100, 50)])


def test_comprimento_soma_todos_os_segmentos():
    assert _rota().comprimento == 150.0


def test_posicao_no_inicio_e_no_fim():
    assert _rota().posicao_em(0.0) == (0, 0)
    assert _rota().posicao_em(150.0) == (100, 50)


def test_posicao_interpola_dentro_do_segmento():
    assert _rota().posicao_em(50.0) == (50, 0)
    assert _rota().posicao_em(125.0) == (100, 25)


def test_posicao_fica_presa_fora_da_rota():
    assert _rota().posicao_em(-10.0) == (0, 0)
    assert _rota().posicao_em(999.0) == (100, 50)


def test_direcao_horizontal_segue_o_segmento():
    rota = Rota([(0, 0), (100, 0), (100, 50), (40, 50)])
    assert rota.direcao_horizontal_em(10.0) == 1
    assert rota.direcao_horizontal_em(120.0) == 0  # trecho vertical não define lado
    assert rota.direcao_horizontal_em(170.0) == -1


def test_rota_precisa_de_dois_pontos():
    rota = Rota([(5, 5)])
    assert rota.comprimento == 0.0
    assert rota.posicao_em(10.0) == (5, 5)


# --- Paridade com as respostas douradas do Godot -------------------------------

def _casos():
    referencias = json.loads(REFERENCIAS.read_text())
    for id_fase, rotas in referencias.items():
        for indice, ref in enumerate(rotas):
            yield pytest.param(id_fase, indice, ref, id=f"{id_fase}-rota{indice + 1}")


@pytest.mark.parametrize("id_fase, indice, ref", list(_casos()))
def test_paridade_com_o_godot(id_fase, indice, ref):
    mapa = Mapa.carregar(id_fase)
    rota = Rota(mapa.rotas[indice].tolist())
    assert rota.comprimento == ref["length"]
    for d, x, y, direcao in ref["samples"]:
        px, py = rota.posicao_em(d)
        # Igualdade exata dos bits em float32, sem tolerância.
        assert (px, py) == (np.float32(x), np.float32(y)), f"distância {d}"
        assert rota.direcao_horizontal_em(d) == direcao, f"distância {d}"
