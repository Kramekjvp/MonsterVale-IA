"""Avalia uma rede treinada pelo critério da decisão 12 (fase dominada?).

Grava, na pasta de saída (padrão: ao lado da rede): avaliacao.md, avaliacao.json
e partida_gulosa.json (a partida da gulosa no formato do jogo, para o M7).

Uso:
  uv run python ferramentas/avaliar_agente.py resultados/treinos/x/rede.pt --fase level_01 --processos 8
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from monstervale_ia.agente_rede import (
    comparar_com_humano, criterio_dominada, exportar_partida_gulosa, robustez_gulosa,
)
from monstervale_ia.agentes import heuristico
from monstervale_ia.avaliacao import CABECALHO, avaliar


def avaliar_rede(caminho: Path, fase: str, processos: int, saida: Path) -> dict:
    saida.mkdir(parents=True, exist_ok=True)
    gulosa, sorteada, veredito = criterio_dominada(caminho, fase, processos)
    perturbada = robustez_gulosa(caminho, fase, processos)
    heur = avaliar(fase, "heurístico", heuristico, [0])
    comparacao = comparar_com_humano(gulosa, fase)
    partida = exportar_partida_gulosa(caminho, fase, saida / "partida_gulosa.json")

    linhas = [
        f"# Avaliação de {caminho.name} em {fase}",
        "",
        f"**Veredito (decisão 12): {'FASE DOMINADA' if veredito.dominada else 'fase NÃO dominada'}**"
        f" — gulosa {'vence com 3★' if veredito.gulosa_venceu_3_estrelas else 'não vence com 3★'};"
        f" sorteada tira 3★ em {veredito.tres_estrelas_sorteada:.0%} de {sorteada.partidas} partidas"
        f" (mínimo {veredito.minimo:.0%}).",
        "",
        CABECALHO,
        gulosa.linha(), sorteada.linha(), perturbada.linha(), heur.linha(),
    ]
    if comparacao:
        h, a = comparacao["humano"], comparacao["agente"]
        linhas.append(
            f"| **melhor humano** | 1 | 100% | {'100%' if h['estrelas'] == 3 else '0%'} | {h['estrelas']} | "
            f"{h['vidas']} | todas | — | {h['minutos']:.1f} |"
        )
        linhas += [
            "", "## Comparação com o melhor humano", "",
            "| | Vidas | Ouro sobrando | Minutos |", "|---|---|---|---|",
            f"| rede gulosa | {a['vidas']:.0f} | {a['ouro_final']:.0f} | {a['minutos']:.1f} |",
            f"| melhor humano | {h['vidas']} | {h['ouro_final']} | {h['minutos']:.1f} |",
        ]
    linhas += ["", f"Partida gulosa exportada: `{partida.name}`."]
    (saida / "avaliacao.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    dados = {
        "rede": str(caminho), "fase": fase, "veredito": asdict(veredito),
        "gulosa": asdict(gulosa), "sorteada": asdict(sorteada), "gulosa_perturbada": asdict(perturbada),
        "heuristico": asdict(heur), "comparacao_humano": comparacao,
    }
    (saida / "avaliacao.json").write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    return dados


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("rede", type=Path)
    parser.add_argument("--fase", default="level_01")
    parser.add_argument("--processos", type=int, default=2)
    parser.add_argument("--saida", type=Path, default=None)
    args = parser.parse_args()
    saida = args.saida or args.rede.parent
    avaliar_rede(args.rede, args.fase, args.processos, saida)
    print((saida / "avaliacao.md").read_text(encoding="utf-8"))
