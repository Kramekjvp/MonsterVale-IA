"""O port do introsort do Godot deixa os empates na mesma ordem que o jogo."""

import json
from pathlib import Path

from monstervale_ia.godot import ordenar_como_godot

CASOS = json.loads((Path(__file__).parent / "referencias" / "ordenacao.json").read_text())


def _menor(a, b):
    return a[0] < b[0]


def test_ordenacao_igual_ao_godot_com_empates():
    for caso in CASOS:
        itens = [list(x) for x in caso["input"]]
        ordenar_como_godot(itens, _menor)
        assert [int(x[1]) for x in itens] == [int(i) for i in caso["output"]], len(itens)


def test_sorted_do_python_seria_diferente():
    # A prova de que o port era necessário: com empates em listas grandes,
    # a ordenação estável do Python diverge do Godot.
    diferentes = 0
    for caso in CASOS:
        estavel = [int(x[1]) for x in sorted(caso["input"], key=lambda x: x[0])]
        diferentes += estavel != [int(i) for i in caso["output"]]
    assert diferentes > 0
