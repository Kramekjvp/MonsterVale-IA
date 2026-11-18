"""PPO, rede e mini-TD (M5)."""

import functools
import json

import numpy as np
import pytest
import torch

from monstervale_ia import ambiente as amb
from monstervale_ia import mini_td as mt
from monstervale_ia.ppo import ColetorAssincrono, ConfigPPO, criar_rede, escolher, treinar, vantagens_gae
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


# --- Coletor assíncrono e checkpoints (M6) --------------------------------------------

REDE_PEQUENA = {"largura": 8, "camadas": 1, "oculta": 8}


def _config_mini(tmp_path, **extra) -> ConfigPPO:
    base = dict(n_ambientes=3, passos_por_coleta=16, semente=1, pasta=str(tmp_path), rede=REDE_PEQUENA,
                dispositivo="cpu")
    base.update(extra)
    return ConfigPPO(**base)


def test_coletor_assincrono_enche_t_passos_por_ambiente():
    T, N = 20, 3
    amostra = mt.MiniTD()
    rede = criar_rede(amostra, mt.TIPOS_POR_CELULA, **REDE_PEQUENA)
    espaco, n_acoes = amostra.observation_space, amostra.action_space.n
    grids = torch.zeros((T, N, *espaco["grid"].shape))
    globais = torch.zeros((T, N, *espaco["global"].shape))
    mascaras = torch.zeros((T, N, n_acoes), dtype=torch.bool)
    acoes = torch.zeros((T, N), dtype=torch.long)
    logprobs = torch.zeros((T, N))
    recompensas = np.zeros((T, N), dtype=np.float32)
    terminados = np.zeros((T, N), dtype=np.float32)
    valores = np.zeros((T, N), dtype=np.float32)
    coletor = ColetorAssincrono(mt.MiniTD, N, semente=5)
    try:
        for _ in range(2):  # a segunda coleta continua de onde a primeira parou
            terminados[:] = 0
            mascaras[:] = False
            partidas = coletor.coletar(
                rede, T, grids, globais, mascaras, acoes, logprobs, recompensas, terminados, valores,
                torch.device("cpu"),
            )
            # todas as posições [T, N] foram escritas (máscara com ao menos uma ação) e a ação sorteada é permitida
            assert mascaras.any(-1).all()
            assert mascaras.gather(2, acoes[..., None]).all()
            assert (logprobs <= 0).all()
            assert len(partidas) == int(terminados.sum())
    finally:
        coletor.fechar()
    assert not coletor.processos


def test_treino_assincrono_roda_no_mini_td(tmp_path):
    config = _config_mini(tmp_path, assincrono=True, total_passos=3 * 3 * 16)
    _, historico = treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, config)
    assert [h["atualizacao"] for h in historico] == [1, 2, 3]
    assert historico[-1]["passo"] == 3 * 3 * 16
    assert (tmp_path / "rede.pt").exists() and (tmp_path / "checkpoint.pt").exists()


@pytest.mark.lento
def test_treino_assincrono_roda_no_ambiente_monstervale(tmp_path):
    config = _config_mini(tmp_path, n_ambientes=2, passos_por_coleta=8, assincrono=True, total_passos=2 * 8)
    _, historico = treinar(functools.partial(amb.AmbienteMonstervale, "level_01"), 9, config)
    assert len(historico) == 1 and np.isfinite(historico[0]["perda_valor"])


def test_retomada_continua_da_atualizacao_certa(tmp_path):
    lote = 3 * 16
    def queda(rede, passo):
        raise KeyboardInterrupt  # derruba o treino na atualização 3

    primeira = _config_mini(tmp_path, total_passos=4 * lote, salvar_a_cada=1, avaliar_a_cada=3)
    with pytest.raises(KeyboardInterrupt):
        treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, primeira, avaliacao=queda)
    assert torch.load(tmp_path / "checkpoint.pt", weights_only=False)["atualizacao"] == 2
    config = _config_mini(tmp_path, total_passos=4 * lote, retomar=True)
    _, historico = treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, config)
    assert [h["atualizacao"] for h in historico] == [3, 4]
    assert historico[0]["passo"] == 3 * lote
    assert historico[0]["taxa"] == pytest.approx(0.5 * config.taxa_aprendizado)  # anelamento continua
    linhas = (tmp_path / "metricas.csv").read_text(encoding="utf-8").splitlines()
    assert linhas.count("passo,nome,valor") == 1
    assert any(linha.startswith(f"{2 * lote},") for linha in linhas)  # o histórico anterior continua lá


