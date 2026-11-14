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
```

Godot fixado em 4.7.2 (mesma versão do jogo).
