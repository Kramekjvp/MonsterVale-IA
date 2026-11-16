# Rede neural para o Monstervale: plano e decisões

Projeto pessoal de Kramek, para aprender redes neurais e aprendizado por reforço e para se divertir. Decisões tomadas numa sessão Grill Me em 2026-11-14.

Jogo alvo: [Monstervale](https://github.com/Brenaki/Monstervale), um tower defense em Godot 4.7/GDScript com 5 fases, 7 classes de humanos com 3 níveis, 3 tipos de dano, bloqueio corpo a corpo, duas entradas a partir da Fase 3 e o chefe Rei Slime.

## Decisões

| # | Tema | Decisão | Por quê |
|---|---|---|---|
| 1 | Jogo | Monstervale, sem mudar as regras | A simulação já é separada da parte visual (`src/core/simulation.gd`) e é determinística |
| 2 | Objetivo | Etapa A: 3 estrelas em cada fase → Etapa C: otimizar cada parcela (tempo, ouro…) → Etapa D: generalizar para mapas nunca vistos | Cada etapa ensina algo novo; D exige um gerador de fases |
| 3 | Ponte com o jogo | Portar o núcleo da simulação para Python, lendo os mesmos JSONs de `data/`, com **testes de paridade** contra as partidas gravadas em `tests/fixtures/partidas` | Treino muito mais rápido que com o Godot pelo socket; a paridade garante fidelidade |
| 4 | Momento da decisão | Começa **por fase de construção** (o jogo pausa entre ondas e a rede faz várias ações, terminando em "chamar onda"); depois passa a **por eventos** | Partidas curtas para aprender; algumas fases pedem reação no meio da onda |
| 5 | Ações | Lista plana com **máscara**, gerada por uma **cabeça convolucional** (um mapa de notas por tipo de ação) + uma saída para "chamar onda". Prioridade de alvo fixa em "primeiro" até a etapa C | Mesmo código de treino de uma lista plana, mas aprende padrões espaciais que transferem para outros mapas (D) |
| 6 | Estado | Só informação bruta. Grid 20×11: construível, caminho, progresso na rota (0 na entrada → 1 na vila), rota da próxima onda, classe do humano (one-hot ×7) e nível. Vetor global: ouro, vidas, onda atual/total, composição da próxima onda, classes liberadas e custos. Canais de monstros entram no modo por eventos | A rede descobre sozinha as boas posições; canais pré-calculados (cobertura) ficam como experimento |
| 7 | Recompensa | Por onda: −(vidas perdidas ÷ vidas iniciais). No fim: bônus de vitória + bônus por estrela; derrota −1. Nada por abates nem por ouro | Alinhada com as estrelas (3★ = ≥ 90% das vidas), sem atalhos |
| 8 | Algoritmo | **PPO com máscara de ações**. Partidas humanas como régua de comparação. Imitação (BC) e busca (MCTS) ficam como experimentos futuros | Base estável e didática |
| 9 | Implementação | PPO próprio em PyTorch, estilo CleanRL (um arquivo), validado antes num **mini-TD de brinquedo** 5×5 | Entender o algoritmo por dentro; o brinquedo isola bugs do PPO |
| 10 | Hardware | Notebook com Arch para programar; desktop W11 (i5-10400F, 32 GB, GTX 1650) para treinar, **no Windows nativo** (revisto em 2026-11-14: o WSL2 do desktop não inicia); nuvem só se a etapa D pedir | O gargalo é a simulação na CPU: ~8–10 ambientes em paralelo |
| 11 | Repositório | Repositório próprio (`monstervale-ia`) com o Monstervale como **submódulo git fixado num commit** (`jogo/`) | Versão do jogo congelada; atualizar vira um passo consciente, seguido dos testes de paridade |
| 12 | Critério "fase dominada" | A política gulosa vence com 3★ **e** a política com sorteio tira 3★ em ≥ 80% de 100 partidas. Em todo relatório: robustez numa variante perturbada (tempos ±10%, ±1 monstro por grupo, só para medir) e comparação com a melhor partida humana (vidas, ouro sobrando, tempo) | Num jogo determinístico, uma vitória gulosa pode ser só uma sequência decorada |
| 13 | Agentes do M8 | **Um agente por fase**, cada um começando dos pesos da rede da Fase 1 (decidido em 2026-11-16). Na Fase 2, comparar com um treino do zero para medir se a transferência ajuda | A rede convolucional serve em qualquer mapa e já sabe o básico; um agente para todas as fases fica para a etapa D |

## Fatos técnicos levantados no código

- O jogo avança a simulação em passo fixo `STEP = 1/60` (`src/game/game.gd`), o que é ótimo para a paridade.
- O mapa (células construíveis e a rota) **não** está nos JSONs: vem das cenas `src/game/levels/level_0X.tscn` (TileMapLayer `Ground`/`Decor` e Path2D), lidas por `src/game/level_reader.gd`. Exportado para `dados/mapas/` no M1.
- Grid de 20×11 células de 32 px (resolução interna de 640×360). As linhas 0 e 10 nunca são construíveis (ficam sob o HUD).
- A rota nunca passa por célula construível: os humanos ficam ao lado da estrada.
- API da simulação: `place_unit`, `upgrade_unit`, `dismiss_unit`, `call_next_wave`, `can_call_next_wave`, `early_call_bonus`, `next_wave_preview`, `next_wave_routes`, `stars`, `tick(delta)`, `drain_events`.
- Sem sorte: as raízes, o atordoamento e o crítico seguem intervalos fixos.
- As partidas gravadas têm ações com `time`, `wave`, `cell`, `unit` e `level`, e um resumo por onda (vidas, ouro, abates, dano por classe).
- `tests/e2e/recorded_player.gd` repete partidas em JSON clicando na interface real. Se o agente exportar partidas nesse formato, dá para assisti-lo jogando no próprio Monstervale.
- **Risco de paridade:** no Godot, `Vector2` usa float32. Posições e distâncias no port Python devem usar float32 (NumPy) para não divergir em empates de alcance e de alvo.
- O Monstervale **não tem licença**. Estudar localmente tudo bem; para publicar o port ou os dados, pedir autorização ao autor (Brenaki).

## Roteiro da etapa A

| Marco | Entrega | Pronto quando |
|---|---|---|
| M0 | Repositório `monstervale-ia`, submódulo, ambiente Python (uv, pytest), WSL2 no desktop | `pytest` roda nas duas máquinas |
| M1 | Script Godot sem tela que exporta cada fase para `dados/mapas/level_0X.json` | 5 JSONs gerados e conferidos visualmente |
| M2 | Port de `route`, `monster`, `unit`, `game_data` e `simulation` para Python | Testes de paridade: as partidas gravadas batem onda por onda (vidas, ouro, abates) com os resumos dos JSONs |
| M3 | Ambiente Gymnasium no modo por fase de construção: estado, máscara, recompensa e exportação de partidas no formato do jogo | Uma partida aleatória com máscara roda do começo ao fim; a partida exportada é aceita pelo `recorded_player` |
| M4 | Linhas de base: aleatório com máscara e robôs heurísticos (estilo dos testes de balanceamento) | Tabela de resultados por fase |
| M5 | PPO próprio + mini-TD 5×5 | O PPO resolve o brinquedo de forma consistente (várias sementes) |
| M6 | Treino na Fase 1 | Critério da decisão 12 cumprido; relatório com a comparação humana |
| M7 | Assistir ao agente no Godot | Vídeo/GIF do agente vencendo a Fase 1 |
| M8 | Fases 2 a 5, um agente por fase partindo da rede da Fase 1 (decisão 13) | Critério cumprido em cada fase |

## Para decidir depois

- Modo por eventos: quais eventos disparam decisões; canais de monstros no estado.
- Etapa C: recompensa por parcela (tempo, ouro gasto); entrada da ação de prioridade; MCTS para o speedrun.
- Etapa D: gerador de fases (caminhos, entradas, áreas construíveis, ondas) e o protocolo de teste com as 5 fases reais como conjunto nunca visto.
- Experimentos: canais de cobertura × estado bruto; BC com partidas humanas × PPO puro; CPU × GPU.
