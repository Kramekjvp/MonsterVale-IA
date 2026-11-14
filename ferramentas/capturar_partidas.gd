extends SceneTree
## Repete as partidas humanas gravadas (jogo/tests/fixtures/partidas) com o
## jogador gravado do próprio jogo, que clica nos botões reais da interface.
##
## As partidas registram ações por TEMPO e relativas às ondas; quem converte
## isso em cliques é o recorded_player.gd do jogo. Este script observa, quadro a
## quadro, quais ações de fato chegaram à simulação e grava:
##   - as ações por quadro, no formato dos roteiros (monstervale_ia/roteiro.py);
##   - as impressões digitais do estado a cada 30 quadros;
##   - o resumo por onda do relatório gerado pela repetição.
##
## Uso (a partir da raiz do monstervale-ia):
##   godot --headless --path jogo -s ../ferramentas/capturar_partidas.gd -- ../testes/referencias/partidas.json
## Com uma pasta como segundo argumento, repete os relatórios dela (ex.: partidas da rede):
##   godot --headless --path jogo -s ../ferramentas/capturar_partidas.gd -- saida.json ../pasta/com/relatorios

const RecordedPlayer = preload("res://tests/e2e/recorded_player.gd")
const FIXTURES_DIR := "res://tests/fixtures/partidas/"
const SAVE_PATH := "user://captura_progress.json"
const SETTINGS_PATH := "user://captura_settings.json"
const LOG_DIR := "user://captura_partidas"
const MAX_SECONDS := 1800.0
const FRAMES_BETWEEN_PRINTS := 30
const WAVE_FIELDS := ["spawned", "killed", "escaped", "units_down", "lives_end", "gold_end"]

var _kinds: Array
var _out: String
var _files: Array
var _dir: String
var _output := {}
var _impressao = load(ProjectSettings.globalize_path("res://").path_join("../ferramentas/impressao_digital.gd").simplify_path())


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var root := ProjectSettings.globalize_path("res://")
	_out = root.path_join(args[0]).simplify_path()
	_dir = root.path_join(args[1]).simplify_path() + "/" if args.size() > 1 else FIXTURES_DIR
	_files = Array(DirAccess.get_files_at(_dir)).filter(func(f): return f.ends_with(".json"))
	_files.sort()
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	file.store_string(JSON.stringify({"stars": {"0": 3, "1": 3, "2": 3, "3": 3}}))
	file.close()


func _process(_delta: float) -> bool:
	# Uma partida por quadro do SceneTree, para a interface montar os botões entre elas.
	if _files.is_empty():
		var f := FileAccess.open(_out, FileAccess.WRITE)
		f.store_string(JSON.stringify(_output, "", true, true))
		f.close()
		return true
	var name: String = _files.pop_front()
	_output[name] = _capture(JSON.parse_string(FileAccess.get_file_as_string(_dir + name)))
	var r: Dictionary = _output[name]
	print("%s: %s, %d vidas, %d ações, cliques falhos %s" % [name, r.state, r.lives, r.actions.size(), r.failed_clicks])
	return false


func _new_game():
	var game = load("res://src/game/main.tscn").instantiate()
	game.progress_path = SAVE_PATH
	game.settings_path = SETTINGS_PATH
	game.start_on_title = false
	game.tutorials_enabled = false
	game.log_dir = LOG_DIR
	root.add_child(game)
	game.set_dev("dev_mode", true)  # só o modo dev registra partidas, e o jogador gravado lê o registro
	game.set_process(false)
	return game


func _capture(report: Dictionary) -> Dictionary:
	var game = _new_game()
	game.open_level(game.LEVEL_IDS.find(report.level))
	if _kinds.is_empty():
		_kinds = game.sim._catalog.monsters.keys()
		_kinds.sort()
	var player := RecordedPlayer.new(game, report)
	var actions := []
	var prints := []
	var frame := 0
	while not player.is_done() and game.sim.elapsed < MAX_SECONDS:
		var before := _snapshot(game.sim)
		player.step()  # ações da pessoa + um passo de 1/60 s
		actions.append_array(_diff(frame, before, game.sim))
		if frame % FRAMES_BETWEEN_PRINTS == 0 or game.sim.state != "playing":
			prints.append([frame, game.sim.gold, game.sim.lives, game.sim.monsters.size(), _fingerprint(game.sim)])
		frame += 1
	var sim = game.sim
	var log: Dictionary = game._match_log.to_dict() if game._match_log != null else {}
	var result := {
		"level": report.level,
		"frames": frame,
		"actions": actions,
		"prints": prints,
		"state": sim.state,
		"lives": sim.lives,
		"gold": sim.gold,
		"failed_clicks": player.failed_clicks,
		"waves": _waves(log),
		"recorded": {"result": report.result, "lives_final": report.lives_final, "gold_final": report.gold_final, "waves": _waves(report)},
	}
	root.remove_child(game)
	game.free()
	return result


func _waves(log: Dictionary) -> Array:
	var waves := []
	for wave: Dictionary in log.get("waves", []):
		var row := {}
		for field: String in WAVE_FIELDS:
			row[field] = wave.get(field)
		waves.append(row)
	return waves


## Estado que só as ações do jogador mudam: humanos (célula, tipo, nível) e ondas chamadas.
func _snapshot(sim) -> Dictionary:
	var units := []
	for u in sim.units:
		units.append([u, u.cell, u.kind, u.level])
	return {"units": units, "waves": sim.waves_started()}


## Ações deste quadro, na ordem em que podem ser repetidas: dispensar (devolve ouro),
## melhorar, posicionar (na ordem em que entraram na lista) e chamar onda.
func _diff(frame: int, before: Dictionary, sim) -> Array:
	var actions := []
	var still := []
	for entry: Array in before.units:
		if entry[0] in sim.units:
			still.append(entry)
		else:
			actions.append([frame, "dismiss", entry[1].x, entry[1].y])
	for entry: Array in still:
		for i in entry[0].level - entry[3]:
			actions.append([frame, "upgrade", entry[1].x, entry[1].y])
	var known: Array = before.units.map(func(e): return e[0])
	for u in sim.units:
		if u not in known:
			actions.append([frame, "place", u.kind, u.cell.x, u.cell.y])
			for i in u.level - 1:
				actions.append([frame, "upgrade", u.cell.x, u.cell.y])
	for i in sim.waves_started() - before.waves:
		actions.append([frame, "call"])
	return actions


func _fingerprint(sim) -> String:
	return _impressao.of(sim, _kinds)
