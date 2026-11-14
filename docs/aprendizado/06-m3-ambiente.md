# M3: o ambiente de treino

## O que foi feito

- `monstervale_ia/ambiente.py`: o `AmbienteMonstervale`, um ambiente **Gymnasium** no modo por fase de construção.
- `monstervale_ia/relatorio.py`: port do `match_log.gd`; as partidas da rede saem no formato de relatório do jogo.
- `monstervale_ia/agentes.py`: dois agentes sem rede neural (aleatório e heurístico), que são as primeiras linhas de base.
- `testes/test_ambiente.py`: espaço, máscara, recompensa, determinismo e a prova de que **uma partida jogada no ambiente é repetida igual, quadro a quadro, dentro do Monstervale**.

## O que é um ambiente Gymnasium

É a interface padrão entre um jogo e um algoritmo de aprendizado por reforço. São só dois métodos:

```python
obs, info = env.reset()                              # começa uma partida
obs, recompensa, terminou, truncou, info = env.step(acao)  # faz uma jogada
```

O algoritmo (o PPO, no M5) não sabe nada de Monstervale: vê números (`obs`), escolhe um número (`acao`) e recebe outro número (`recompensa`). Toda a tradução "jogo ↔ números" mora no ambiente. Por isso, o ambiente é onde moram as decisões 4 a 7 do plano.

## Como a rede joga (decisão 4)

O tempo para entre as ondas. Cada `step` é **uma** ação:

```
posicionar / melhorar / dispensar → o tempo não anda, recompensa 0, a rede escolhe de novo
chamar a onda                     → a simulação roda até o campo limpar; recompensa da onda
```

Depois de 10 ações na mesma construção, a máscara só deixa chamar a onda. Sem esse limite, uma rede no começo do treino poderia ficar posicionando e dispensando para sempre.

## As ações (decisão 5)

São 1.981 números: `tipo × 220 + y × 20 + x`, com tipo 0–6 = posicionar cada classe, 7 = melhorar, 8 = dispensar, e o 1980 = chamar a onda. Essa ordem é proposital: é a mesma da saída que a rede vai ter, um mapa 20×11 de notas para cada tipo de ação, achatado.

A **máscara** (`action_masks()`) marca quais estão válidas agora. No início da Fase 1, são 249 de 1.981 (2 classes × 124 células + chamar). O PPO zera a probabilidade das inválidas antes de sortear, então a rede nunca perde tempo aprendendo que "não dá para pôr mago na Fase 1". O ambiente confere que toda ação permitida pela máscara funciona, e os testes jogam centenas de ações aleatórias para provar isso.

## O que a rede vê (decisão 6)

- `grid` (12 × 11 × 20): construível, caminho, progresso na rota (0 na entrada → 1 na vila), rota da próxima onda, um canal por classe e o nível.
- `global` (29 números): ouro, vidas, ondas, composição da próxima onda (10 tipos de monstro), classes liberadas, custos, bônus de chamar agora e ações restantes.

Tudo é dividido por escalas fixas para ficar perto de 0 a 1. Redes neurais aprendem mal quando um número de entrada vale 1.000 (ouro) e outro vale 0,05.

## A recompensa (decisão 7)

Por onda: −(vidas perdidas ÷ 20). No fim: vitória +1, +0,5 por estrela; derrota −1. A heurística que vence a Fase 1 com 15 vidas recebe −0,25 + 1 + 1,0 = **+1,75**. Uma vitória perfeita (3★, 20 vidas) recebe +2,5.

## Assistir no jogo: o atraso de um quadro

Para assistir à rede no Monstervale (M7), o relatório tem que ser repetível pelo jogador gravado do jogo. O primeiro teste falhou, e o motivo é instrutivo: o jogador gravado **anota o início de cada onda um quadro depois** de chamá-la (ele só olha a simulação no começo do passo seguinte) e mede as ações a partir daí. Nas partidas humanas isso não importa. Na nossa, as ações da construção vêm antes da chamada da onda e, na repetição, caíam depois dela.

Sem poder mexer no jogo, a exportação compensa: as ações saem com 1/60 s a menos, o que cancela o atraso exatamente. O teste agora compara o histórico do ambiente (convertido em roteiro) com a repetição feita **dentro do jogo**, quadro a quadro, nas 10 partidas, inclusive as do agente aleatório, que posiciona e dispensa no mesmo quadro.

**Lição:** um teste mais fraco ("termina com as mesmas vidas") tinha passado nas partidas heurísticas e escondido o problema. O teste certo compara o estado inteiro.

## As primeiras linhas de base

| Fase | Heurística (melhora o mais barato; posiciona colado na estrada) | Aleatório |
|---|---|---|
| 1 | vence 2★ | perde na onda 4 |
| 2 | perde na onda 12 | perde na onda 4 |
| 3 | vence 2★ | perde na onda 4 |
| 4 | perde na onda 13 | perde na onda 4 |
| 5 | vence 2★ | perde na onda 4 |

Uma heurística de 20 linhas vence 3 fases com 2★. Para valer a pena, a rede tem que chegar às **3★**, e é isso que o critério da decisão 12 exige.

## Velocidade

Uma partida inteira leva 4 a 10 s; a de um agente que joga mal (o começo do treino) leva menos de 1 s.

## Para fixar

- **O ambiente é o contrato** entre o jogo e o aprendizado: estado, ações, recompensa e fim de partida.
- **Máscara de ações** tira do aprendizado o trabalho inútil de descobrir as regras.
- **Teste o que você quer garantir:** "repete igual" é comparar o estado inteiro, não só o placar final.
