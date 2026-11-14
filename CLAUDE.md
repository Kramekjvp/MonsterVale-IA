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
uv run pytest                             # testes
godot --headless --path jogo --import     # uma vez, depois de clonar
godot --headless --path jogo -s ../ferramentas/exportar_mapas.gd -- ../dados/mapas
# respostas douradas (o Godot calcula, o Python tem que bater bit a bit)
godot --headless --path jogo -s ../ferramentas/referencias_rota.gd -- ../testes/referencias/rota.json
```

## Port da simulação

- Cada arquivo de `jogo/src/core/` vira um módulo em `monstervale_ia/` (route.gd → rota.py ...).
- Contas com `Vector2` passam por `monstervale_ia/vetor.py`, que copia o C++ do Godot em float32.
- `float` do GDScript é float64: distâncias percorridas, tempos e cooldowns ficam em float do Python.
- Paridade é igualdade exata, sem tolerância. Se um teste dourado falhar, procure a operação que mudou de precisão.

Godot fixado em 4.7.2 (mesma versão do jogo).