def test_checkpoint_periodico(tmp_path):
    lote = 3 * 16
    treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, _config_mini(tmp_path, total_passos=3 * lote, salvar_a_cada=1))
    assert torch.load(tmp_path / "checkpoint.pt", weights_only=False)["atualizacao"] == 3


def test_grava_a_melhor_rede(tmp_path):
    retornos = iter([1.0, 3.0, 2.0])
    config = _config_mini(tmp_path, total_passos=3 * 3 * 16, avaliar_a_cada=1, chave_melhor="retorno")
    treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, config, avaliacao=lambda rede, passo: {"retorno": next(retornos)})
    salvo = torch.load(tmp_path / "melhor_rede.pt", weights_only=False)
    assert set(salvo) == {"rede", "config"}
    rede = criar_rede(mt.MiniTD(), mt.TIPOS_POR_CELULA, **salvo["config"]["rede"])
    rede.load_state_dict(salvo["rede"])
    assert torch.load(tmp_path / "checkpoint.pt", weights_only=False)["melhor"] == 3.0


def test_retomar_com_config_diferente_levanta_erro(tmp_path):
    lote = 3 * 16
    treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, _config_mini(tmp_path, total_passos=2 * lote))
    config = _config_mini(tmp_path, total_passos=3 * lote, n_ambientes=4, retomar=True)
    with pytest.raises(ValueError) as erro:
        treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, config)
    mensagem = str(erro.value)
    assert f"total_passos: salvo {2 * lote} x atual {3 * lote}" in mensagem
    assert "n_ambientes: salvo 3 x atual 4" in mensagem
    assert "passos_por_coleta" not in mensagem


def test_retomada_parte_do_melhor_valor_real(tmp_path):
    lote = 3 * 16

    def queda(rede, passo):  # a 1ª avaliação melhora; a 2ª derruba o treino
        if passo == lote:
            return {"retorno": 5.0}
        raise KeyboardInterrupt

    config = _config_mini(tmp_path, total_passos=4 * lote, avaliar_a_cada=1, chave_melhor="retorno", salvar_a_cada=3)
    with pytest.raises(KeyboardInterrupt):
        treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, config, avaliacao=queda)
    # a atualização 1 não é múltiplo de salvar_a_cada, mas o checkpoint já guarda o melhor valor
    assert torch.load(tmp_path / "checkpoint.pt", weights_only=False)["melhor"] == 5.0
    antes = torch.load(tmp_path / "melhor_rede.pt", weights_only=False)["rede"]
    config = _config_mini(tmp_path, total_passos=4 * lote, avaliar_a_cada=1, chave_melhor="retorno",
                          salvar_a_cada=3, retomar=True)
    treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, config, avaliacao=lambda rede, passo: {"retorno": 2.0})
    depois = torch.load(tmp_path / "melhor_rede.pt", weights_only=False)["rede"]
    assert all(torch.equal(antes[k], depois[k]) for k in antes)  # a rede pior não sobrescreveu


# --- Janela de partidas, melhor rede por métrica, parada, rede inicial (M8) -----------


def _estrelas_da_partida(n: int) -> int:
    """Estrelas da n-ésima partida terminada (n = 1, 2, ...) de um ambiente: 3, 2, 1, 0, 3, 2, 1, 0, ..."""
    return (n * 7) % 4


