extends RefCounted
## Impressão digital (SHA-1) do estado completo da simulação, em bytes exatos.
## Mesmo formato de impressao_digital() em monstervale_ia/roteiro.py.

const STATES := {"playing": 0, "won": 1, "lost": 2}


static func of(sim, kinds: Array) -> String:
	var b := StreamPeerBuffer.new()  # little-endian por padrão
	b.put_double(sim.elapsed)
	b.put_32(sim.gold)
	b.put_32(sim.lives)
	b.put_32(STATES[sim.state])
	b.put_32(sim.waves_started())
	b.put_double(sim.next_wave_countdown)
	b.put_32(sim.monsters.size())
	for m in sim.monsters:
		b.put_32(kinds.find(m.kind))
		b.put_double(m.distance)
		b.put_32(m.hp)
		b.put_double(m.cooldown)
		b.put_double(m.slow_timer)
		b.put_double(m.slow_factor)
		b.put_double(m.root_timer)
		b.put_double(m.stun_timer)
		b.put_32(sim.units.find(m.blocker) if m.blocker != null else -1)
	b.put_32(sim.units.size())
	for u in sim.units:
		b.put_32(u.level)
		b.put_32(u.hp)
		b.put_double(u.cooldown)
		b.put_double(u.down_timer)
		b.put_32(u.attacks_made)
		b.put_32(u.blocked.size())
	b.put_32(sim.fires.size())
	for f: Dictionary in sim.fires:
		b.put_double(f.remaining)
		b.put_double(f.timer)
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA1)
	ctx.update(b.data_array)
	return ctx.finish().hex_encode()

