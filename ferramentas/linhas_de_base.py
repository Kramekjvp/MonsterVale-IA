"""Linhas de base do M4: como jogam agentes sem rede neural, em cada fase.

Grava resultados/linhas_de_base/<fase>.json e, com --tabela, monta
docs/linhas_de_base.md a partir de todos os JSONs.

Uso:
  uv run python ferramentas/linhas_de_base.py level_01 [level_02 ...] [--processos 8]
  uv run python ferramentas/linhas_de_base.py --tabela
"""

from __future__ import annotations

import argparse
import json
from functools import partial
from pathlib import Path

from monstervale_ia.agentes import aleatorio, heuristico
from monstervale_ia.avaliacao import CABECALHO, Resultado, avaliar, melhor_humano, salvar
from monstervale_ia.dados_jogo import IDS_FASES, carregar_fase

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "resultados" / "linhas_de_base"
NOMES_CLASSES = {
    "archer": "arqueiros", "warrior": "guerreiros", "mage": "magos", "spearman": "lanceiros",
    "druid": "druidas", "monk": "monges", "rogue": "ladinos",
}
SEMENTES_ALEATORIO = list(range(30))
PERTURBACOES = list(range(10))


def rodar_fase(fase: str, processos: int) -> list[Resultado]:
    resultados = [
        avaliar(fase, "aleatório", partial(aleatorio, 0.3), SEMENTES_ALEATORIO, processos=processos),
        avaliar(fase, "heurístico", heuristico, [0]),
        avaliar(fase, "heurístico, perturbado", heuristico, [0], PERTURBACOES, processos=processos),
    ]
    for classe in carregar_fase(fase)["classes"]:
        resultados.append(avaliar(fase, f"só {NOMES_CLASSES[classe]}", partial(heuristico, [classe]), [0]))
    return resultados


def tabela() -> str:
    partes = [
        "# Linhas de base (M4)",
        "",
        "Gerado por `ferramentas/linhas_de_base.py`. Agentes sem rede neural, nas regras do commit fixado do jogo.",
        "",
        "- **aleatório:** sorteia entre as ações válidas (chama a onda com 30% de chance); 30 partidas.",
        "- **heurístico:** melhora o humano mais barato de melhorar; senão, posiciona colado na estrada,"
        " começando perto da vila e alternando as classes; senão, chama a onda. Determinístico: 1 partida.",
        "- **heurístico, perturbado:** o mesmo, em 10 variantes da fase com tempos de surgimento ±10% e"
        " ±1 monstro por grupo (decisão 12). Mede o quanto o resultado depende da partitura exata das ondas.",
        "- **só <classe>:** o heurístico usando uma classe só, como os robôs dos testes de balanceamento do jogo.",
        "- **melhor humano:** a melhor partida gravada da fase, repetida nas regras de hoje.",
        "",
        "Retorno = soma das recompensas (vitória perfeita com 3★ = +2,5; derrota sem vidas = −2).",
    ]
    for fase in IDS_FASES:
        arquivo = PASTA / f"{fase}.json"
        if not arquivo.exists():
            continue
        partes += ["", f"## {fase}", "", CABECALHO]
        for r in json.loads(arquivo.read_text()):
            partes.append(Resultado(**r).linha())
        humano = melhor_humano(fase)
        if humano:
            partes.append(
                f"| **melhor humano** | 1 | 100% | {'100%' if humano['estrelas'] == 3 else '0%'} | "
                f"{humano['estrelas']} | {humano['vidas']} | todas | "
                f"{-(20 - humano['vidas']) / 20 + 1 + 0.5 * humano['estrelas']:+.2f} | {humano['minutos']:.1f} |"
            )
    return "\n".join(partes) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("fases", nargs="*")
    parser.add_argument("--processos", type=int, default=2)
    parser.add_argument("--tabela", action="store_true")
    args = parser.parse_args()
    PASTA.mkdir(parents=True, exist_ok=True)
    for fase in args.fases:
        resultados = rodar_fase(fase, args.processos)
        salvar(resultados, PASTA / f"{fase}.json")
        print(f"## {fase}\n{CABECALHO}")
        for r in resultados:
            print(r.linha())
    if args.tabela:
        (RAIZ / "docs" / "linhas_de_base.md").write_text(tabela(), encoding="utf-8")
        print("docs/linhas_de_base.md atualizado")
