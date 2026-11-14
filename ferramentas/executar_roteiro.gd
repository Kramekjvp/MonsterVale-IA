extends SceneTree
## Executa roteiros de ações (gerados pelo Python) na simulação ORIGINAL do jogo
## e grava as impressões digitais do estado a cada 30 quadros.
## Formato do roteiro e da impressão digital: monstervale_ia/roteiro.py.
##
## Uso (a partir da raiz do monstervale-ia):
##   godot --headless --path jogo -s ../ferramentas/executar_roteiro.gd -- ../testes/referencias/roteiros_entrada.json ../testes/referencias/roteiros.json

const GameData = preload("res://src/core/game_data.gd")
const LevelReader = preload("res://src/game/level_reader.gd")
const Simulation = preload("res://src/core/simulation.gd")
const LEVEL_SCENE := "res://src/game/levels/%s.tscn"
const STEP := 1.0 / 60.0
const FRAMES_BETWEEN_PRINTS := 30


var _impressao = load(ProjectSettings.globalize_path("res://").path_join("../ferramentas/impressao_digital.gd").simplify_path())


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var root := ProjectSettings.globalize_path("res://")
	var input: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(root.path_join(args[0]).simplify_path()))
	var catalog := GameData.load_catalog()
	var kinds: Array = catalog.monsters.keys()
	kinds.sort()
	var output := {}
	for name: String in input:
		var spec: Dictionary = input[name]
		var scene: Node = load(LEVEL_SCENE % spec.level).instantiate()
		var level := LevelReader.read(scene, GameData.load_level(spec.level))
		scene.free()
		var sim = Simulation.new(catalog, level)
		sim.invincible = spec.get("invincible", false)
		output[name] = _run(sim, spec.actions, kinds, int(spec.frames))
		print(name, ": ", output[name].state, " em ", output[name].prints[-1][0], " quadros")
	var out := root.path_join(args[1]).simplify_path()
	var file := FileAccess.open(out, FileAccess.WRITE)
	if file == null:
		push_error("não consegui gravar %s (caminhos são relativos a jogo/)" % out)
		quit(1)
		return
	file.store_string(JSON.stringify(output, "", false, true))
	file.close()
	quit()


func _run(sim, actions: Array, kinds: Array, frames: int) -> Dictionary:
	var by_frame := {}
	for action: Array in actions:
		var frame := int(action[0])
		if not by_frame.has(frame):
			by_frame[frame] = []
		by_frame[frame].append(action)
	var results := []
	var prints := []
	for frame in frames:
		for action: Array in by_frame.get(frame, []):
			results.append(_apply(sim, action))
		sim.tick(STEP)
		if frame % FRAMES_BETWEEN_PRINTS == 0 or sim.state != "playing":
			prints.append([frame, sim.gold, sim.lives, sim.monsters.size(), _fingerprint(sim, kinds)])
		if sim.state != "playing":
			break
	return {"results": results, "prints": prints, "state": sim.state}


func _apply(sim, action: Array) -> bool:
	match action[1]:
		"place":
			return sim.place_unit(action[2], Vector2i(int(action[3]), int(action[4]))) != null
		"call":
			return sim.call_next_wave()
		"gold":
			sim.gold += int(action[2])
			return true
	var unit = sim.unit_at(Vector2i(int(action[2]), int(action[3])))
	if unit == null:
		return false
	match action[1]:
		"upgrade":
			return sim.upgrade_unit(unit)
		"dismiss":
			sim.dismiss_unit(unit)
			return true
		"priority":
			unit.cycle_priority()
			return true
	push_error("ação desconhecida: %s" % action[1])
	return false


func _fingerprint(sim, kinds: Array) -> String:
	return _impressao.of(sim, kinds)
