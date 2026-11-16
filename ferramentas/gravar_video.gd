extends SceneTree
## Grava em vídeo uma partida repetida pela interface real do jogo (M7: assistir à rede).
##
## Usa o recorded_player do jogo, como capturar_partidas.gd, mas COM tela: a cada quadro
## desenhado, um passo de 1/60 s. Com o Movie Maker do Godot (--write-movie), o tempo
## é fixo em 60 quadros por segundo, então o vídeo sai em velocidade real mesmo que a
## máquina demore mais para desenhar cada quadro.
##
## Uso (a partir da raiz do monstervale-ia):
##   godot --path jogo --write-movie C:/caminho/absoluto/rede.avi --fixed-fps 60 \
##         -s ../ferramentas/gravar_video.gd -- ../resultados/m7/partidas/partida_rede_level_01.json

const RecordedPlayer = preload("res://tests/e2e/recorded_player.gd")
const SAVE_PATH := "user://video_progress.json"
const SETTINGS_PATH := "user://video_settings.json"
const LOG_DIR := "user://video_partidas"
const SEGUNDOS_NO_FIM := 3.0  # deixa a tela de vitória aparecer antes de fechar o vídeo

var _game
var _player
var _report: Dictionary
var _quadros_no_fim := 0


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var caminho := ProjectSettings.globalize_path("res://").path_join(args[0]).simplify_path()
	_report = JSON.parse_string(FileAccess.get_file_as_string(caminho))
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	file.store_string(JSON.stringify({"stars": {"0": 3, "1": 3, "2": 3, "3": 3}}))
	file.close()


## O jogo é montado no primeiro quadro, com a árvore de cenas já rodando (em _initialize
## os nós do HUD ainda não existem, e os cliques do jogador gravado falham).
func _montar() -> void:
	_game = load("res://src/game/main.tscn").instantiate()
	_game.progress_path = SAVE_PATH
	_game.settings_path = SETTINGS_PATH
	_game.start_on_title = false
	_game.tutorials_enabled = false
	_game.log_dir = LOG_DIR
	root.add_child(_game)
	_game.set_dev("dev_mode", true)  # o jogador gravado lê o registro, que só o modo dev mantém
	_game.set_process(false)  # quem avança a simulação é o jogador gravado, um passo por quadro
	_game.open_level(_game.LEVEL_IDS.find(_report.level))
	_player = RecordedPlayer.new(_game, _report)


func _process(_delta: float) -> bool:
	if _game == null:
		_montar()
		return false
	if not _player.is_done():
		_player.step()
		return false
	if _quadros_no_fim == 0:
		var sim = _game.sim
		print("fim: %s, %d vidas, %d estrelas, cliques falhos %s" % [sim.state, sim.lives, sim.stars(), _player.failed_clicks])
	_quadros_no_fim += 1
	return _quadros_no_fim >= int(SEGUNDOS_NO_FIM * 60)