class _FimRapido(mt.MiniTD):
    """Mini-TD que expõe `estrelas` variadas (ciclo 3, 2, 1, 0 por ambiente) para exercitar a janela."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.terminadas = 0

    def step(self, acao):
        obs, r, term, trunc, info = super().step(acao)
        info = dict(info)
        if term or trunc:
            self.terminadas += 1
        info["estrelas"] = _estrelas_da_partida(max(1, self.terminadas))
        return obs, r, term, trunc, info


def _config_janela(tmp_path, **extra) -> ConfigPPO:
    base = dict(total_passos=4 * 3 * 16, janela_partidas=2)
    base.update(extra)
    return _config_mini(tmp_path, **base)


def _sequencia_de_estrelas(n: int) -> list[int]:
    return [_estrelas_da_partida(k) for k in range(1, n + 1)]


def _confere_fracao_da_janela(historico, K, anteriores=()):
    """Com UM ambiente a ordem das partidas é a do ciclo de estrelas: confere, atualização a
    atualização, a fração de 3 estrelas e de vitórias nas últimas K partidas terminadas."""
    terminadas = list(anteriores)
    novas = 0  # partidas já terminadas pelo ambiente atual
    conferidas = 0
    for h in historico:
        novas += int(h.get("partidas", 0))
        terminadas = list(anteriores) + _sequencia_de_estrelas(novas)
        if len(terminadas) < K:
            assert "janela/tres_estrelas" not in h
            continue
        ultimas = terminadas[-K:]
        assert h["janela/tres_estrelas"] == pytest.approx(sum(e == 3 for e in ultimas) / K)
        assert h["janela/vitorias"] == pytest.approx(sum(e >= 1 for e in ultimas) / K)
        conferidas += 1
    return conferidas


@pytest.mark.parametrize("assincrono", [False, True])
def test_fracao_da_janela_conta_as_ultimas_k_partidas(tmp_path, assincrono):
    config = _config_janela(tmp_path, n_ambientes=1, total_passos=8 * 16, janela_partidas=5, assincrono=assincrono)
    _, historico = treinar(_FimRapido, mt.TIPOS_POR_CELULA, config)
    assert sum(h.get("partidas", 0) for h in historico) > 10
    assert _confere_fracao_da_janela(historico, 5) >= 3
    # as frações não são triviais: a janela mistura partidas de 0 a 3 estrelas
    assert len({h["janela/tres_estrelas"] for h in historico if "janela/tres_estrelas" in h}) > 1


def test_janela_so_aparece_cheia(tmp_path):
    _, historico = treinar(_FimRapido, mt.TIPOS_POR_CELULA, _config_janela(tmp_path))
    com_janela = [h for h in historico if "janela/tres_estrelas" in h]
    assert com_janela, "a janela de 2 partidas devia encher"
    primeira = com_janela[0]
    assert all("janela/tres_estrelas" not in h for h in historico[:historico.index(primeira)])
    assert 0.0 <= primeira["janela/tres_estrelas"] <= primeira["janela/vitorias"] <= 1.0
    # janela grande demais nunca enche
    _, historico = treinar(_FimRapido, mt.TIPOS_POR_CELULA, _config_janela(tmp_path / "b", janela_partidas=10_000))
    assert all("janela/tres_estrelas" not in h for h in historico)


def test_sem_estrelas_nao_ha_janela(tmp_path):
    _, historico = treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, _config_janela(tmp_path))
    assert all("janela/tres_estrelas" not in h for h in historico)


def test_melhor_rede_por_metrica_da_janela(tmp_path):
    config = _config_janela(tmp_path, chave_melhor="janela/tres_estrelas")
    _, historico = treinar(_FimRapido, mt.TIPOS_POR_CELULA, config)
    assert (tmp_path / "melhor_rede.pt").exists()
    valores = [h["janela/tres_estrelas"] for h in historico if "janela/tres_estrelas" in h]
    assert torch.load(tmp_path / "checkpoint.pt", weights_only=False)["melhor"] == max(valores)
    recordes = sum(v > max(valores[:i], default=-1.0) for i, v in enumerate(valores))
    assert sum("avaliacao/melhor" in h for h in historico) == recordes  # estritamente maior: empate não grava


def test_chave_com_prefixo_avaliacao_equivale_a_sem_prefixo(tmp_path):
    retornos = iter([1.0, 3.0, 2.0])
    config = _config_mini(tmp_path, total_passos=3 * 3 * 16, avaliar_a_cada=1, chave_melhor="avaliacao/retorno")
    treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, config, avaliacao=lambda rede, passo: {"retorno": next(retornos)})
    assert torch.load(tmp_path / "checkpoint.pt", weights_only=False)["melhor"] == 3.0


def test_parada_antecipada(tmp_path):
    lote = 3 * 16
    estrelas = iter([1.0, 2.0, 3.0, 3.0, 3.0, 3.0])
    config = _config_mini(
        tmp_path, total_passos=6 * lote, avaliar_a_cada=1,
        criterio_parada={"avaliacao/estrelas": 3, "avaliacao/retorno": 0.5},
    )
    _, historico = treinar(
        mt.MiniTD, mt.TIPOS_POR_CELULA, config,
        avaliacao=lambda rede, passo: {"estrelas": next(estrelas), "retorno": 1.0},
    )
    assert [h["atualizacao"] for h in historico] == [1, 2, 3]
    assert historico[-1]["parou_cedo"] == 1.0 and "parou_cedo" not in historico[0]
    assert (tmp_path / "rede.pt").exists()
    assert torch.load(tmp_path / "checkpoint.pt", weights_only=False)["atualizacao"] == 3
    salvo = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert salvo["criterio_parada"]["avaliacao/estrelas"] == 3


def test_rede_inicial_carrega_pesos_e_rejeita_arquitetura_diferente(tmp_path):
    lote = 3 * 16
    origem = tmp_path / "origem"
    treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, _config_mini(origem, total_passos=2 * lote))
    salvo = torch.load(origem / "rede.pt", weights_only=False)["rede"]
    # taxa 0: depois de 1 atualização os pesos continuam os da rede inicial
    config = _config_mini(tmp_path / "novo", total_passos=lote, taxa_aprendizado=0.0, anelar_taxa=False,
                          rede_inicial=str(origem / "rede.pt"))
    rede, _ = treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, config)
    assert all(torch.equal(salvo[k], v) for k, v in rede.state_dict().items())
    outra = _config_mini(tmp_path / "outra", total_passos=lote, rede_inicial=str(origem / "rede.pt"),
                         rede={"largura": 16, "camadas": 1, "oculta": 8})
    with pytest.raises(ValueError, match="arquitetura"):
        treinar(mt.MiniTD, mt.TIPOS_POR_CELULA, outra)


def test_retomada_preserva_a_janela(tmp_path):
    def queda(rede, passo):
        raise KeyboardInterrupt

    K = 5  # maior que as partidas de UMA atualização, menor que as de antes da queda
    comum = dict(n_ambientes=1, janela_partidas=K, total_passos=8 * 16)
    primeira = _config_janela(tmp_path, salvar_a_cada=1, avaliar_a_cada=4, **comum)
    with pytest.raises(KeyboardInterrupt):
        treinar(_FimRapido, mt.TIPOS_POR_CELULA, primeira, avaliacao=queda)
    janela = torch.load(tmp_path / "checkpoint.pt", weights_only=False)["janela"]
    assert len(janela) == K
    antigas = [int(p["estrelas"]) for p in janela]
    _, historico = treinar(_FimRapido, mt.TIPOS_POR_CELULA, _config_janela(tmp_path, retomar=True, **comum))
    assert historico[0]["atualizacao"] == 4
    # a 1ª atualização retomada tem menos de K partidas novas: a métrica só existe e só tem o
    # valor certo se a janela do checkpoint foi lida (o ciclo de estrelas reinicia no novo ambiente)
    assert historico[0].get("partidas", 0) < K
    assert "janela/tres_estrelas" in historico[0]
    assert _confere_fracao_da_janela(historico, K, anteriores=antigas) == len(historico)
