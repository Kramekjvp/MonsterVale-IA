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


# --- Avaliação de uma rede (M6) ---------------------------------------------------------

import json
import pickle
from dataclasses import asdict

import pytest
import torch

from monstervale_ia.agente_rede import (
    carregar_rede, criar_agente, criterio_dominada, exportar_partida_gulosa, fabrica_agente,
)
from monstervale_ia.agentes import jogar
from monstervale_ia.ambiente import TIPOS_POR_CELULA, AmbienteMonstervale
from monstervale_ia.avaliacao import ambiente
from monstervale_ia.ppo import ConfigPPO, criar_rede


@pytest.fixture(scope="module")
def rede_pt(tmp_path_factory):
    torch.manual_seed(0)
    config = ConfigPPO(rede={"largura": 8, "camadas": 2, "oculta": 8})
    rede = criar_rede(AmbienteMonstervale("level_01"), TIPOS_POR_CELULA, **config.rede)
    caminho = tmp_path_factory.mktemp("rede") / "rede.pt"
    torch.save({"rede": rede.state_dict(), "config": asdict(config)}, caminho)
    return caminho


def _jogar_registrando(caminho, gulosa, semente):
    agente = criar_agente(str(caminho), "level_01", gulosa)
    acoes = []

    def espiao(env, rng):
        a = agente(env, rng)
        assert env.action_masks()[a]
        acoes.append(a)
        return a

    return jogar(ambiente("level_01"), espiao, semente), acoes


def test_carregar_rede_em_modo_de_avaliacao(rede_pt):
    assert not carregar_rede(rede_pt, "level_01").training


def test_agente_so_escolhe_acoes_validas_e_gulosa_e_deterministica(rede_pt):
    r1, a1 = _jogar_registrando(rede_pt, True, 0)
    r2, a2 = _jogar_registrando(rede_pt, True, 0)
    assert a1 == a2 and r1 == r2


def test_sorteada_repete_com_a_mesma_semente(rede_pt):
    _, a1 = _jogar_registrando(rede_pt, False, 3)
    _, a2 = _jogar_registrando(rede_pt, False, 3)
    _, a3 = _jogar_registrando(rede_pt, False, 4)
    assert a1 == a2 and a1 != a3


def test_criterio_devolve_a_estrutura(rede_pt):
    gulosa, sorteada, veredito = criterio_dominada(rede_pt, "level_01", sementes=[0, 1])
    assert gulosa.partidas == 1 and sorteada.partidas == 2
    assert 0 <= veredito.tres_estrelas_sorteada <= 1 and veredito.minimo == 0.8
    assert veredito.dominada is False  # rede aleatória não domina
    assert hasattr(gulosa, "ouro_medio")


def test_criterio_com_processos(rede_pt):
    _, sorteada, _ = criterio_dominada(rede_pt, "level_01", processos=2, sementes=[0, 1, 2, 3])
    _, sequencial, _ = criterio_dominada(rede_pt, "level_01", processos=1, sementes=[0, 1, 2, 3])
    assert sorteada.partidas == 4 and sorteada == sequencial


def test_fabrica_e_serializavel(rede_pt):
    pickle.loads(pickle.dumps(fabrica_agente(rede_pt, "level_01", True)))


def test_exporta_a_partida_gulosa(rede_pt, tmp_path):
    destino = exportar_partida_gulosa(rede_pt, "level_01", tmp_path / "partida.json")
    assert destino.exists() and json.loads(destino.read_text(encoding="utf-8"))
