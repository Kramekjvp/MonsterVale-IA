"""Funções numéricas do GDScript com o mesmo comportamento do Godot.

Os nomes seguem o GDScript para ficar fácil comparar com o código original.
"""

from __future__ import annotations

import math


def roundi(x: float) -> int:
    """roundi(): arredonda o .5 para LONGE do zero (2.5 → 3, -2.5 → -3).

    Atenção: o round() do Python arredonda o .5 para o PAR mais próximo
    (2.5 → 2, 3.5 → 4). Usar round() aqui mudaria o dano em vários golpes.
    """
    # Não use floor(x + 0.5): para x = 0.49999999999999994 a soma já arredonda
    # para 1.0. Separar a parte inteira deixa a comparação exata, como std::round.
    inteiro = math.floor(abs(x))
    if abs(x) - inteiro >= 0.5:
        inteiro += 1
    return int(math.copysign(inteiro, x))


def maxi(a: int, b: int) -> int:
    return a if a > b else b


def mini(a: int, b: int) -> int:
    return a if a < b else b


def maxf(a: float, b: float) -> float:
    return a if a > b else b


def div_int(a: int, b: int) -> int:
    """Divisão de inteiros do GDScript: trunca em direção ao zero (como em C)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q
