extends SceneTree
## Respostas douradas de monster.gd e unit.gd:
## - dano depois da resistência, para todo monstro × tipo de dano × dano de 1 a 80;
## - custos, reembolso e vida de cada humano ao subir de nível;
## - recuperação de vida (regen) quadro a quadro, nos níveis que têm regen.
##
## Uso (a partir da raiz do monstervale-ia):
##   godot --headless --path jogo -s ../ferramentas/referencias_entidades.gd -- ../testes/referencias/entidades.json

const GameData = preload("res://src/core/game_data.gd")
const Monster = preload("res://src/core/monster.gd")
const Unit = preload("res://src/core/unit.gd")
const Route = preload("res://src/core/route.gd")
const STEP := 1.0 / 60.0


func _init() -> void:
	var out := ProjectSettings.globalize_path("res://").path_join(OS.get_cmdline_user_args()[0]).simplify_path()
	DirAccess.make_dir_recursive_absolute(out.get_base_dir())
	var catalog := GameData.load_catalog()
	var result := {
		"damage": _damage_table(catalog),
		"units": _unit_levels(catalog),
		"regen": _regen_traces(catalog),
	}
	var file := FileAccess.open(out, FileAccess.WRITE)
	file.store_string(JSON.stringify(result, "", true, true))
	file.close()
	print("referências: ", out)
	quit()


func _damage_table(catalog: Dictionary) -> Dictionary:
	var route := Route.new([Vector2(0, 0), Vector2(100, 0)])
	var table := {}
	for kind: String in catalog.monsters:
		var monster := Monster.new(kind, catalog.monsters[kind], route)
		var by_type := {}
		for damage_type: String in GameData.DAMAGE_TYPES:
			var row := []
			for amount in range(1, 81):
				row.append(monster.damage_from(amount, damage_type))
			by_type[damage_type] = row
		table[kind] = by_type
	return table


func _unit_levels(catalog: Dictionary) -> Dictionary:
	var result := {}
	for kind: String in catalog.units:
		var unit := Unit.new(kind, catalog.units[kind], Vector2i(3, 4), Vector2(112, 144))
		var steps := []
		while true:
			steps.append({
				"level": unit.level, "spent": unit.spent, "refund": unit.refund(),
				"hp": unit.hp, "upgrade_cost": unit.upgrade_cost(),
				"block_room": unit.has_block_room(),
			})
			if not unit.can_upgrade():
				break
			unit.hp -= 7  # dano antes de subir: a melhoria mantém a vida perdida
			unit.raise_level()
		result[kind] = steps
	return result


func _regen_traces(catalog: Dictionary) -> Dictionary:
	var result := {}
	for kind: String in catalog.units:
		for level in range(1, 4):
			if not catalog.units[kind].levels[level - 1].has("regen"):
				continue
			var unit := Unit.new(kind, catalog.units[kind], Vector2i(0, 0), Vector2.ZERO)
			while unit.level < level:
				unit.raise_level()
			unit.hp = 10
			var trace := []
			for frame in 900:
				unit.recover(STEP)
				trace.append(unit.hp)
			result["%s_%d" % [kind, level]] = trace
	return result
