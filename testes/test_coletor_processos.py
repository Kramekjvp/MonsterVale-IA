"""Robustez do coletor assíncrono: filhos sem torch e erro rápido (em vez de travar) quando um filho morre."""

import functools
import subprocess
import sys
from pathlib import Path
import time

import pytest
import torch

from monstervale_ia import mini_td as mt
from monstervale_ia.ppo import ColetorAssincrono, criar_rede
from ambientes_falsos import FalhaNoPasso, MorreNoPasso, fabrica_que_levanta, fabrica_que_morre

RAIZ = Path(__file__).resolve().parent.parent
LIMITE = 60.0  # segundos; só para o teste nunca travar a suíte (o esperado é falhar em poucos segundos)


def _buffers(T, N, amostra):
    espaco = amostra.observation_space
    return dict(
        grids=torch.zeros((T, N, *espaco["grid"].shape)),
        globais=torch.zeros((T, N, *espaco["global"].shape)),
        mascaras=torch.zeros((T, N, amostra.action_space.n), dtype=torch.bool),
        acoes=torch.zeros((T, N), dtype=torch.long),
        logprobs=torch.zeros((T, N)),
        recompensas=torch.zeros((T, N)).numpy(),
        terminados=torch.zeros((T, N)).numpy(),
        valores=torch.zeros((T, N)).numpy(),
    )


def _coletar(coletor, T, N):
    amostra = mt.MiniTD()
    rede = criar_rede(amostra, mt.TIPOS_POR_CELULA, largura=8, camadas=1, oculta=8)
    b = _buffers(T, N, amostra)
    return coletor.coletar(rede, T, b["grids"], b["globais"], b["mascaras"], b["acoes"], b["logprobs"],
                           b["recompensas"], b["terminados"], b["valores"], torch.device("cpu"))


def test_filhos_nao_importam_torch():
    coletor = ColetorAssincrono(mt.MiniTD, 2, semente=1)
    try:
        assert len(coletor.diagnosticos) == 2
        assert all(d["torch_importado"] is False for d in coletor.diagnosticos)
    finally:
        coletor.fechar()


def test_filho_que_morre_no_meio_da_coleta_levanta_erro_rapido():
    coletor = ColetorAssincrono(functools.partial(MorreNoPasso, 3), 2, semente=1)
    inicio = time.monotonic()
    try:
        with pytest.raises(RuntimeError, match=r"ambiente \d.*morreu.*código de saída 3"):
            _coletar(coletor, 10, 2)
    finally:
        coletor.fechar()
    assert time.monotonic() - inicio < LIMITE


def test_excecao_no_step_do_filho_chega_ao_principal():
    coletor = ColetorAssincrono(FalhaNoPasso, 2, semente=1)
    try:
        with pytest.raises(RuntimeError, match="falha de mentira no step"):
            _coletar(coletor, 4, 2)
    finally:
        coletor.fechar()


def test_excecao_na_criacao_do_ambiente_levanta_erro_rapido():
    inicio = time.monotonic()
    with pytest.raises(RuntimeError, match="falha de mentira na criação"):
        ColetorAssincrono(fabrica_que_levanta, 2, semente=1)
    assert time.monotonic() - inicio < LIMITE


def test_filho_que_morre_na_inicializacao_levanta_erro_rapido():
    inicio = time.monotonic()
    with pytest.raises(RuntimeError, match=r"morreu na inicialização.*código de saída 5"):
        ColetorAssincrono(fabrica_que_morre, 2, semente=1)
    assert time.monotonic() - inicio < LIMITE


def test_inicializacao_lenta_estoura_o_tempo_configurado():
    with pytest.raises(TimeoutError, match="não ficou pronto"):
        ColetorAssincrono(mt.MiniTD, 1, semente=1, tempo_inicializacao=0.0)


def test_filho_com_o_ambiente_monstervale_nao_importa_torch():
    from monstervale_ia.ambiente import AmbienteMonstervale

    coletor = ColetorAssincrono(functools.partial(AmbienteMonstervale, "level_01"), 1, semente=1)
    try:
        assert coletor.diagnosticos[0]["torch_importado"] is False
    finally:
        coletor.fechar()


@pytest.mark.parametrize("script", ["treinar_fase", "treinar_mini_td"])
def test_topo_dos_scripts_de_treino_nao_importa_torch(script):
    """O spawn executa o topo do script principal em cada filho: ele não pode puxar o torch."""
    codigo = (
        "import runpy, sys\n"
        f"runpy.run_path(r'{RAIZ / 'ferramentas' / (script + '.py')}', run_name='__mp_main__')\n"
        "assert 'torch' not in sys.modules, 'o topo do script importou o torch'\n"
    )
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
