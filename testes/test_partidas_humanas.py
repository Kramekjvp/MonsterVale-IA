"""As 42 partidas humanas gravadas, repetidas no Python, iguais ao jogo.

ferramentas/capturar_partidas.gd repete cada partida com o jogador gravado do
próprio jogo (clicando na interface real) e anota as ações que chegaram à
simulação, quadro a quadro, mais as impressões digitais do estado. Aqui o
Python aplica as mesmas ações e precisa chegar aos mesmos estados.

As partidas aprovadas por quem dirige o jogo também precisam terminar como no
relatório original (é o que os testes e2e do jogo exigem).
"""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.lento

from monstervale_ia.dados_jogo import carregar_catalogo, carregar_fase
from monstervale_ia.roteiro import executar
from monstervale_ia.simulacao import Simulacao

PARTIDAS = json.loads((Path(__file__).parent / "referencias" / "partidas.json").read_text(encoding="utf-8"))
CATALOGO = carregar_catalogo()
TIPOS = sorted(CATALOGO["monsters"])

# As que jogo/tests/e2e/test_recorded_matches.gd exige que se repitam exatamente.
APROVADAS = [
    "partida_2026-11-06_13-21-26_level_01.json",
    "partida_2026-11-06_17-02-07_level_02.json",
    "partida_2026-11-06_21-21-02_level_03.json",
    "partida_2026-11-06_20-23-07_level_03.json",
]


def _repetir(nome: str) -> tuple[Simulacao, dict]:
    p = PARTIDAS[nome]
    sim = Simulacao(CATALOGO, carregar_fase(p["level"]))
    sim.registrar_eventos = False
    return sim, executar(sim, p["actions"], TIPOS, p["frames"])


@pytest.mark.parametrize("nome", sorted(PARTIDAS))
def test_partida_humana_igual_ao_jogo(nome):
    esperado = PARTIDAS[nome]
    sim, obtido = _repetir(nome)
    for o, e in zip(obtido["prints"], esperado["prints"]):
        assert o == e, f"diverge no quadro {e[0]}: python {o[:4]} × godot {e[:4]}"
    assert len(obtido["prints"]) == len(esperado["prints"])
    assert all(obtido["results"]), "alguma ação que funcionou no jogo falhou no Python"
    assert (sim.estado, sim.vidas, sim.ouro) == (esperado["state"], esperado["lives"], esperado["gold"])


@pytest.mark.parametrize("nome", APROVADAS)
def test_partida_aprovada_termina_como_o_relatorio_original(nome):
    gravado = PARTIDAS[nome]["recorded"]
    sim, _ = _repetir(nome)
    assert sim.estado == gravado["result"]
    assert sim.vidas == gravado["lives_final"]
    assert sim.ouro == gravado["gold_final"]
