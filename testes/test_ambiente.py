"""Ambiente Gymnasium (M3): espaço, máscara, recompensa, determinismo e exportação."""

import json
from pathlib import Path

import numpy as np
import pytest

from monstervale_ia.agentes import aleatorio, heuristico, jogar
from monstervale_ia.ambiente import (
    ACAO_CHAMAR,
    CANAIS,
    CLASSES,
    N_ACOES,
    TIPO_DISPENSAR,
    TIPO_MELHORAR,
    AmbienteMonstervale,
    Recompensas,
    acao_para_texto,
    indice_acao,
)
from monstervale_ia.dados_jogo import IDS_FASES, carregar_catalogo
from monstervale_ia.roteiro import executar
from monstervale_ia.simulacao import Simulacao
from monstervale_ia.dados_jogo import carregar_fase

REF = Path(__file__).parent / "referencias"


# --- Espaços e observação ------------------------------------------------------------

def test_espacos_e_observacao_inicial():
    env = AmbienteMonstervale("level_01")
    obs, info = env.reset()
    assert env.observation_space.contains(obs)
    assert env.action_space.n == N_ACOES == 1981
    assert obs["grid"].shape == (len(CANAIS), 11, 20)
    construivel = obs["grid"][CANAIS.index("construivel")]
    assert {(x, y) for y, x in zip(*np.nonzero(construivel))} == set(env.mapa.construiveis)
    # Fase 1 começa com 120 de ouro e só arqueiro (65) e guerreiro (50): 2 classes × 124 células + chamar
    assert env.action_masks().sum() == 2 * len(env.mapa.construiveis) + 1


def test_progresso_na_rota_vai_de_0_na_entrada_a_1_na_vila():
    env = AmbienteMonstervale("level_01")
    obs, _ = env.reset()
    progresso = obs["grid"][CANAIS.index("progresso_rota")]
    celulas = env.mapa.celulas_da_rota(0)
    (x0, y0), (x1, y1) = celulas[0], celulas[-1]
    assert progresso[y0, x0] == 0.0 and progresso[y1, x1] == 1.0


def test_humano_aparece_no_canal_da_classe_e_do_nivel():
    env = AmbienteMonstervale("level_01")
    env.reset()
    x, y = env.mapa.celulas_junto_a_estrada()[0]
    obs, *_ = env.step(indice_acao(CLASSES.index("archer"), x, y))
    assert obs["grid"][CANAIS.index("classe_archer"), y, x] == 1.0
    assert obs["grid"][CANAIS.index("nivel"), y, x] == pytest.approx(1 / 3)


def test_duas_rotas_marcam_a_entrada_da_proxima_onda():
    env = AmbienteMonstervale("level_03")
    obs, _ = env.reset()
    assert obs["grid"][CANAIS.index("rota_proxima_onda")].sum() > 0


# --- Máscara ----------------------------------------------------------------------------

def test_acoes_fora_da_mascara_sao_recusadas():
    env = AmbienteMonstervale("level_01")
    env.reset()
    mago = indice_acao(CLASSES.index("mage"), 3, 4)  # mago não existe na Fase 1
    assert not env.action_masks()[mago]
    with pytest.raises(ValueError):
        env.step(mago)


def test_melhorar_e_dispensar_so_onde_ha_humano():
    env = AmbienteMonstervale("level_01")
    env.reset()
    x, y = env.mapa.celulas_junto_a_estrada()[0]
    env.step(indice_acao(CLASSES.index("warrior"), x, y))
    mascara = env.action_masks()
    assert mascara[indice_acao(TIPO_DISPENSAR, x, y)]
    assert mascara[indice_acao(TIPO_MELHORAR, x, y)]  # sobrou 70 de ouro, melhoria custa 30
    assert mascara.reshape(-1)[: ACAO_CHAMAR].reshape(9, 220)[TIPO_DISPENSAR].sum() == 1


def test_limite_de_acoes_por_construcao_obriga_a_chamar():
    env = AmbienteMonstervale("level_01", max_acoes_por_construcao=2)
    env.reset()
    celulas = env.mapa.celulas_junto_a_estrada()
    env.step(indice_acao(CLASSES.index("warrior"), *celulas[0]))
    env.step(indice_acao(CLASSES.index("warrior"), *celulas[1]))
    mascara = env.action_masks()
    assert mascara.sum() == 1 and mascara[ACAO_CHAMAR]


@pytest.mark.parametrize("fase", IDS_FASES)
def test_agente_aleatorio_nunca_escolhe_acao_que_falha(fase):
    # O ambiente confere (assert) que toda ação permitida pela máscara funciona.
    for semente in range(3):
        resumo = jogar(AmbienteMonstervale(fase), aleatorio(0.2), semente)
        assert resumo["estado"] in ("won", "lost")


def test_acao_para_texto():
    assert acao_para_texto(ACAO_CHAMAR) == "chamar onda"
    assert acao_para_texto(indice_acao(0, 3, 4)) == "posicionar archer em (3,4)"
    assert acao_para_texto(indice_acao(TIPO_MELHORAR, 19, 10)) == "melhorar (19,10)"


# --- Recompensa ---------------------------------------------------------------------------

def test_recompensa_soma_vidas_perdidas_e_resultado():
    env = AmbienteMonstervale("level_01")
    resumo = jogar(env, heuristico())
    r = Recompensas()
    perdidas = (20 - resumo["vidas"]) / 20
    if resumo["estado"] == "won":
        esperado = -perdidas + r.vitoria + r.por_estrela * resumo["estrelas"]
    else:
        # derrota graduada: peso × (ondas que faltavam ÷ total); ondas_iniciadas é a onda da derrota
        faltavam = (env.sim.total_ondas() - env.sim.ondas_iniciadas() + 1) / env.sim.total_ondas()
        esperado = -perdidas + r.derrota * faltavam
    assert resumo["retorno"] == pytest.approx(esperado)


