# Otimização da simulação (antes do M6)

## Resultado

| Medida | Antes | Depois |
|---|---|---|
| Carga fixa (5 fases heurísticas + 20 partidas aleatórias) | 37,9 s | ~10 s (**3,9×**) |
| Quadros de simulação por segundo | 8.500 | ~33.000 |
| Treino PPO, 4 ambientes, aqui (2 núcleos) | ~40 decisões/s | 75–83 decisões/s |
| Suíte de paridade lenta | ~4 min | ~45 s |

E nenhum bit mudou: rota, entidades, os 15 roteiros, as 42 partidas humanas e as repetições no jogo continuam idênticos ao Godot.

Ferramenta: `uv run python ferramentas/medir_velocidade.py [--perfil]`.

## O método: medir, mudar, provar, repetir

1. **Medir com perfil (cProfile)** numa carga fixa e representativa. Otimizar sem perfil é chutar.
2. **Atacar o maior item.** O primeiro perfil foi claro: `posicao_em` era chamada 12 milhões de vezes para 2,1 milhões de monstro-quadros, ~6 vezes por monstro a cada quadro, e as distâncias outras 24 milhões.
3. **Provar que nada mudou:** a paridade completa depois de cada rodada.
4. **Parar nos retornos decrescentes:** a terceira rodada não ganhou nada mensurável. Era hora de parar.

## As otimizações

**Cache de posição.** A posição de um monstro só depende da distância percorrida. `Monstro.posicao()` guarda o resultado e só recalcula quando a distância muda. Monstros bloqueados, presos ou atordoados não andam, e então nem recalculam.

**Rota com pré-cálculo.** `move_toward` refazia `vd / |vd|` a cada chamada, mas para um segmento fixo esse valor é constante. Ele é calculado uma vez, com **as mesmas operações float32, na mesma ordem**, e por isso dá os mesmos bits. A busca do segmento virou busca binária (`bisect`), que devolve o mesmo índice do laço original. A posição e a direção saem da mesma busca.

**Pré-filtro de distância em float64.** "Está no alcance?" é a pergunta mais feita. Em float64 (rápido, Python puro) ela quase sempre tem resposta óbvia; só quando a distância cai a menos de **0,001 px** da borda é que fazemos a conta exata em float32. Isso é seguro porque, num mapa de ~700 px, o erro do float32 numa distância fica abaixo de ~0,0003 px: fora da faixa de 0,001 px, é impossível as duas contas discordarem. Nas comparações de "o mais perto", a conta exata continua sendo feita, só que apenas para os candidatos que passam no filtro.

**Atributos em campos.** `humano.atributos()["range"]` era uma busca em dicionário em cada laço; agora `humano.alcance` é atualizado ao subir de nível.

**Contas no próprio laço.** Nos laços mais internos, chamar uma função custa mais que a conta. O pré-filtro passou a ser escrito direto no laço.

## O que NÃO se pode otimizar

As regras de `CLAUDE.md` continuam valendo: a ordem das etapas, a ordem dos laços, os desempates e o introsort do Godot. Exemplo: em `_proximos`, as distâncias passaram a ser calculadas uma vez antes de ordenar, mas a ordenação continua sendo a do Godot, com os mesmos valores float32 comparados.

## Onde está o tempo agora

No treino, a simulação ainda é ~85% do tempo, e a rede (forward + backward) ~20% (o profiler infla um pouco o código Python). A máscara e a observação somam menos de 1%.

O próximo salto exigiria reescrever o núcleo em **Numba** ou **Cython**, com a simulação toda em arrays. É um projeto grande, que só vale se o treino real mostrar que precisa. Estimativa para o desktop (6 núcleos, ambientes em processos, rede na GPU): **~300 a 400 decisões/s**, ou ~1 hora por milhão de passos.

## Para fixar

- **Perfil antes de otimizar**, numa carga fixa que represente o uso real.
- **Cache de valores derivados** (posição a partir da distância) é o ganho mais barato.
- **Pré-filtro com margem provada**: a conta rápida decide os casos óbvios; a exata, só a fronteira.
- **Testes de paridade tornam a otimização segura**: dá para ousar, porque qualquer bit diferente aparece na hora.
- **Saiba parar:** quando uma rodada não ganha nada, o resto custa mais do que vale.
