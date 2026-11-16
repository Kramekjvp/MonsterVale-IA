"""Valida o PPO no mini-TD (M5): o PPO tem que chegar perto do retorno ótimo.

Treina com algumas sementes, avalia a política gulosa e a sorteada em cada
traçado e compara com o ótimo calculado por força bruta.

Uso:
  uv run python ferramentas/treinar_mini_td.py --sementes 1 2 3 --passos 150000
  uv run tensorboard --logdir resultados/treinos   # curvas de aprendizado
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from monstervale_ia.mini_td import RETORNO_OTIMO, TIPOS_POR_CELULA, TRACADOS, MiniTD
from monstervale_ia.ppo import ConfigPPO, escolher, treinar

RAIZ = Path(__file__).resolve().parent.parent


def avaliar_mini_td(rede, partidas_por_tracado: int = 20, gulosa: bool = True, semente: int = 0) -> dict:
    rng = np.random.default_rng(semente)
    resultado = {}
    for tracado in range(len(TRACADOS)):
        env = MiniTD(tracados=[tracado])
        retornos = []
        for p in range(1 if gulosa else partidas_por_tracado):
            obs, _ = env.reset(seed=p)
            total = 0.0
            while True:
                obs, r, fim, _, _ = env.step(escolher(rede, obs, env.action_masks(), gulosa, rng))
                total += r
                if fim:
                    break
            retornos.append(total)
        resultado[f"tracado_{tracado}"] = float(np.mean(retornos))
    resultado["media"] = float(np.mean(list(resultado.values())))
    resultado["fracao_do_otimo"] = resultado["media"] / float(np.mean(list(RETORNO_OTIMO.values())))
    return resultado


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sementes", type=int, nargs="+", default=[1])
    parser.add_argument("--passos", type=int, default=150_000)
    parser.add_argument("--ambientes", type=int, default=8)
    parser.add_argument("--assincrono", action="store_true", help="coletor assíncrono (um processo por ambiente)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # no Windows, com a saída redirecionada, o padrão é cp1252

    resumo = {}
    for semente in args.sementes:
        config = ConfigPPO(
            total_passos=args.passos, n_ambientes=args.ambientes, passos_por_coleta=64,
            semente=semente, pasta=str(RAIZ / "resultados" / "treinos" / f"mini_td_s{semente}{'_assinc' if args.assincrono else ''}"),
            avaliar_a_cada=10, assincrono=args.assincrono, rede={"largura": 32, "camadas": 3, "oculta": 64},
        )
        rede, historico = treinar(
            MiniTD, TIPOS_POR_CELULA, config,
            avaliacao=lambda rede, passo: avaliar_mini_td(rede, gulosa=True),
        )
        for h in historico:
            if "avaliacao/media" in h:
                print(f"s{semente} passo {h['passo']:>7d}  retorno (treino) {h.get('partida/retorno', float('nan')):+.2f}"
                      f"  guloso {h['avaliacao/media']:+.2f}  entropia {h['entropia']:.2f}  kl {h['kl']:.4f}"
                      f"  {h['passos_por_segundo']:.0f} passos/s")
        gulosa = avaliar_mini_td(rede, gulosa=True)
        sorteada = avaliar_mini_td(rede, gulosa=False, partidas_por_tracado=50, semente=semente)
        resumo[semente] = {"gulosa": gulosa, "sorteada": sorteada}
        print(f"semente {semente}: gulosa {gulosa}\n            sorteada {sorteada}")
    saida = RAIZ / "resultados" / "mini_td_resumo.json"
    saida.write_text(json.dumps(resumo, indent=2), encoding="utf-8")
    print(f"ótimo: {RETORNO_OTIMO}  → {saida}")
