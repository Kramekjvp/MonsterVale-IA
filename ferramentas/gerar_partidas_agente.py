"""Gera partidas do ambiente e grava os relatórios no formato do jogo em
testes/referencias/agente/, mais o histórico de ações de cada uma.

Serve para provar que uma partida jogada no ambiente é repetida igual no
Monstervale de verdade (testes/test_ambiente.py). Usa o agente aleatório
(perde cedo, muita ação desfeita) e o heurístico (chega ao fim e às vezes vence).

Uso: uv run python ferramentas/gerar_partidas_agente.py
Depois: godot --headless --path jogo -s ../ferramentas/capturar_partidas.gd -- \
        ../testes/referencias/agente.json ../testes/referencias/agente
"""

import json
import shutil
from pathlib import Path

from monstervale_ia.agentes import aleatorio, heuristico, jogar
from monstervale_ia.ambiente import AmbienteMonstervale
from monstervale_ia.dados_jogo import IDS_FASES

PASTA = Path(__file__).resolve().parent.parent / "testes" / "referencias" / "agente"

if __name__ == "__main__":
    shutil.rmtree(PASTA, ignore_errors=True)
    PASTA.mkdir(parents=True)
    historicos = {}
    for fase in IDS_FASES:
        for nome_agente, agente, semente in [("aleatorio", aleatorio(), 1), ("heuristico", heuristico(), 0)]:
            env = AmbienteMonstervale(fase, gravar=True)
            resumo = jogar(env, agente, semente)
            nome = f"agente_{fase}_{nome_agente}.json"
            env.salvar_relatorio(PASTA / nome)
            historicos[nome] = {
                "level": fase, "historico": env.historico, "roteiro": env.historico_como_roteiro(),
                "estado": env.sim.estado, "vidas": env.sim.vidas, "ouro": env.sim.ouro, "quadro": env.quadro,
            }
            print(f"{nome}: {resumo['estado']}, onda {resumo['onda']}, vidas {resumo['vidas']}, "
                  f"estrelas {resumo['estrelas']}, {len(env.historico)} ações")
    (PASTA.parent / "agente_historicos.json").write_text(json.dumps(historicos), encoding="utf-8")
