# M2, parte 1: a rota e os testes dourados

## O que foi feito

- `monstervale_ia/vetor.py`: aritmética de `Vector2` copiada do C++ do Godot, em float32.
- `monstervale_ia/rota.py`: port de `jogo/src/core/route.gd`.
- `ferramentas/referencias_rota.gd`: o Godot calcula a posição em ~19 mil distâncias nas 7 rotas das 5 fases e grava em `testes/referencias/rota.json`.
- `testes/test_rota.py`: os 6 testes originais do jogo traduzidos + 7 testes de paridade (um por rota) que exigem **igualdade exata** com o Godot.

## Como a rota funciona

Um monstro não guarda "onde está". Guarda **quantos pixels já andou** (`distance`). A rota é uma lista de pontos; para achar a posição, ela descobre em qual segmento aquela distância cai e anda o resto dentro do segmento:

```
pontos:   P0 ──────── P1
                      │
                      │
                      P2 ──────── P3
inícios:  0          |P0P1|      |P0P1|+|P1P2|
```

Isso simplifica muito o resto do jogo: "o monstro mais adiantado" é só a maior distância, e "andar" é somar velocidade × tempo.

## Testes dourados

Em vez de escrever à mão os valores esperados, **pedimos ao programa original que calcule** e gravamos as respostas. O port tem que reproduzi-las. É o jeito padrão de portar código com segurança: o original é o oráculo. Os 6 testes do jogo verificam o comportamento em casos simples; os dourados verificam ~19 mil casos reais, inclusive frações estranhas (passo de 0,37 px de propósito).

## Por que float32 importa: o experimento

O GDScript mistura duas precisões:

| Valor | Tipo no Godot | Precisão |
|---|---|---|
| distância percorrida, comprimento da rota, tempos | `float` | 64 bits |
| posições (`Vector2`) | `real_t` | 32 bits |

Na amostra `[36.63, 20.630001068115234, 272.0]`, a distância é 64 bits, mas o x da posição já mostra o arredondamento de 32 bits (`20.630001`).

Para medir se isso importa, escrevemos a versão "ingênua", com tudo em float64 do Python:

> **2.112 de 17.166 posições (12%) saem diferentes do Godot.** O maior erro é 0,00004 px.

Parece nada, mas a simulação faz comparações como `distância ≤ alcance`. Um monstro a exatamente 96 px de um arqueiro de alcance 96 está dentro ou fora conforme o último bit. Um ataque a mais ou a menos muda o ouro, que muda as compras, que muda a partida inteira. É o **efeito borboleta** de simulações determinísticas: erros minúsculos não ficam minúsculos.

Por isso `vetor.py` copia o C++ do Godot **operação por operação, na mesma ordem**. Em ponto flutuante, `(a + b) + c` pode ser diferente de `a + (b + c)`, então a ordem também importa.

## O custo

Contas com `np.float32` escalar são lentas em Python puro (cada operação cria um objeto NumPy). Por enquanto, priorizamos **certo** antes de **rápido**: com a paridade garantida pelos testes dourados, dá para otimizar depois (Numba, vetorização) e os testes avisam se a otimização mudar algum bit.

## Para fixar

- **Oráculo:** ao portar, o programa original gera as respostas esperadas.
- **Precisão é parte do comportamento:** em simulação determinística, float32 × float64 muda o resultado.
- **Primeiro certo, depois rápido**, com testes que travam o "certo" no lugar.
