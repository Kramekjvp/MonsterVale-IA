"""Sanidade dos mapas exportados do jogo (marco M1)."""

import pytest

from monstervale_ia.mapa import Mapa

FASES = ["level_01", "level_02", "level_03", "level_04", "level_05"]
# Fases com duas entradas, segundo docs/001-DECISOES.md do jogo.
ROTAS_POR_FASE = {"level_01": 1, "level_02": 1, "level_03": 2, "level_04": 2, "level_05": 2}


@pytest.fixture(params=FASES)
def mapa(request) -> Mapa:
    return Mapa.carregar(request.param)


def test_grid_e_20_por_11(mapa):
    assert (mapa.colunas, mapa.linhas, mapa.tamanho_celula) == (20, 11, 32)


def test_construiveis_ficam_dentro_do_grid(mapa):
    assert mapa.construiveis
    assert all(mapa.dentro(c) for c in mapa.construiveis)


def test_quantidade_de_rotas(mapa):
    assert len(mapa.rotas) == ROTAS_POR_FASE[mapa.id]


def test_rota_nunca_passa_por_celula_construivel(mapa):
    # Os humanos ficam ao lado da estrada, nunca em cima dela.
    for i in range(len(mapa.rotas)):
        assert not set(mapa.celulas_da_rota(i)) & mapa.construiveis


def test_rotas_comecam_fora_do_mapa_e_terminam_na_vila(mapa):
    for rota in mapa.rotas:
        assert not mapa.dentro(mapa.celula_de(*rota[0]))
        assert mapa.celula_de(*rota[-1]) == mapa.celula_de(*mapa.vila)


def test_posicoes_em_float32_como_o_godot(mapa):
    assert all(r.dtype.name == "float32" for r in mapa.rotas)
