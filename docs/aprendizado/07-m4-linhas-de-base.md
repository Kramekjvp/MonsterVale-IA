# M4: linhas de base

## O que foi feito

- `monstervale_ia/avaliacao.py`: avalia qualquer agente numa fase (vitórias, 3★, vidas, onda, retorno, tempo), em paralelo; gera a **variante perturbada** (decisão 12); acha a **melhor partida humana** de cada fase.
- `ferramentas/linhas_de_base.py`: roda os agentes sem rede neural e monta [`docs/linhas_de_base.md`](../linhas_de_base.md).
- `agentes.heuristico(classes=...)`: o heurístico restrito a uma classe, como os robôs dos testes de balanceamento do jogo.

## Por que linhas de base antes da rede

Sem régua, não dá para saber se a rede aprendeu algo. "A rede venceu a Fase 1" parece ótimo, até descobrir que 20 linhas de código também vencem. As linhas de base respondem três perguntas:

1. **O problema é difícil?** Se o aleatório vencesse, não precisaria de rede.
2. **Qual é o mínimo aceitável?** A rede tem que bater o heurístico.
3. **Qual é o teto conhecido?** O humano tirou 3★ em todas as fases.

## O que a tabela mostra

| Fase | Melhor sem rede | Humano |
|---|---|---|
| 1 | **só guerreiros: 3★, 20 vidas** | 3★, 20 vidas |
| 2 | ninguém vence (heurístico perde na onda 12) | 3★, 19 vidas |
| 3 | heurístico: 2★, 12 vidas | 3★, 20 vidas |
| 4 | só magos: 1★, 7 vidas | 3★, 20 vidas |
| 5 | heurístico: 2★, 12 vidas | 3★, 20 vidas |

Quatro achados:

**1. A Fase 1 já cai com uma regra simples.** "Só guerreiros, colados na estrada, melhorando sempre" segura todos os goblins: 3★ com 20 vidas. Os testes de balanceamento do jogo só verificam guerreiros de nível 1, que perdem. Para a etapa A, a Fase 1 é o aquecimento ideal: se a rede não aprender isso, o problema está na rede.

**2. O aleatório nunca vence nada.** 150 partidas, zero vitórias, sempre morto por volta da onda 4. É o ponto de partida da rede: no começo do treino ela joga assim, e o retorno é −2 em toda partida. A recompensa por onda (decisão 7) é o que dá sinal antes da primeira vitória: perder menos vidas já melhora o número.

**3. Vitória determinística pode ser sorte.** Na Fase 5, o heurístico vence com 2★ no jogo original, mas nas 10 variantes perturbadas vence só **40%** das vezes, com 3 vidas em média. A "vitória" dependia da partitura exata das ondas. É exatamente por isso que a decisão 12 exige mais do que uma vitória gulosa. Já na Fase 1 o heurístico é robusto (15,4 vidas nas variantes contra 15 no original).

**4. Cada fase pede uma classe diferente.** Lanceiros sozinhos vencem a 3 e a 5 (duas rotas, lobos rápidos); magos sozinhos são os únicos a vencer a 4 (cavaleiros esqueletos, fracos contra magia). O jogo foi desenhado para isso ("o que ensina" na tabela de fases do jogo). A rede vai ter que descobrir essas relações sozinha, pelas recompensas.

## A variante perturbada

`perturbar_fase(fase, semente)` muda só a "partitura" das ondas: cada grupo tem os tempos de surgimento multiplicados por um valor entre 0,9 e 1,1 e ganha ou perde até 1 monstro (mínimo 1). Mapa, classes, ouro e regras ficam iguais. A mesma semente gera sempre a mesma variante, então os resultados são reproduzíveis.

Ela não conta para "dominar" (decisão 1: sem mudar as regras), mas é a prévia barata da etapa D: mede se o agente **joga** ou só **decorou**.

## Para fixar

- **Toda medida precisa de régua:** aleatório (piso), heurística simples (mínimo aceitável), humano (teto conhecido).
- **Num ambiente determinístico, uma vitória não prova nada.** Teste variações antes de comemorar.
- **Baselines revelam o problema:** já sabemos que a Fase 1 é fácil, a 2 é a primeira de verdade, e cada fase favorece uma classe.