def _perder_sem_construir(fase, **opcoes):
    """Chama as ondas sem posicionar nada até perder. Devolve (onda da derrota, retorno, env)."""
    env = AmbienteMonstervale(fase, **opcoes)
    env.reset()
    retorno = 0.0
    while True:
        _, recompensa, terminou, truncado, info = env.step(ACAO_CHAMAR)
        retorno += recompensa
        if terminou or truncado:
            assert env.sim.estado == "lost"
            return info["onda"], retorno, env


def test_derrota_graduada_valor_exato():
    # Sem defesa, a level_01 perde na onda 3 (1-based: ondas_iniciadas já contava a da derrota).
    # Venceu 2 de 12 ondas, então faltavam 10/12; as vidas perdidas somam 20/20 = 1.
    onda, retorno, _ = _perder_sem_construir("level_01")
    assert onda == 3
    assert retorno == pytest.approx(-1.0 - 10 / 12)
    # level_03 perde na onda 4: faltavam 9/12
    onda, retorno, _ = _perder_sem_construir("level_03")
    assert onda == 4
    assert retorno == pytest.approx(-1.0 - 9 / 12)


def test_derrota_na_onda_1_vale_o_peso_cheio():
    env = AmbienteMonstervale("level_01")
    env.reset()
    env.sim.vidas = 1  # um monstro que passe já derrota, ainda na onda 1
    _, recompensa, terminou, _, info = env.step(ACAO_CHAMAR)
    assert terminou and env.sim.estado == "lost" and info["onda"] == 1
    assert recompensa == pytest.approx(-1 / 20 - 1.0)  # peso × 12/12: igual ao comportamento antigo


def test_derrota_cedo_vale_menos_que_derrota_tardia():
    # Mesma fase, mesmo número de vidas: perder cada vez mais tarde tem que doer menos.
    retornos = []
    for onda_da_derrota in (1, 6, 12):
        env = AmbienteMonstervale("level_01")
        env.reset()
        env.sim._proxima_onda = onda_da_derrota - 1
        env.sim.vidas = 1
        _, r, terminou, *_ = env.step(ACAO_CHAMAR)
        assert terminou and env.sim.estado == "lost" and env.sim.ondas_iniciadas() == onda_da_derrota
        retornos.append(r)
    assert retornos[0] < retornos[1] < retornos[2]
    assert retornos[2] == pytest.approx(-1 / 20 - 1 / 12)


def test_peso_da_derrota_escala_a_derrota_graduada():
    _, retorno, _ = _perder_sem_construir("level_01", recompensas=Recompensas(derrota=-3.0))
    assert retorno == pytest.approx(-1.0 - 3.0 * 10 / 12)


def test_vitoria_inalterada_pela_derrota_graduada():
    # A recompensa da vitória não depende de derrota: vidas perdidas + vitória + estrelas.
    env = AmbienteMonstervale("level_01")
    resumo = jogar(env, heuristico())
    if resumo["estado"] != "won":
        pytest.skip("o heurístico não vence a level_01 neste commit")
    r = Recompensas()
    esperado = -(20 - resumo["vidas"]) / 20 + r.vitoria + r.por_estrela * resumo["estrelas"]
    assert resumo["retorno"] == pytest.approx(esperado)


def test_construir_nao_passa_tempo_nem_da_recompensa():
    env = AmbienteMonstervale("level_01")
    env.reset()
    _, recompensa, terminou, _, info = env.step(indice_acao(0, *env.mapa.celulas_junto_a_estrada()[0]))
    assert (recompensa, terminou, info["quadro"]) == (0.0, False, 0)


# --- Determinismo e exportação ---------------------------------------------------------------

def test_mesmo_historico_mesma_partida():
    a = AmbienteMonstervale("level_05")
    jogar(a, heuristico())
    b = AmbienteMonstervale("level_05")
    b.reset()
    for _, acao in a.historico:
        b.step(acao)
    assert (b.sim.estado, b.sim.vidas, b.sim.ouro, b.quadro) == (a.sim.estado, a.sim.vidas, a.sim.ouro, a.quadro)


HISTORICOS = json.loads((REF / "agente_historicos.json").read_text(encoding="utf-8"))
REPETIDAS = json.loads((REF / "agente.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("nome", sorted(HISTORICOS))
def test_partida_exportada_e_repetida_igual_no_jogo(nome):
    """O relatório gravado pelo ambiente, repetido no Monstervale pelo jogador
    gravado do jogo (ferramentas/capturar_partidas.gd), termina igual."""
    nosso, jogo = HISTORICOS[nome], REPETIDAS[nome]
    assert jogo["failed_clicks"] == []
    assert (jogo["state"], jogo["lives"], jogo["gold"]) == (nosso["estado"], nosso["vidas"], nosso["ouro"])
    assert jogo["frames"] == nosso["quadro"]


@pytest.mark.lento
@pytest.mark.parametrize("nome", sorted(REPETIDAS))
def test_repeticao_no_jogo_bate_quadro_a_quadro_com_a_partida_do_ambiente(nome):
    """A partida do ambiente (histórico → roteiro) e a repetição no Monstervale
    passam pelos mesmos estados, quadro a quadro."""
    jogo, nosso = REPETIDAS[nome], HISTORICOS[nome]
    catalogo = carregar_catalogo()
    sim = Simulacao(catalogo, carregar_fase(nosso["level"]))
    sim.registrar_eventos = False
    obtido = executar(sim, nosso["roteiro"], sorted(catalogo["monsters"]), jogo["frames"])
    assert all(obtido["results"])
    assert obtido["prints"] == jogo["prints"]
