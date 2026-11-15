"""PPO, rede e mini-TD (M5)."""

import numpy as np
import pytest
import torch

from monstervale_ia import ambiente as amb
from monstervale_ia import mini_td as mt
from monstervale_ia.ppo import ConfigPPO, escolher, treinar, vantagens_gae
from monstervale_ia.rede import RedePolitica

# --- Rede -----------------------------------------------------------------------------


def test_mesma_rede_serve_para_grids_de_tamanhos_diferentes():
    rede = RedePolitica(canais_grid=5, tamanho_global=4, tipos_por_celula=2, largura=16, camadas=2, oculta=16)
    for a, l in [(5, 5), (11, 20), (7, 13)]:
        notas, valor = rede(torch.zeros(3, 5, a, l), torch.zeros(3, 4))
        assert notas.shape == (3, 2 * a * l + 1) and valor.shape == (3,)


def test_ordem_das_notas_e_a_mesma_das_acoes_do_ambiente():
    # A nota da ação "tipo k na célula (x, y)" tem que vir do mapa k, linha y, coluna x.
    rede = RedePolitica(canais_grid=12, tamanho_global=29, tipos_por_celula=9, largura=8, camadas=1, oculta=8)
    with torch.no_grad():
        rede.cabeca_espacial.weight.zero_()
        rede.cabeca_espacial.bias.copy_(torch.arange(9, dtype=torch.float32))  # nota = tipo
    notas, _ = rede(torch.zeros(1, 12, 11, 20), torch.zeros(1, 29))
    for tipo, x, y in [(0, 0, 0), (3, 7, 4), (8, 19, 10)]:
        assert notas[0, amb.indice_acao(tipo, x, y)] == tipo


def test_rede_nunca_sorteia_acao_proibida():
    env = amb.AmbienteMonstervale("level_01")
    obs, _ = env.reset()
    rede = RedePolitica(12, 29, 9, largura=8, camadas=1, oculta=8)
    mascara = env.action_masks()
    rng = np.random.default_rng(0)
    for _ in range(200):
        assert mascara[escolher(rede, obs, mascara, gulosa=False, rng=rng)]
    assert mascara[escolher(rede, obs, mascara, gulosa=True)]


# --- GAE ------------------------------------------------------------------------------


def test_gae_calculado_a_mao():
    # 1 ambiente, 3 passos, partida acaba no passo 1; γ = 0,5, λ = 1 (sem atenuação).
    r = np.array([[1.0], [2.0], [4.0]], dtype=np.float32)
    v = np.array([[0.5], [1.0], [2.0]], dtype=np.float32)
    fim = np.array([[0.0], [1.0], [0.0]], dtype=np.float32)
    vant, ret = vantagens_gae(r, v, fim, np.array([3.0], dtype=np.float32), gamma=0.5, lambd=1.0)
    # passo 2: δ = 4 + 0,5·3 − 2 = 3,5
    # passo 1 (fim): δ = 2 − 1 = 1; sem futuro
    # passo 0: δ = 1 + 0,5·1 − 0,5 = 1; A = 1 + 0,5·1 = 1,5
    np.testing.assert_allclose(vant[:, 0], [1.5, 1.0, 3.5])
    np.testing.assert_allclose(ret[:, 0], [2.0, 2.0, 5.5])


# --- Mini-TD --------------------------------------------------------------------------


def test_mini_td_mascara_e_observacao():
    env = mt.MiniTD(tracados=[0])
    obs, _ = env.reset(seed=0)
    assert env.observation_space.contains(obs)
    m = env.action_masks()
    assert m[mt.ACAO_CHAMAR] and m.sum() == 20 + 1  # 20 células fora da estrada + chamar
    _, _, _, _, _ = env.step(mt.TIPO_TORRE * mt.CELULAS + 0)  # torre em (0,0)
    assert env.action_masks()[mt.TIPO_MELHORAR * mt.CELULAS + 0]


@pytest.mark.lento
def test_retorno_otimo_do_mini_td():
    for t, esperado in mt.RETORNO_OTIMO.items():
        assert mt.retorno_otimo(t) == pytest.approx(esperado)


@pytest.mark.lento
def test_ppo_resolve_o_mini_td(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent / "ferramentas"))
    from treinar_mini_td import avaliar_mini_td

    config = ConfigPPO(
        total_passos=40_000, n_ambientes=8, passos_por_coleta=64, semente=1, pasta=str(tmp_path),
        rede={"largura": 32, "camadas": 3, "oculta": 64},
    )
    rede, _ = treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, config)
    assert avaliar_mini_td(rede, gulosa=True)["fracao_do_otimo"] == 1.0
    assert avaliar_mini_td(rede, gulosa=False, partidas_por_tracado=50)["fracao_do_otimo"] >= 0.97
