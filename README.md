# monstervale-ia

Uma rede neural que aprende a jogar o tower defense [Monstervale](https://github.com/Brenaki/Monstervale) por aprendizado por reforço (PPO com máscara de ações). Projeto pessoal, para aprender e se divertir.

O plano completo, com as 12 decisões de projeto e o roteiro, está em [`docs/plano.md`](docs/plano.md). O que se aprende em cada marco fica em [`docs/aprendizado/`](docs/aprendizado).

## Andamento

| Marco | Status |
|---|---|
| M0 Repositório e ambiente | ✅ |
| M1 Mapas exportados do jogo | ✅ |
| M2 Simulação em Python com paridade | ⏳ rota ✅ entidades ✅ simulação ✅ · falta: partidas humanas |
| M3 Ambiente Gymnasium | |
| M4 Linhas de base | |
| M5 PPO + mini-TD | |
| M6 Fase 1 dominada | |
| M7 Assistir ao agente no Godot | |
| M8 Fases 2 a 5 | |

## Preparar

Precisa de Python 3.11+, [uv](https://docs.astral.sh/uv/) e [Godot 4.7.2](https://godotengine.org/download) (só para exportar mapas e assistir partidas).

```bash
git clone --recurse-submodules https://github.com/Kramekjvp/MonsterVale-IA.git
cd MonsterVale-IA
uv sync
uv run pytest
```

Se já tinha clonado sem `--recurse-submodules`: `git submodule update --init`.

### Exportar os mapas de novo

Só é preciso depois de atualizar o submódulo `jogo/`:

```bash
godot --headless --path jogo --import
godot --headless --path jogo -s ../ferramentas/exportar_mapas.gd -- ../dados/mapas
```

## Estrutura

```
jogo/              o Monstervale (submódulo git, fixado num commit; não editar)
dados/mapas/       mapas das 5 fases exportados do jogo
ferramentas/       scripts que rodam dentro do Godot
monstervale_ia/    código Python: mapa, simulação, ambiente, agente
testes/            testes (pytest)
docs/              plano e notas de aprendizado
```

## Créditos

O Monstervale é de [Brenaki](https://github.com/Brenaki) e não tem licença publicada: este repositório só aponta para ele como submódulo. Os mapas em `dados/mapas/` são derivados das cenas do jogo.
