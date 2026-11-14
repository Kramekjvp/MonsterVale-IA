# monstervale-ia

Projeto pessoal de aprendizado: uma rede neural (PPO com máscara de ações) para dominar o tower defense [Monstervale](https://github.com/Brenaki/Monstervale).

## Como trabalhar aqui

- Tudo em português: código (nomes), comentários, docs e mensagens de commit.
- O objetivo é **aprender**. A cada marco, explique o que foi feito e por quê, e registre em `docs/aprendizado/`.
- As decisões do projeto estão em `docs/plano.md`. Não mude uma decisão sem discutir com o Kramek.
- `jogo/` é o Monstervale como submódulo fixado num commit. **Nunca edite arquivos dentro de `jogo/`.** Atualizar o submódulo exige rodar os testes de paridade de novo.
- Posições e distâncias da simulação usam **float32**, como o `Vector2` do Godot.
- O jogo avança em passo fixo de 1/60 s (`STEP` em `jogo/src/game/game.gd`).

## Comandos

```bash
uv sync                                   # ambiente Python
uv run pytest -m 'not lento'              # testes rápidos (segundos)
uv run pytest                             # tudo, inclusive paridade de partidas (~3 min)
godot --headless --path jogo --import     # uma vez, depois de clonar
godot --headless --path jogo -s ../ferramentas/exportar_mapas.gd -- ../dados/mapas
# respostas douradas (o Godot calcula, o Python tem que bater bit a bit)
godot --headless --path jogo -s ../ferramentas/referencias_rota.gd -- ../testes/referencias/rota.json
godot --headless --path jogo -s ../ferramentas/referencias_entidades.gd -- ../testes/referencias/entidades.json
godot --headless --path jogo -s ../ferramentas/referencias_ordenacao.gd -- ../testes/referencias/ordenacao.json
uv run python ferramentas/gerar_roteiros.py   # roteiros de ações para a paridade da simulação
godot --headless --path jogo -s ../ferramentas/executar_roteiro.gd -- ../testes/referencias/roteiros_entrada.json ../testes/referencias/roteiros.json
godot --headless --path jogo -s ../ferramentas/capturar_partidas.gd -- ../testes/referencias/partidas.json   # ~4 min
uv run python ferramentas/gerar_partidas_agente.py   # partidas do ambiente exportadas no formato do jogo
godot --headless --path jogo -s ../ferramentas/capturar_partidas.gd -- ../testes/referencias/agente.json ../testes/referencias/agente
```

## Port da simulação

- Cada arquivo de `jogo/src/core/` vira um módulo em `monstervale_ia/` (route.gd → rota.py ...).
- Contas com `Vector2` passam por `monstervale_ia/vetor.py`, que copia o C++ do Godot em float32.
- `float` do GDScript é float64: distâncias percorridas, tempos e cooldowns ficam em float do Python.
- Ordem das etapas, ordem dos laços e critérios de desempate do GDScript são parte do comportamento: não "melhore".
- `sort_custom` do Godot não é estável: use `ordenar_como_godot` (godot.py), nunca `sorted()`.
- Os nomes de estado ("playing", "won", "lost") e de eventos ("unit_placed"...) ficam iguais aos do jogo.
- Paridade é igualdade exata, sem tolerância. Se um teste dourado falhar, procure a operação que mudou de precisão.

## Ambiente (M3)

- `monstervale_ia/ambiente.py`: Gymnasium, modo por fase de construção. Ações: `tipo × 220 + y × 20 + x` (0–6 posicionar, 7 melhorar, 8 dispensar) e 1980 = chamar onda.
- Ações permitidas pela máscara TÊM que funcionar (o ambiente confere com assert).
- `salvar_relatorio()` ajusta os tempos em −1/60 s para o recorded_player do jogo repetir no mesmo quadro.

Godot fixado em 4.7.2 (mesma versão do jogo).
