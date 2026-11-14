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


# --- Array.sort_custom() --------------------------------------------------------
# O Godot ordena com introsort (core/templates/sort_array.h), que NÃO é estável:
# elementos "empatados" podem trocar de ordem. O sorted() do Python é estável.
# Para empates saírem na mesma ordem do jogo, este é um port linha a linha.

_LIMIAR_INTROSORT = 16


def ordenar_como_godot(lista: list, menor) -> None:
    """Ordena `lista` no lugar, como Array.sort_custom(menor) do Godot 4.7."""
    n = len(lista)
    if n:
        _introsort(lista, 0, n, _bitlog(n) * 2, menor)
        _insercao_final(lista, 0, n, menor)


def _bitlog(n: int) -> int:
    k = 0
    while n != 1:
        n >>= 1
        k += 1
    return k


def _mediana_de_3(v, a, b, c, menor) -> int:
    if menor(v[a], v[b]):
        if menor(v[b], v[c]):
            return b
        if menor(v[a], v[c]):
            return c
        return a
    if menor(v[a], v[c]):
        return a
    if menor(v[b], v[c]):
        return c
    return b


def _particionar(v, primeiro, ultimo, pivo, menor) -> int:
    while True:
        while primeiro != pivo and menor(v[primeiro], v[pivo]):
            primeiro += 1
        ultimo -= 1
        while ultimo != pivo and menor(v[pivo], v[ultimo]):
            ultimo -= 1
        if primeiro >= ultimo:
            return primeiro
        # O C++ guarda um ponteiro para o pivô; se ele vai ser trocado, o ponteiro o segue.
        if pivo == primeiro:
            pivo = ultimo
        elif pivo == ultimo:
            pivo = primeiro
        v[primeiro], v[ultimo] = v[ultimo], v[primeiro]
        primeiro += 1


def _introsort(v, primeiro, ultimo, profundidade, menor) -> None:
    while ultimo - primeiro > _LIMIAR_INTROSORT:
        if profundidade == 0:
            _ordenacao_parcial(v, primeiro, ultimo, ultimo, menor)
            return
        profundidade -= 1
        meio = primeiro + (ultimo - primeiro) // 2
        corte = _particionar(v, primeiro, ultimo, _mediana_de_3(v, primeiro, meio, ultimo - 1, menor), menor)
        _introsort(v, corte, ultimo, profundidade, menor)
        ultimo = corte


def _insercao_sem_guarda(v, ultimo, valor, menor) -> None:
    proximo = ultimo - 1
    while menor(valor, v[proximo]):
        v[ultimo] = v[proximo]
        ultimo = proximo
        proximo -= 1
    v[ultimo] = valor


def _insercao_linear(v, primeiro, ultimo, menor) -> None:
    valor = v[ultimo]
    if menor(valor, v[primeiro]):
        for i in range(ultimo, primeiro, -1):
            v[i] = v[i - 1]
        v[primeiro] = valor
    else:
        _insercao_sem_guarda(v, ultimo, valor, menor)


def _ordenacao_por_insercao(v, primeiro, ultimo, menor) -> None:
    if primeiro == ultimo:
        return
    for i in range(primeiro + 1, ultimo):
        _insercao_linear(v, primeiro, i, menor)


def _insercao_final(v, primeiro, ultimo, menor) -> None:
    if ultimo - primeiro > _LIMIAR_INTROSORT:
        _ordenacao_por_insercao(v, primeiro, primeiro + _LIMIAR_INTROSORT, menor)
        for i in range(primeiro + _LIMIAR_INTROSORT, ultimo):
            _insercao_sem_guarda(v, i, v[i], menor)
    else:
        _ordenacao_por_insercao(v, primeiro, ultimo, menor)


# Heapsort, usado só quando o introsort passa da profundidade máxima.

def _empurrar_heap(v, primeiro, buraco, topo, valor, menor) -> None:
    pai = (buraco - 1) // 2
    while buraco > topo and menor(v[primeiro + pai], valor):
        v[primeiro + buraco] = v[primeiro + pai]
        buraco = pai
        pai = (buraco - 1) // 2
    v[primeiro + buraco] = valor


def _ajustar_heap(v, primeiro, buraco, tamanho, valor, menor) -> None:
    topo = buraco
    filho = 2 * buraco + 2
    while filho < tamanho:
        if menor(v[primeiro + filho], v[primeiro + (filho - 1)]):
            filho -= 1
        v[primeiro + buraco] = v[primeiro + filho]
        buraco = filho
        filho = 2 * (filho + 1)
    if filho == tamanho:
        v[primeiro + buraco] = v[primeiro + (filho - 1)]
        buraco = filho - 1
    _empurrar_heap(v, primeiro, buraco, topo, valor, menor)


def _tirar_do_heap(v, primeiro, ultimo, resultado, valor, menor) -> None:
    v[resultado] = v[primeiro]
    _ajustar_heap(v, primeiro, 0, ultimo - primeiro, valor, menor)


def _ordenacao_parcial(v, primeiro, ultimo, meio, menor) -> None:
    tamanho = meio - primeiro
    if tamanho >= 2:
        pai = (tamanho - 2) // 2
        while True:
            _ajustar_heap(v, primeiro, pai, tamanho, v[primeiro + pai], menor)
            if pai == 0:
                break
            pai -= 1
    for i in range(meio, ultimo):
        if menor(v[i], v[primeiro]):
            _tirar_do_heap(v, primeiro, meio, i, v[i], menor)
    while meio - primeiro > 1:
        meio -= 1
        _tirar_do_heap(v, primeiro, meio, meio, v[meio], menor)
