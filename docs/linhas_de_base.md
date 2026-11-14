# Linhas de base (M4)

Gerado por `ferramentas/linhas_de_base.py`. Agentes sem rede neural, nas regras do commit fixado do jogo.

- **aleatório:** sorteia entre as ações válidas (chama a onda com 30% de chance); 30 partidas.
- **heurístico:** melhora o humano mais barato de melhorar; senão, posiciona colado na estrada, começando perto da vila e alternando as classes; senão, chama a onda. Determinístico: 1 partida.
- **heurístico, perturbado:** o mesmo, em 10 variantes da fase com tempos de surgimento ±10% e ±1 monstro por grupo (decisão 12). Mede o quanto o resultado depende da partitura exata das ondas.
- **só <classe>:** o heurístico usando uma classe só, como os robôs dos testes de balanceamento do jogo.
- **melhor humano:** a melhor partida gravada da fase, repetida nas regras de hoje.

Retorno = soma das recompensas (vitória perfeita com 3★ = +2,5; derrota sem vidas = −2).

## level_01

| Agente | Partidas | Vitórias | 3★ | Estrelas (média) | Vidas | Onda | Retorno | Minutos |
|---|---|---|---|---|---|---|---|---|
| aleatório | 30 | 0% | 0% | 0.00 | 0.0 | 3.4 | -2.00 | 2.0 |
| heurístico | 1 | 100% | 0% | 2.00 | 15.0 | 12.0 | +1.75 | 7.0 |
| heurístico, perturbado | 10 | 100% | 0% | 2.00 | 15.4 | 12.0 | +1.77 | 7.0 |
| só arqueiros | 1 | 100% | 0% | 2.00 | 12.0 | 12.0 | +1.60 | 6.6 |
| só guerreiros | 1 | 100% | 100% | 3.00 | 20.0 | 12.0 | +2.50 | 7.3 |
| **melhor humano** | 1 | 100% | 100% | 3 | 20 | todas | +2.50 | 5.2 |

## level_02

| Agente | Partidas | Vitórias | 3★ | Estrelas (média) | Vidas | Onda | Retorno | Minutos |
|---|---|---|---|---|---|---|---|---|
| aleatório | 30 | 0% | 0% | 0.00 | 0.0 | 3.5 | -2.00 | 3.2 |
| heurístico | 1 | 0% | 0% | 0.00 | 0.0 | 12.0 | -2.00 | 13.1 |
| heurístico, perturbado | 10 | 10% | 0% | 0.10 | 0.2 | 11.0 | -1.74 | 11.9 |
| só arqueiros | 1 | 0% | 0% | 0.00 | 0.0 | 7.0 | -2.00 | 6.9 |
| só guerreiros | 1 | 0% | 0% | 0.00 | 0.0 | 9.0 | -2.00 | 9.8 |
| só magos | 1 | 0% | 0% | 0.00 | 0.0 | 5.0 | -2.00 | 5.0 |
| **melhor humano** | 1 | 100% | 100% | 3 | 19 | todas | +2.45 | 6.2 |

## level_03

| Agente | Partidas | Vitórias | 3★ | Estrelas (média) | Vidas | Onda | Retorno | Minutos |
|---|---|---|---|---|---|---|---|---|
| aleatório | 30 | 0% | 0% | 0.00 | 0.0 | 4.1 | -2.00 | 1.9 |
| heurístico | 1 | 100% | 0% | 2.00 | 12.0 | 12.0 | +1.60 | 7.1 |
| heurístico, perturbado | 10 | 90% | 0% | 1.30 | 7.3 | 12.0 | +0.81 | 7.5 |
| só arqueiros | 1 | 0% | 0% | 0.00 | 0.0 | 6.0 | -2.00 | 3.3 |
| só guerreiros | 1 | 0% | 0% | 0.00 | 0.0 | 12.0 | -2.00 | 8.0 |
| só magos | 1 | 0% | 0% | 0.00 | 0.0 | 9.0 | -2.00 | 4.8 |
| só lanceiros | 1 | 100% | 0% | 1.00 | 6.0 | 12.0 | +0.80 | 7.0 |
| só druidas | 1 | 0% | 0% | 0.00 | 0.0 | 4.0 | -2.00 | 2.4 |
| **melhor humano** | 1 | 100% | 100% | 3 | 20 | todas | +2.50 | 6.7 |

## level_04

| Agente | Partidas | Vitórias | 3★ | Estrelas (média) | Vidas | Onda | Retorno | Minutos |
|---|---|---|---|---|---|---|---|---|
| aleatório | 30 | 0% | 0% | 0.00 | 0.0 | 3.6 | -2.00 | 2.7 |
| heurístico | 1 | 0% | 0% | 0.00 | 0.0 | 13.0 | -2.00 | 11.1 |
| heurístico, perturbado | 10 | 0% | 0% | 0.00 | 0.0 | 12.8 | -2.00 | 10.7 |
| só arqueiros | 1 | 0% | 0% | 0.00 | 0.0 | 10.0 | -2.00 | 8.1 |
| só guerreiros | 1 | 0% | 0% | 0.00 | 0.0 | 13.0 | -2.00 | 11.1 |
| só magos | 1 | 100% | 0% | 1.00 | 7.0 | 13.0 | +0.85 | 10.4 |
| só lanceiros | 1 | 0% | 0% | 0.00 | 0.0 | 12.0 | -2.00 | 10.2 |
| só druidas | 1 | 0% | 0% | 0.00 | 0.0 | 6.0 | -2.00 | 5.6 |
| só monges | 1 | 0% | 0% | 0.00 | 0.0 | 13.0 | -2.00 | 10.6 |
| só ladinos | 1 | 0% | 0% | 0.00 | 0.0 | 11.0 | -2.00 | 8.9 |
| **melhor humano** | 1 | 100% | 100% | 3 | 20 | todas | +2.50 | 10.4 |

## level_05

| Agente | Partidas | Vitórias | 3★ | Estrelas (média) | Vidas | Onda | Retorno | Minutos |
|---|---|---|---|---|---|---|---|---|
| aleatório | 30 | 0% | 0% | 0.00 | 0.0 | 3.7 | -2.00 | 2.6 |
| heurístico | 1 | 100% | 0% | 2.00 | 12.0 | 14.0 | +1.60 | 11.2 |
| heurístico, perturbado | 10 | 40% | 0% | 0.60 | 3.1 | 14.0 | -0.75 | 11.2 |
| só arqueiros | 1 | 0% | 0% | 0.00 | 0.0 | 13.0 | -2.00 | 10.0 |
| só guerreiros | 1 | 0% | 0% | 0.00 | 0.0 | 14.0 | -2.00 | 11.9 |
| só magos | 1 | 0% | 0% | 0.00 | 0.0 | 6.0 | -2.00 | 4.7 |
| só lanceiros | 1 | 100% | 0% | 2.00 | 11.0 | 14.0 | +1.55 | 11.9 |
| só druidas | 1 | 0% | 0% | 0.00 | 0.0 | 6.0 | -2.00 | 5.9 |
| só monges | 1 | 0% | 0% | 0.00 | 0.0 | 14.0 | -2.00 | 10.0 |
| só ladinos | 1 | 0% | 0% | 0.00 | 0.0 | 11.0 | -2.00 | 8.2 |
| **melhor humano** | 1 | 100% | 100% | 3 | 20 | todas | +2.50 | 11.6 |
