# M2, parte 2: monstro e humano

## O que foi feito

- `monstervale_ia/monstro.py`: port de `monster.gd`, com vida, resistências, lentidão, raiz, atordoamento e imunidades.
- `monstervale_ia/humano.py`: port de `unit.gd`, com níveis, custo de melhoria, reembolso, bloqueio e recuperação de vida.
- `monstervale_ia/godot.py`: funções numéricas do GDScript (`roundi`, `mini`, divisão de inteiros).
- `monstervale_ia/dados_jogo.py`: lê o balanceamento de `jogo/data/` e junta com o mapa exportado, no mesmo formato que o `LevelReader` monta.
- `ferramentas/referencias_entidades.gd` + `testes/test_entidades.py`: respostas douradas para 2.400 valores de dano, a progressão de nível dos 7 humanos e a recuperação de vida quadro a quadro.

## Como as duas classes funcionam

São **estado**: guardam números e respondem perguntas simples. Quem faz o jogo acontecer (andar, atacar, bloquear) é a simulação, na próxima parte.

- **Monstro:** guarda a distância andada na rota, a vida e os timers de efeito. A velocidade atual é 0 se estiver preso ou atordoado; senão, é a velocidade × o fator de lentidão. Uma lentidão mais fraca não substitui uma mais forte que ainda está valendo.
- **Humano:** guarda o nível, quanto ouro já foi gasto nele (`gasto`, que define o reembolso de metade), a vida e quem ele está segurando. Ao subir de nível, ganha a **diferença** de vida máxima: um guerreiro com 53/60 que sobe para o nível 2 (90 de vida) fica com 83, não com 90.

## A armadilha do arredondamento

O dano com resistência é `max(1, roundi(dano × resistência))`.

| Função | 2,5 vira | 3,5 vira | 4,5 vira |
|---|---|---|---|
| `roundi` do Godot (longe do zero) | 3 | 4 | 5 |
| `round` do Python (para o par, o "arredondamento bancário") | **2** | 4 | **4** |

Medimos: com o `round` do Python, **56 de 2.400 valores de dano** sairiam errados, quase todos com **esqueletos levando dano de impacto** (resistência 1,5), ou seja, monge e guerreiro contra esqueletos, o ponto central da Fase 4. A rede aprenderia que o monge é um pouco pior do que é de verdade.

Até a implementação "óbvia" do arredondamento correto tem um furo: `floor(x + 0.5)` transforma 0,49999999999999994 em 1, porque a soma já arredonda. O `roundi` aqui separa a parte inteira antes de comparar, como o `std::round` do C++.

## Números do JSON

O Godot lê **todo número do JSON como float**. O tipo final depende da variável que recebe:

```gdscript
var hp: int     # hp = data.hp      → vira int (trunca)
var speed: float  # speed = data.speed → continua float
```

No Python, o `json` já diferencia `18` (int) de `0.8` (float), mas o port faz as conversões explicitamente (`int(...)`, `float(...)`), espelhando os tipos declarados no GDScript. Divisão de inteiros também: `spent / 2` no GDScript trunca em direção ao zero, como em C, enquanto o `//` do Python arredonda para baixo. Para números positivos dá igual, mas `div_int` deixa a intenção explícita.

## Para fixar

- **Cada linguagem tem suas convenções numéricas:** arredondamento, divisão de inteiros, precisão. Ao portar, elas são parte do comportamento, não detalhe.
- **Estado × comportamento:** classes de estado simples tornam o resto testável; a lógica do jogo fica concentrada na simulação.
- **Testes dourados pegam o que a gente nem pensou em testar.** Ninguém escreveria à mão um teste para "esqueleto, impacto, dano 3".
