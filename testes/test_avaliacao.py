"""Avaliação (M4): variante perturbada, resumo de resultados e régua humana."""

from functools import partial

from monstervale_ia.agentes import aleatorio, heuristico
from monstervale_ia.avaliacao import avaliar, estrelas_por_vidas, melhor_humano, perturbar_fase
from monstervale_ia.dados_jogo import carregar_fase


def test_perturbacao_e_reproduzivel_e_so_mexe_nas_ondas():
    fase = carregar_fase("level_03")
    a, b, c = perturbar_fase(fase, 7), perturbar_fase(fase, 7), perturbar_fase(fase, 8)
    assert a == b and a != c
    assert fase["waves"][0]["groups"][0]["interval"] == carregar_fase("level_03")["waves"][0]["groups"][0]["interval"]
    for chave in ("routes", "buildable", "classes", "start_gold", "lives"):
        assert a[chave] == fase[chave]


def test_perturbacao_respeita_os_limites():
    fase = carregar_fase("level_05")
    for semente in range(20):
        nova = perturbar_fase(fase, semente)
        for onda_a, onda_b in zip(fase["waves"], nova["waves"]):
            for ga, gb in zip(onda_a["groups"], onda_b["groups"]):
                assert gb["count"] >= 1 and abs(gb["count"] - ga["count"]) <= 1
                assert 0.9 * ga["interval"] <= gb["interval"] <= 1.1 * ga["interval"]
                assert gb["monster"] == ga["monster"]


def test_avaliar_resume_as_partidas():
    r = avaliar("level_01", "heurístico", heuristico, [0])
    assert (r.partidas, r.vitorias, r.vidas_media) == (1, 1.0, 15.0)
    r = avaliar("level_01", "aleatório", partial(aleatorio, 0.3), [0, 1, 2])
    assert r.partidas == 3 and r.vitorias == 0.0


def test_melhor_humano_e_estrelas():
    assert estrelas_por_vidas(18) == 3 and estrelas_por_vidas(17) == 2 and estrelas_por_vidas(9) == 1
    humano = melhor_humano("level_01")
    assert humano["estrelas"] == 3 and humano["vidas"] == 20
