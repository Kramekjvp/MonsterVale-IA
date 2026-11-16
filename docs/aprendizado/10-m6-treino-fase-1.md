# M6: treino na Fase 1

## Resultado

**Fase 1 dominada** pelo critério da decisão 12, com a rede de 1 milhão de passos (`resultados/treinos/f1_s1/rede_1M.pt`):

| Agente | Partidas | Vitórias | 3★ | Vidas | Minutos |
|---|---|---|---|---|---|
| rede gulosa | 1 | 100% | 100% | 20 | 7,4 |
| rede sorteada | 100 | 100% | **100%** (mínimo 80%) | 20,0 | 7,3 |
| rede gulosa, perturbada | 10 | 100% | 100% | 19,6 | 7,3 |
| heurístico | 1 | 100% | 0% | 15 | 7,0 |
| melhor humano | 1 | 100% | 100% | 20 | 5,2 |

Comparação com o humano: as mesmas 20 vidas, 116 de ouro sobrando contra 127, e **2 minutos mais lenta** (7,4 contra 5,2).

## O que foi feito

- **Coleta assíncrona** (`ppo.py`): cada ambiente roda no seu processo e no seu ritmo; a rede responde em lote a quem estiver pronto. Antes, todos esperavam o ambiente que estivesse rodando uma onda.
- **Checkpoints, retomada e melhor rede** (`ppo.py`). A retomada recusa uma config diferente da salva, porque mudaria o anelamento da taxa no meio do treino.
- **Avaliação da decisão 12** (`agente_rede.py`, `ferramentas/avaliar_agente.py`): gulosa, sorteada ×100, variante perturbada, humano, e a partida gulosa exportada no formato do jogo.
- **Treino por fase** (`ferramentas/treinar_fase.py`): gamma 0,999, 16 ambientes, avaliação gulosa a cada 10 atualizações.

## Por que gamma 0,999

O bônus de vitória e estrelas só chega no fim da partida. Antes do treino, estimei até ~130 decisões por partida (12 ondas × até 10 ações + chamar): com γ = 0,99, o bônus valeria 0,99¹³⁰ ≈ 27% visto da primeira decisão; com 0,999, ~88%. Na prática a rede aprendeu a jogar com só ~26 decisões por partida (0,99²⁶ ≈ 77%), então 0,99 talvez também servisse. Numa partida curta e finita, quase não descontar custa pouca variância e é a escolha segura.

## A curva

| Passos | Gulosa | Partidas sorteadas do treino |
|---|---|---|
| 20 mil | perde na onda 3 | perdem |
| 61 mil | vence com 1★ (6 vidas) | perdem (onda ~4) |
| 143 mil | **3★, 20 vidas** | — |
| 225 mil → 1 M | 3★, 20 vidas, sempre | 3★ em média, entropia caindo até 0,22 |

## Três lições

**1. Decisões por segundo não são constantes.** O treino começou a ~138 decisões/s e terminou a ~25. No começo a rede perde na onda 3 com ~11 decisões; no fim joga as 12 ondas com ~26 decisões (constrói pouco e bem). Cada decisão passa a carregar muito mais quadros de simulação. *Quanto melhor o agente, mais caro cada passo.* O orçamento de um treino tem que ser pensado em quadros simulados, não em passos.

**2. A gulosa satura antes da política estar pronta.** Aos 143 mil passos a gulosa já fazia 3★, mas a `melhor_rede.pt` (a primeira a atingir +2,5) tira 3★ só em **74%** das partidas sorteadas: reprovada. Foram precisos mais passos para a política inteira (não só a ação mais provável) ficar firme. Escolher a melhor rede só pelo retorno guloso é uma régua que satura: depois de +2,5, ela não distingue mais nada.

**3. Robustez sem ter treinado para ela.** Na variante perturbada (tempos ±10%, ±1 monstro), que a rede nunca viu, ela venceu as 10 com 3★ e perdeu em média 0,4 vida. É um sinal de que joga, e não só decorou a partitura.

## O que fica para depois

- **Tempo:** a rede é 2 minutos mais lenta que o humano porque a recompensa não fala de tempo (decisão 7). É exatamente a etapa C.
- **Seleção da melhor rede:** avaliar também a sorteada periodicamente (algumas partidas) ou escolher pela fração de 3★ da sorteada.
- **Velocidade:** com o agente bom, a simulação domina de novo. Para as fases 2 a 5 (mais longas e mais difíceis) vale medir Python 3.13 e, se preciso, um núcleo em Numba.

## Para fixar

- **Meça o critério de verdade, não um substituto.** A gulosa com 3★ parecia "pronto"; a sorteada mostrou que não estava.
- **O custo por passo muda durante o treino.** Planeje em quadros simulados.
- **Variantes perturbadas** distinguem jogar de decorar, mesmo num jogo determinístico.
