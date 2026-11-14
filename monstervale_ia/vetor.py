"""Aritmética de vetores 2D idêntica à do Godot.

No Godot, ``Vector2`` guarda x e y em float32 (``real_t``), e cada operação
arredonda para float32. Já o ``float`` do GDScript é de 64 bits. As funções
abaixo copiam o código C++ do Godot (core/math/vector2.cpp) operação por
operação, com ``np.float32``, para que o Python chegue nos mesmos bits.

Um vetor aqui é só uma tupla ``(x, y)`` de ``np.float32``.
"""

from __future__ import annotations

import numpy as np

f32 = np.float32
Vetor = tuple[np.float32, np.float32]

# Godot: core/math/math_defs.h
CMP_EPSILON = f32(0.00001)


def vetor(x: float, y: float) -> Vetor:
    return f32(x), f32(y)


def comprimento(v: Vetor) -> np.float32:
    """Vector2::length(): sqrt(x*x + y*y), tudo em float32."""
    x, y = v
    return np.sqrt(x * x + y * y)


def distancia(a: Vetor, b: Vetor) -> np.float32:
    """Vector2::distance_to(): sqrt((ax-bx)² + (ay-by)²) em float32."""
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return np.sqrt(dx * dx + dy * dy)


def mover_em_direcao(de: Vetor, para: Vetor, passo: float) -> Vetor:
    """Vector2::move_toward(): anda `passo` pixels de `de` até `para`, sem passar.

    O parâmetro chega ao C++ como real_t, então `passo` vira float32 antes da conta.
    """
    passo = f32(passo)
    vd = (para[0] - de[0], para[1] - de[1])
    tamanho = comprimento(vd)
    if tamanho <= passo or tamanho < CMP_EPSILON:
        return para
    # v + vd / len * p_delta, componente a componente, na ordem do C++
    return (
        de[0] + vd[0] / tamanho * passo,
        de[1] + vd[1] / tamanho * passo,
    )
