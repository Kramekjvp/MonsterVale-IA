# M5: o PPO, a rede e o mini-TD

## O que foi feito

- `monstervale_ia/rede.py`: a rede convolucional com cabeça espacial (decisão 5).
- `monstervale_ia/ppo.py`: o PPO com máscara de ações, escrito do zero no estilo CleanRL (decisões 8 e 9).
- `monstervale_ia/mini_td.py`: um tower defense 5×5 de brinquedo, com a estratégia ótima calculada por força bruta.
- `ferramentas/treinar_mini_td.py`: treina e compara com o ótimo.
- PyTorch 2.15 e TensorBoard nas dependências.

**Resultado:** nas 3 sementes, a política gulosa chega a **100% do ótimo** nos 4 traçados, e a sorteada a 99,5–100%, em ~20 mil passos (~10 s de treino).

## A rede

```
grid (C × A × L) ──┐
                   ├─ concat ─→ 4 × [conv 3×3 + ReLU] ─→ tronco (64 × A × L)
global (G) ─ pinta ┘                                       │
                                                           ├─ conv 1×1 ───→ T mapas A × L ─→ notas "tipo × célula"
                                                           ├─ média + global ─→ MLP ─→ nota "chamar onda"
                                                           └─ média + máximo + global ─→ MLP ─→ valor
```

- **"Pintar" o vetor global** em todas as células: cada célula sabe quanto ouro há, quantas vidas restam etc. na hora de dar a nota de "pôr um arqueiro aqui".
- **Convoluções 3×3** olham a vizinhança. Com 4 camadas, cada célula "enxerga" 9×9 células em volta, o suficiente para o alcance do arqueiro (~3,5 células).
- **Cabeça espacial 1×1:** a nota de "tipo k na célula (x, y)" sai do próprio ponto (x, y) do tronco. A rede aprende "o que torna uma célula boa", não "a ação nº 1.234 é boa". Por isso a **mesma rede** roda em 5×5, 11×20 e em qualquer mapa novo (testado em `test_ppo.py`).
- **Máscara:** as ações proibidas recebem nota −10⁸ antes do softmax, ou seja, probabilidade zero.

São ~168 mil parâmetros. É uma rede pequena, que cabe com folga na GTX 1650.

## O PPO, em três passos

**1. Coleta.** 8 ambientes jogam 64 a 128 passos cada com a política atual. Para cada passo guardamos estado, máscara, ação, log-probabilidade, valor estimado e recompensa.

**2. Vantagem (GAE).** Para cada passo: "foi melhor ou pior que o esperado?"

```
δ_t = r_t + γ·V(s_{t+1})·(1 − fim_t) − V(s_t)       erro de uma etapa
A_t = δ_t + γ·λ·(1 − fim_t)·A_{t+1}                 soma descontada dos erros
```

O `(1 − fim)` corta o futuro quando a partida acaba: o valor da próxima partida não tem nada a ver com esta.

**3. Atualização.** Quatro épocas sobre o lote, em minilotes:

```
razão = π_novo(a|s) / π_velho(a|s)
L = −mín( razão·A,  recorte(razão, 0,8, 1,2)·A )   ← a "trava" do PPO
  + 0,5·(V(s) − retorno)²                           ← o valor aprende a prever
  − 0,01·entropia                                   ← continuar explorando
```

O recorte é a ideia central do PPO: se uma ação boa já ficou 20% mais provável, o gradiente para de empurrar. Isso evita que um lote de sorte destrua a política.

Os números para acompanhar no TensorBoard (`uv run tensorboard --logdir resultados/treinos`):

| Métrica | O que diz | Faixa saudável |
|---|---|---|
| `partida/retorno` | o desempenho | subindo |
| `entropia` | o quanto ainda explora | cai devagar; despencar cedo é mau sinal |
| `kl` | o quanto a política mudou na atualização | ~0,001 a 0,02 |
| `fracao_recortada` | quantas razões bateram na trava | < 0,2 |
| `variancia_explicada` | se o valor prevê bem os retornos | sobe até perto de 1 |

## O mini-TD

Um 5×5 com as mesmas peças do Monstervale (grid, máscara, ações `tipo × célula + chamar`, recompensa por onda e estrelas), com 4 traçados sorteados a cada partida. Assim a rede é obrigada a **ler o mapa**: nenhuma posição fixa serve para os 4.

A primeira versão era fácil demais: 29% a 96% das configurações de torre resolviam a última onda. Endurecemos as ondas até só 3,5% a 6% resolverem (exceto no traçado em U, em que muitas células cobrem duas voltas do caminho). O aleatório caiu de −0,07 para −1,31; o ótimo seguiu +2,5.

## O brinquedo pega bugs? A sabotagem

Um teste que nunca falha não prova nada. Introduzimos de propósito três bugs clássicos de quem implementa PPO:

| PPO | Gulosa | Sorteada |
|---|---|---|
| correto | **100% do ótimo** | +2,50 |
| GAE esquece que a partida acabou | 92% | +2,00 |
| vantagem com o sinal trocado | −80% | −2,00 |
| treino ignora a máscara (a coleta usa) | 92% | +2,32 |

**A lição mais importante do M5:** os bugs sutis não dão erro nem fazem o treino explodir. Eles só deixam o resultado uns **8% pior**. No Monstervale, sem saber o ótimo, um resultado 8% pior pareceria "a rede ainda está aprendendo". É por isso que o PPO tinha de ser validado num problema com resposta conhecida antes, e por isso o critério de aprovação é rígido: **gulosa = 100% e sorteada ≥ 97%, em todas as sementes.**

## Fumaça no Monstervale

O PPO roda no ambiente real sem erro. Com só 4 mil passos, joga como o aleatório (retorno −2, perde na onda 3), o que é esperado. O número que importa para o M6: **~40 passos de decisão por segundo aqui (2 núcleos)**. Cada "chamar onda" roda milhares de quadros de simulação, e isso domina o tempo: a rede em si é rápida.

No desktop (6 núcleos, ambientes em paralelo), a estimativa é de 150 a 300 passos por segundo. Treinos de milhões de passos levariam horas a dias. Por isso o primeiro passo do M6 é **otimizar a simulação**, com os testes de paridade garantindo que nenhum bit mude.

## Para fixar

- **Teste o algoritmo num problema com resposta conhecida antes do problema real.**
- **Sabote seus próprios testes** para provar que eles pegam bugs.
- **Bugs em aprendizado por reforço não quebram: pioram um pouco.** Só uma referência exata os denuncia.
- **Meça onde está o gargalo:** aqui é a simulação, não a rede.
