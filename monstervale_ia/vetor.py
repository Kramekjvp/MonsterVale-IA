"""Aritmética de vetores 2D idêntica à do Godot.

No Godot, ``Vector2`` guarda x e y em float32 (``real_t``), e cada operação
arredonda para float32. Já o ``float`` do GDScript é de 64 bits. As funções
abaixo copiam o código C++ do Godot (core/math/vector2.cpp) operação por
operação, com ``np.float32``, para que o Python chegue nos mesmos bits.

Um vetor aqui é só uma tupla ``(x, y)`` de ``np.float32``.
"""

from __future__ import annotations

import math

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


def somar(a: Vetor, b: Vetor) -> Vetor:
    return a[0] + b[0], a[1] + b[1]


def subtrair(a: Vetor, b: Vetor) -> Vetor:
    return a[0] - b[0], a[1] - b[1]


def escalar(v: Vetor, k: float) -> Vetor:
    """Vector2 * real_t: o escalar vira float32 antes de multiplicar."""
    k = f32(k)
    return v[0] * k, v[1] * k


def direcao_para(de: Vetor, para: Vetor) -> Vetor:
    """Vector2::direction_to(): vetor unitário de `de` até `para` (normalize())."""
    x = para[0] - de[0]
    y = para[1] - de[1]
    q = x * x + y * y  # length_squared
    if q == 0:
        return f32(0.0), f32(0.0)
    tamanho = np.sqrt(q)
    return x / tamanho, y / tamanho


def ponto_mais_proximo_do_segmento(p: Vetor, a: Vetor, b: Vetor) -> Vetor:
    """Geometry2D.get_closest_point_to_segment(), core/math/geometry_2d.h."""
    px, py = p[0] - a[0], p[1] - a[1]
    nx, ny = b[0] - a[0], b[1] - a[1]
    l2 = nx * nx + ny * ny
    if l2 < f32(1e-20):
        return a
    d = (nx * px + ny * py) / l2
    if d <= f32(0.0):
        return a
    if d >= f32(1.0):
        return b
    return a[0] + nx * d, a[1] + ny * d


# Margem do pré-filtro em float64. No mapa do jogo (coordenadas até ~700 px), o
# erro do float32 numa distância fica abaixo de ~3e-4 px; com 1e-3 de folga, o
# resultado em float64 só decide quando é impossível o float32 discordar.
MARGEM_PREFILTRO = 1e-3


def distancia_aprox(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distância em float64 (rápida, NÃO idêntica ao Godot): só para pré-filtrar."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def dentro_do_raio(a: Vetor, af: tuple[float, float], b: Vetor, bf: tuple[float, float], raio: float) -> bool:
    """distancia(a, b) <= raio, com o mesmo resultado do Godot, mas rápido.

    `af`/`bf` são as mesmas posições como float do Python. Só calcula em float32
    quando a distância cai a menos de MARGEM_PREFILTRO da borda.
    """
    d = distancia_aprox(af, bf)
    if d < raio - MARGEM_PREFILTRO:
        return True
    if d > raio + MARGEM_PREFILTRO:
        return False
    return float(distancia(a, b)) <= raio
