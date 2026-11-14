# M2, parte 4: as partidas humanas (M2 concluído)

## O que foi feito

- `ferramentas/capturar_partidas.gd`: repete as 42 partidas gravadas com o **jogador gravado do próprio jogo**, que clica nos botões reais da interface, e anota, quadro a quadro, as ações que chegaram à simulação, mais as impressões digitais do estado.
- `ferramentas/impressao_digital.gd`: o hash do estado, agora compartilhado entre os dois scripts do Godot.
- `testes/test_partidas_humanas.py`: o Python repete as 42 partidas e tem que passar pelos mesmos estados. As 4 partidas aprovadas também têm que terminar como o relatório original.

**Resultado:** 42 partidas, zero cliques falhos, todas idênticas quadro a quadro. As aprovadas terminam com o mesmo resultado, as mesmas vidas e o mesmo ouro do relatório.

## Qual é o alvo certo da comparação?

A ideia ingênua seria comparar o Python com os relatórios gravados. Mas o jogo mudou depois de muitas dessas partidas: o balanceamento foi ajustado várias vezes, com base justamente nelas. Exemplo: a partida aprovada da Fase 4 terminou com 16 vidas quando foi jogada, e hoje, repetida, termina com 20, porque a onda 13 encolheu.

Então há duas perguntas diferentes:

| Pergunta | Contra o quê comparar |
|---|---|
| O port reproduz o jogo **de hoje**? | A repetição feita pelo Godot de hoje (as 42 partidas) |
| O jogo de hoje ainda reproduz as partidas **aprovadas**? | O relatório original (as 4 que o jogo exige) |

O nosso port responde à primeira e herda a segunda de graça.

## Tempo × quadros

As partidas gravam as ações por **tempo** e relativas às ondas ("comprei um arqueiro 3,2 s depois do início da onda 4"), e as ondas são chamadas repetindo as pausas da pessoa. Converter isso em quadros exatos tem regras sutis: margem de relógio, ondas que começavam sozinhas antes das ondas manuais, pausa medida a partir da limpeza do campo...

Em vez de portar essas regras, **deixamos o próprio jogo fazer a conversão**: o script observa a simulação antes e depois de cada quadro e anota a diferença (quem foi posicionado, melhorado, dispensado, quantas ondas foram chamadas). Princípio de novo: não reimplemente o que dá para observar na fonte de verdade.

A única regra nossa é a **ordem das ações dentro de um quadro**: dispensar primeiro (devolve ouro), depois melhorar, posicionar e, por último, chamar a onda. As impressões digitais confirmam que a ordem está certa.

## Testes rápidos × lentos

A suíte completa leva ~3 minutos. Para o dia a dia:

```bash
uv run pytest -m 'not lento'   # 77 testes em menos de 1 s
uv run pytest                  # tudo: + paridade de partidas inteiras
```

Rode a completa antes de cada commit que mexe em `simulacao.py`.

## O que o M2 entregou

Uma simulação em Python que é, comprovadamente, **o mesmo jogo** que o Monstervale:

| Camada | Garantia |
|---|---|
| Rota | ~19 mil posições bit a bit |
| Monstro e humano | 2.400 valores de dano, níveis, regen quadro a quadro |
| Ordenação | introsort do Godot, inclusive empates |
| Simulação | 15 roteiros sintéticos, ~122 mil quadros |
| Partidas reais | 42 partidas humanas, quadro a quadro |

Daqui para frente, tudo o que a rede aprender no Python vale no jogo de verdade.

## Para fixar

- **Defina o alvo da paridade com cuidado:** "igual ao jogo de hoje" e "igual ao que aconteceu" são perguntas diferentes quando o jogo evolui.
- **Observe em vez de reimplementar:** capturar o efeito (diferença de estado) é mais seguro que portar a regra que o produz.
- **Separe testes rápidos e lentos**, para o ciclo de desenvolvimento continuar ágil.
