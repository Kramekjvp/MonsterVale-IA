"""Treina o PPO numa fase do Monstervale (M6: Fase 1).

A cada `--avaliar-a-cada` atualizações, a política gulosa joga uma partida
(o jogo é determinístico: uma basta) e o resultado vai para o TensorBoard.
A melhor rede pelo retorno guloso fica em `melhor_rede.pt`; a última, em
`rede.pt`; `checkpoint.pt` permite retomar um treino interrompido.

Uso:
  uv run python ferramentas/treinar_fase.py --fase level_01 --passos 2000000 --nome f1_s1
  uv run python ferramentas/treinar_fase.py --nome f1_s1 --retomar     # continua de onde parou, com a config salva
  uv run tensorboard --logdir resultados/treinos
  uv run python ferramentas/avaliar_agente.py resultados/treinos/f1_s1/melhor_rede.pt --fase level_01 --processos 8
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
from pathlib import Path

import numpy as np
import torch

from monstervale_ia.agentes import jogar
from monstervale_ia.ambiente import TIPOS_POR_CELULA, AmbienteMonstervale
from monstervale_ia.ppo import ConfigPPO, escolher, treinar

RAIZ = Path(__file__).resolve().parent.parent


def avaliar_gulosa(rede, passo: int, fase: str) -> dict:
    """Uma partida gulosa (determinística) com a rede atual."""
    rede.eval()

    def agir(env: AmbienteMonstervale, rng: np.random.Generator) -> int:
        return escolher(rede, env._observacao(), env.action_masks(), True, rng)

    r = jogar(AmbienteMonstervale(fase), agir, 0)
    rede.train()
    return {
        "retorno": r["retorno"], "estrelas": r["estrelas"], "vidas": r["vidas"],
        "onda": r["onda"], "venceu": float(r["estado"] == "won"),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fase", default="level_01")
    parser.add_argument("--nome", required=True, help="pasta em resultados/treinos/")
    parser.add_argument("--passos", type=int, default=2_000_000)
    parser.add_argument("--ambientes", type=int, default=24)
    parser.add_argument("--passos-por-coleta", type=int, default=128)
    parser.add_argument("--gamma", type=float, default=0.999)
    parser.add_argument("--taxa", type=float, default=2.5e-4)
    parser.add_argument("--entropia", type=float, default=0.01)
    parser.add_argument("--semente", type=int, default=1)
    parser.add_argument("--avaliar-a-cada", type=int, default=10, help="atualizações")
    parser.add_argument("--salvar-a-cada", type=int, default=10, help="atualizações")
    parser.add_argument("--retomar", action="store_true",
                        help="continua o treino da pasta com a config e a fase salvas (os outros argumentos são ignorados)")
    args = parser.parse_args()
    # No Windows, com a saída redirecionada (> log.txt), o padrão é cp1252, que não tem ★ nem →.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    pasta = RAIZ / "resultados" / "treinos" / args.nome
    if args.retomar:
        # A config original manda (passos, ambientes, gamma...): retomar com outra mudaria o treino no meio.
        salva = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
        config = ConfigPPO(**{**salva, "pasta": str(pasta)})
        args.fase = (pasta / "fase.txt").read_text(encoding="utf-8").strip()  # a fase não está na ConfigPPO
        print(f"retomando {pasta.name} em {args.fase} com a config salva"
              f" ({config.total_passos} passos, {config.n_ambientes} ambientes)")
    else:
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "fase.txt").write_text(args.fase, encoding="utf-8")
        config = ConfigPPO(
            total_passos=args.passos, n_ambientes=args.ambientes, passos_por_coleta=args.passos_por_coleta,
            gamma=args.gamma, taxa_aprendizado=args.taxa, coef_entropia=args.entropia,
            semente=args.semente, assincrono=True, dispositivo="auto", pasta=str(pasta),
            avaliar_a_cada=args.avaliar_a_cada, salvar_a_cada=args.salvar_a_cada, chave_melhor="retorno",
        )
    rede, historico = treinar(
        functools.partial(AmbienteMonstervale, args.fase), TIPOS_POR_CELULA, config,
        avaliacao=functools.partial(avaliar_gulosa, fase=args.fase), retomar=args.retomar,
    )
    for h in historico:
        if "avaliacao/retorno" in h:
            print(f"passo {h['passo']:>8d}  treino {h.get('partida/retorno', float('nan')):+.2f}"
                  f"  guloso {h['avaliacao/retorno']:+.2f} ({h['avaliacao/estrelas']:.0f}★,"
                  f" {h['avaliacao/vidas']:.0f} vidas)  entropia {h['entropia']:.2f}"
                  f"  {h['passos_por_segundo']:.0f} passos/s")
    print(f"CUDA: {torch.cuda.is_available()}  → {config.pasta}")
