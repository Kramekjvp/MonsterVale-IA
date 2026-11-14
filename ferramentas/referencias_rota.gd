extends SceneTree
## Gera as "respostas douradas" da rota: o que o route.gd do jogo devolve para
## várias distâncias em todas as rotas das 5 fases. O port Python precisa
## reproduzir esses números exatamente (testes/test_rota.py).
##
## Uso (a partir da raiz do monstervale-ia):
##   godot --headless --path jogo -s ../ferramentas/referencias_rota.gd -- ../testes/referencias/rota.json

const LevelReader = preload("res://src/game/level_reader.gd")
const Route = preload("res://src/core/route.gd")
const LEVEL_IDS := ["level_01", "level_02", "level_03", "level_04", "level_05"]
const LEVEL_SCENE := "res://src/game/levels/%s.tscn"
## Passo "quebrado" de propósito, para cair no meio dos segmentos e gerar frações.
const SAMPLE_STEP := 0.37


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var out := ProjectSettings.globalize_path("res://").path_join(args[0]).simplify_path()
	DirAccess.make_dir_recursive_absolute(out.get_base_dir())
	var result := {}
	for id: String in LEVEL_IDS:
		var scene: Node = load(LEVEL_SCENE % id).instantiate()
		var level := LevelReader.read(scene, {})
		scene.free()
		var routes := []
		for points: Array in level.routes:
			routes.append(_samples(Route.new(points)))
		result[id] = routes
	var file := FileAccess.open(out, FileAccess.WRITE)
	file.store_string(JSON.stringify(result, "", false, true))
	file.close()
	print("referências: ", out)
	quit()


func _samples(route: Route) -> Dictionary:
	var distances := [-5.0, 0.0]
	var d := SAMPLE_STEP
	while d < route.length + 5.0:
		distances.append(d)
		d += SAMPLE_STEP
	distances.append(route.length)
	var samples := []
	for distance: float in distances:
		var p := route.position_at(distance)
		samples.append([distance, p.x, p.y, route.horizontal_direction_at(distance)])
	return {"length": route.length, "samples": samples}
