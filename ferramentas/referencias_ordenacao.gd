extends SceneTree
## Respostas douradas do Array.sort_custom() do Godot com MUITOS empates.
## O introsort do Godot não é estável; o port em monstervale_ia/godot.py precisa
## deixar os empates na mesma ordem.
##
## Uso: godot --headless --path jogo -s ../ferramentas/referencias_ordenacao.gd -- ../testes/referencias/ordenacao.json


func _init() -> void:
	var out := ProjectSettings.globalize_path("res://").path_join(OS.get_cmdline_user_args()[0]).simplify_path()
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	var cases := []
	for size in [0, 1, 2, 5, 16, 17, 18, 33, 64, 100, 257, 1000]:
		for distinct in [1, 3, 10, 1000]:
			var items := []
			for i in size:
				items.append([rng.randi_range(0, distinct - 1), i])  # [chave, id original]
			var sorted := items.duplicate()
			sorted.sort_custom(func(a, b): return a[0] < b[0])
			cases.append({"input": items, "output": sorted.map(func(x): return x[1])})
	var file := FileAccess.open(out, FileAccess.WRITE)
	file.store_string(JSON.stringify(cases))
	file.close()
	quit()
