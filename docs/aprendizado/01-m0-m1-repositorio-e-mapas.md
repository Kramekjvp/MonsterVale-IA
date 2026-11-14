# M0 e M1: repositório e mapas

## O que foi feito

1. **Repositório com o jogo como submódulo.** `jogo/` aponta para o Monstervale no commit `be61e63` (7/nov/2026).
2. **Ambiente Python com uv.** `pyproject.toml` declara as dependências e `uv.lock` fixa as versões exatas. Assim, notebook e desktop rodam a mesma coisa.
3. **Exportação dos mapas.** `ferramentas/exportar_mapas.gd` roda dentro do Godot sem tela e grava `dados/mapas/level_0X.json`.
4. **Leitura do mapa em Python.** `monstervale_ia/mapa.py` carrega o JSON, calcula por quais células a rota passa e desenha o mapa em texto.
5. **Testes de sanidade.** `testes/test_mapa.py` tem 6 testes × 5 fases = 30 verificações.

## Por que cada coisa

### Submódulo em vez de cópia

Um submódulo é um "ponteiro" para um commit específico de outro repositório. O nosso projeto inteiro depende de as regras do jogo não mudarem: se o autor ajustar o balanceamento amanhã, um agente treinado hoje pode passar a perder sem você ter mudado nada. Com o submódulo fixado, a versão do jogo só muda quando você decide (`git submodule update --remote`) e, nessa hora, os testes de paridade dizem se o port Python precisa de ajuste.

### Por que exportar pelo próprio Godot

O mapa de cada fase está numa cena `.tscn`, que guarda os tiles num formato binário compactado. Daria para tentar decodificar isso em Python, mas seria reimplementar uma parte do Godot e torcer para acertar. Em vez disso, o script **usa o próprio `LevelReader` do jogo**: a regra "esta célula é construível" é exatamente a mesma que o jogo aplica (tile com o dado `buildable` e sem decoração por cima). Princípio geral: quando dá para usar a fonte de verdade, não reimplemente.

O `-s` do Godot roda um script que estende `SceneTree` no lugar do jogo; `--headless` roda sem janela. É o mesmo truque que o projeto do jogo usa para rodar os testes.

### Por que float32

O Godot guarda `Vector2` com 32 bits por número; o Python, por padrão, usa 64. Parece detalhe, mas a simulação compara distâncias o tempo todo ("o monstro está no alcance?", "qual é o mais perto?"). Com precisões diferentes, um empate pode cair para um lado no Godot e para o outro no Python, e a partida diverge dali em diante. Por isso as rotas já são carregadas como `float32`.

## O que os mapas mostram

`#` construível · `1`/`2` rota (e entrada) · `+` rotas juntas · `*` decoração · `V` vila

Fase 1, um caminho:

```
   01234567890123456789
 0 ....................
 1 ####*#####*##*#.....
 2 #*#############.....
 3 ########111111111V..
 4 ########1######.....
 5 ##*#####1######.....
 6 ########1###########
 7 111111111######*##*#
 8 ###########*########
 9 #*###*##########*#*#
10 ....................
```

Fase 3, duas entradas que se juntam perto da vila:

```
   01234567890123456789
 0 ....................
 1 #*##*####*###*#.....
 2 11111111#*#*###.....
 3 #######1#####++++V..
 4 #*#####111111+#.....
 5 ###*#########2#.....
 6 ##*##*##*#2222######
 7 ##########2####*####
 8 22222222222#*#####*#
 9 #*####*##*###*##*###
10 ....................
```

Observações que viram fatos para as próximas etapas:

- **A rota nunca passa por célula construível.** Guerreiros e monges seguram os monstros ficando *ao lado* da estrada, com alcance de 44 px (pouco mais de uma célula).
- **As linhas 0 e 10 nunca são construíveis**, porque ficam embaixo do HUD. A máscara de ações já elimina essas 40 células de graça.
- **Sobram ~90 a 125 células construíveis por fase.** Com 7 classes, "posicionar" tem no máximo ~875 opções válidas. Bem menos que as ~2.900 da conta teórica, e a máscara cuida disso.
- **Na Fase 3, a célula (7,6) fica perto das duas rotas.** O jogo registra que um arqueiro de nível 3 ali cobria as duas entradas. Ótimo teste futuro: a rede vai descobrir esse ponto sozinha?

## Para fixar

- **Fonte de verdade:** reaproveite o código original sempre que possível; reimplementar é para o que *precisa* rodar rápido (a simulação, no M2).
- **Reprodutibilidade:** submódulo fixado + `uv.lock` = qualquer máquina reproduz exatamente o mesmo ambiente e o mesmo jogo.
- **Testes de sanidade baratos** pegam erros de exportação antes que eles virem bugs misteriosos de treino três marcos depois.
