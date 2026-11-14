"""Gera testes/referencias/roteiros_entrada.json: 3 roteiros por fase.

- rapido: chama onda a cada 4 s (ondas sobrepostas, perde cedo)
- calmo: chama onda a cada 25 s
- completo: invencível e com ouro extra, para todos chegarem ao nível 3 e
  todas as habilidades (fogo, linha, raiz, atordoamento, crítico, divisão,
  Rei Slime) entrarem em jogo

Uso: uv run python ferramentas/gerar_roteiros.py
Depois: godot --headless --path jogo -s ../ferramentas/executar_roteiro.gd -- \
        ../testes/referencias/roteiros_entrada.json ../testes/referencias/roteiros.json
"""

import json
from pathlib import Path

from monstervale_ia.dados_jogo import IDS_FASES, carregar_fase
from monstervale_ia.roteiro import gerar_roteiro

SAIDA = Path(__file__).resolve().parent.parent / "testes" / "referencias" / "roteiros_entrada.json"

entrada = {}
for f in IDS_FASES:
    classes = carregar_fase(f)["classes"]
    entrada[f"{f}_rapido"] = {"level": f, "frames": 54_000, "actions": gerar_roteiro(f, classes)}
    entrada[f"{f}_calmo"] = {"level": f, "frames": 60_000, "actions": gerar_roteiro(f, classes, 60_000, 1500, 26)}
    entrada[f"{f}_completo"] = {
        "level": f, "frames": 80_000, "invincible": True,
        "actions": gerar_roteiro(f, classes, 80_000, 900, 26, ouro_extra=6000),
    }
SAIDA.write_text(json.dumps(entrada))
print(f"{len(entrada)} roteiros em {SAIDA}")
