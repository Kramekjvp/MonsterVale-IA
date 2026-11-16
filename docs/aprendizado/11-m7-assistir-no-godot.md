# M7: assistir à rede no Godot

## Resultado

A partida gulosa da rede da Fase 1, repetida **no próprio Monstervale** pela interface real (o `recorded_player.gd` do jogo clica nos botões): vitória, 20 vidas, 3★, 26 ações, nenhum clique falho. Os vídeos estão em `resultados/m7/`: `rede_level_01.mp4` (velocidade real, 7 min 25 s) e `rede_level_01_4x.mp4`.

Isso fecha o ciclo do projeto: o jogo em GDScript → o port em Python (com paridade exata) → a rede treinada no port → a partida da rede de volta no jogo, com o mesmo resultado.

## Como funciona

1. `AmbienteMonstervale(gravar=True)` registra a partida no formato dos relatórios do jogo (`salvar_relatorio`, M3), com os tempos ajustados em −1/60 s para o jogador gravado agir no mesmo quadro.
2. `ferramentas/capturar_partidas.gd` repete o relatório sem tela e confere estado, vidas e cliques. É a prova de que a partida funciona no jogo.
3. `ferramentas/gravar_video.gd` repete o mesmo relatório **com tela**, um passo de 1/60 s por quadro desenhado, e o **Movie Maker** do Godot (`--write-movie arquivo.avi --fixed-fps 60`) grava cada quadro. Com o tempo fixo, o vídeo sai em velocidade real mesmo que desenhar demore mais que 1/60 s.
4. O ffmpeg converte o AVI (MJPEG, ~1 GB) em MP4 H.264 (~24 MB).

```bash
godot --headless --path jogo --import
godot --headless --path jogo -s ../ferramentas/capturar_partidas.gd -- ../resultados/m7/captura.json ../resultados/m7/partidas
godot --path jogo --write-movie C:/caminho/absoluto/rede.avi --fixed-fps 60 -s ../ferramentas/gravar_video.gd -- ../resultados/m7/partidas/partida_rede_level_01.json
ffmpeg -i rede.avi -c:v libx264 -crf 23 -pix_fmt yuv420p -movflags +faststart rede.mp4
```

No desktop, o Godot e o ffmpeg ficam em `D:\Ferramentas` (fora do PATH: use o caminho completo, o `_console.exe` do Godot para ver a saída).

## O tropeço

A primeira gravação terminou em **derrota**, com um clique falho. O script montava o jogo em `_initialize()`, antes de a árvore de cenas rodar: os nós da interface ainda não existiam, e o primeiro clique do jogador gravado caiu no vazio. Sem o primeiro guerreiro, a partida desandou. Montar o jogo no primeiro `_process()` resolveu (é o que `capturar_partidas.gd` já fazia).

A lição: a mesma lista de ações dá resultados opostos se uma única ação falhar. Por isso a repetição confere os cliques falhos e o resultado final, e não só "o script rodou".

## O que a rede faz

Só guerreiros, nenhum arqueiro, num bloco colado à estrada: dois guerreiros antes da onda 1, melhorias até o nível 3, e uma nova posição só quando sobra ouro. As pessoas que jogaram misturavam arqueiros e guerreiros. Na Fase 1, o guerreiro com bloqueio parece dominar o arqueiro (o robô "só guerreiros" do M4 também tira 3★).

## Para fixar

- **Feche o ciclo no sistema original.** Um agente treinado num port só vale se o resultado se repetir no jogo de verdade.
- **Tempo fixo para gravar:** o Movie Maker desacopla a velocidade do vídeo da velocidade da máquina.
- **Ordem de inicialização importa** em scripts de `SceneTree`: monte cenas quando a árvore já está rodando.
