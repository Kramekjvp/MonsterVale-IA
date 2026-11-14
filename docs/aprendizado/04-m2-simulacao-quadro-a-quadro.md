# M2, parte 3: a simulação, quadro a quadro

## O que foi feito

- `monstervale_ia/simulacao.py`: port completo de `simulation.gd` (ondas, surgimento, movimento, bloqueio, ataques, prioridades de alvo, explosão, linha, fogo, crítico, controle, divisão dos slimes, Rei Slime, ouro e estrelas).
- `monstervale_ia/godot.py`: port do **introsort** do Godot (`Array.sort_custom`).
- `monstervale_ia/vetor.py`: `direction_to` e `Geometry2D.get_closest_point_to_segment`, copiados do C++.
- `monstervale_ia/roteiro.py` + `ferramentas/executar_roteiro.gd`: o mesmo roteiro de ações roda no Godot e no Python, e o estado completo é comparado a cada 30 quadros.
- 15 roteiros (3 por fase), ~122 mil quadros, **todos idênticos bit a bit** ao jogo.

## O passo da simulação

Cada `passo(1/60)` faz, nesta ordem:

```
contagem da próxima onda → surgimento → monstros (andar/bloquear/bater)
→ humanos atacam → fogo queima → ondas limpas dão bônus → vitória/derrota
```

A **ordem importa**. Se os humanos atacassem antes de os monstros andarem, um goblin que entraria no alcance neste quadro só levaria a flechada no próximo. Por isso o port mantém a mesma ordem das etapas e dos laços, inclusive as cópias de lista (`monsters.duplicate()` vira `list(self.monstros)`) e os critérios de desempate:

- **Escolha de alvo:** `nota > melhor`, com `>` estrito. No empate, vence o **primeiro** monstro da lista.
- **Ataque de passagem:** `d <= menor`, com `<=`. No empate, vence o **último** humano da lista.

São escolhas arbitrárias do código original. O port não pode "melhorá-las".

## Impressão digital do estado

Comparar o estado inteiro a cada quadro geraria arquivos enormes. A solução foi uma **impressão digital**: os dois lados escrevem o estado completo (tempo, ouro, vidas e, para cada monstro e humano, distância, vida, timers e bloqueio) em bytes, no mesmo formato, e calculam o SHA-1. Um único bit diferente muda o hash inteiro. O teste mostra o primeiro quadro em que os hashes divergem, que é onde começar a procurar o bug.

## Cobertura: teste que passa fácil demais engana

A primeira versão dos roteiros passou de primeira, e isso pedia desconfiança. Medimos o que eles exercitavam: as partidas duravam ~1 minuto, ninguém chegava ao nível 3, e não havia fogo, divisão de slime nem Rei Slime. **Um teste de paridade só garante o que ele executa.** Corrigimos com três tipos de roteiro por fase:

| Roteiro | O que exercita |
|---|---|
| rápido | ondas sobrepostas, derrota |
| calmo | ritmo normal, derrota mais tarde |
| completo | invencível + ouro extra: todas as classes no nível 3, fogo, críticos, raízes, atordoamento, divisões e o Rei Slime soltando filhotes até morrer |

## A ordenação que não é estável

A explosão do mago atinge "os N monstros mais perto do alvo". Para isso, o jogo ordena por distância com `sort_custom`, que usa **introsort** e **não é estável**: em empates, a ordem pode mudar. O `sorted()` do Python é estável. Testamos contra o Godot, com empates forçados:

> Até 16 elementos, as duas ordenações concordam (o introsort usa ordenação por inserção, que é estável). **A partir de 17, divergem**, exatamente o limiar `INTROSORT_THRESHOLD = 16` do código C++.

Numa onda de slimes se dividindo perto de uma explosão, 17 monstros no raio acontecem de verdade. Por isso o algoritmo de ordenação do Godot foi portado linha a linha.

## Velocidade

| | Quadros/s | Comparado ao tempo real |
|---|---|---|
| Godot (GDScript) | ~2.400 | ~40× |
| Python (port) | ~1.300 a 2.100 | ~20× a 35× |

Uma fase de 10 minutos leva ~20 s num núcleo. Com 8 processos no desktop, são ~1.500 partidas por hora. Dá para começar, mas otimizar vai acelerar muito o treino. Há margem evidente: `posicao()` recalcula a posição na rota várias vezes por quadro para o mesmo monstro. Como os testes de paridade travam o comportamento, qualquer otimização que mude um bit é pega na hora.

## Para fixar

- **Determinismo exige reproduzir as arbitrariedades:** ordem das etapas, critérios de desempate, algoritmo de ordenação.
- **Hash do estado** é um jeito barato de comparar simulações longas e achar o primeiro ponto de divergência.
- **Desconfie de teste verde fácil:** meça a cobertura (que regras de fato rodaram) antes de confiar.
