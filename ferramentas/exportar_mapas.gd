extends SceneTree
## Exporta o mapa de cada fase do Monstervale (cenas .tscn) para JSON.
##
## O mapa não está nos JSONs de balanceamento do jogo: as células construíveis
## vêm dos TileMapLayers "Ground" e "Decor" e as rotas dos monstros vêm dos
## Path2D "Route", "Route2"... Para o port em Python ler exatamente o que o jogo
## lê, este script usa o próprio LevelReader do jogo.
##
## Uso (a partir da raiz do monstervale-ia):
##   godot --headless --path jogo -s ../ferramentas/exportar_mapas.gd -- ../dados/mapas

const LevelReader = preload("res://src/game/level_reader.gd")
const LEVEL_IDS := ["level_01", "level_02", "level_03", "level_04", "level_05"]
const LEVEL_SCENE := "res://src/game/levels/%s.tscn"
## Resolução interna do jogo (640×360) dividida pelo tamanho do tile (32 px).
const GRID_COLUMNS := 20
const GRID_ROWS := 11


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var out_dir := args[0] if args.size() > 0 else "../dados/mapas"
	out_dir = ProjectSettings.globalize_path("res://").path_join(out_dir).simplify_path()
	DirAccess.make_dir_recursive_absolute(out_dir)
	for id: String in LEVEL_IDS:
		var path := out_dir.path_join("%s.json" % id)
		var file := FileAccess.open(path, FileAccess.WRITE)
		file.store_string(JSON.stringify(_export(id), "  ", false))
		file.close()
		print("exportado: ", path)
	quit()


func _export(id: String) -> Dictionary:
	var scene: Node = load(LEVEL_SCENE % id).instantiate()
	var level := LevelReader.read(scene, {})
	var ground: TileMapLayer = scene.get_node("Ground")
	var decor: TileMapLayer = scene.get_node("Decor")
	var village: Node2D = scene.get_node("Village")
	var data := {
		"id": id,
		"cell_size": level.cell_size,
		"columns": GRID_COLUMNS,
		"rows": GRID_ROWS,
		"buildable": _sorted_cells(level.buildable.keys()),
		"ground": _sorted_cells(ground.get_used_cells()),
		"decor": _sorted_cells(decor.get_used_cells()),
		"routes": level.routes.map(func(points): return points.map(_point)),
		"village": _point(village.position),
	}
	scene.free()
	return data


func _point(point: Vector2) -> Array:
	return [point.x, point.y]


func _sorted_cells(cells: Array) -> Array:
	var list := cells.map(func(cell: Vector2i): return [cell.x, cell.y])
	list.sort_custom(func(a, b): return a[1] < b[1] or (a[1] == b[1] and a[0] < b[0]))
	return list
