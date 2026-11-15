"""Simulação: paridade quadro a quadro com a simulação original do Godot.

Os roteiros (testes/referencias/roteiros_entrada.json) são executados no Godot
por ferramentas/executar_roteiro.gd, que grava as impressões digitais em
testes/referencias/roteiros.json. Aqui o Python executa os mesmos roteiros.
"""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.lento

from monstervale_ia.dados_jogo import carregar_catalogo, carregar_fase
from monstervale_ia.roteiro import executar

PASTA = Path(__file__).parent / "referencias"
ENTRADA = json.loads((PASTA / "roteiros_entrada.json").read_text(encoding="utf-8"))
ESPERADO = json.loads((PASTA / "roteiros.json").read_text(encoding="utf-8"))
CATALOGO = carregar_catalogo()
TIPOS = sorted(CATALOGO["monsters"])


@pytest.mark.parametrize("nome", list(ENTRADA))
def test_roteiro_igual_ao_godot_quadro_a_quadro(nome):
    spec = ENTRADA[nome]
    from monstervale_ia.simulacao import Simulacao

    sim = Simulacao(CATALOGO, carregar_fase(spec["level"]))
    obtido = executar(sim, spec["actions"], TIPOS, spec["frames"], spec.get("invincible", False))
    esperado = ESPERADO[nome]

    # Primeira divergência, com contexto, em vez de uma lista enorme de diferenças.
    for o, e in zip(obtido["prints"], esperado["prints"]):
        assert o == e, f"diverge no quadro {e[0]}: python {o[:4]} × godot {e[:4]}"
    assert len(obtido["prints"]) == len(esperado["prints"])
    assert obtido["results"] == esperado["results"][: len(obtido["results"])]
    assert obtido["state"] == esperado["state"]
