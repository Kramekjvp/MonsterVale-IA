"""Mede a velocidade da simulação e do ambiente numa carga fixa e representativa.

Carga: o heurístico jogando as 5 fases inteiras (muitos monstros e humanos,
fim de jogo pesado) + 20 partidas do aleatório na Fase 1 (o começo do treino).

Uso:
  uv run python ferramentas/medir_velocidade.py            # tempo e quadros/s
  uv run python ferramentas/medir_velocidade.py --perfil   # onde o tempo vai (cProfile)
"""

import argparse
import cProfile
import pstats
import time

from monstervale_ia.agentes import aleatorio, heuristico, jogar
from monstervale_ia.ambiente import AmbienteMonstervale
from monstervale_ia.dados_jogo import IDS_FASES


def carga() -> tuple[int, int]:
    quadros = passos = 0
    for fase in IDS_FASES:
        env = AmbienteMonstervale(fase)
        r = jogar(env, heuristico())
        quadros += r["quadro"]
        passos += len(env.historico)
    for semente in range(20):
        env = AmbienteMonstervale("level_01")
        r = jogar(env, aleatorio(0.3), semente)
        quadros += r["quadro"]
        passos += len(env.historico)
    return quadros, passos


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--perfil", action="store_true")
    args = parser.parse_args()
    if args.perfil:
        perfil = cProfile.Profile()
        perfil.enable()
        carga()
        perfil.disable()
        pstats.Stats(perfil).sort_stats("tottime").print_stats(22)
    else:
        inicio = time.perf_counter()
        quadros, passos = carga()
        dt = time.perf_counter() - inicio
        print(f"{dt:.1f} s | {quadros} quadros = {quadros / dt:,.0f} quadros/s | {passos} decisões = {passos / dt:,.0f} decisões/s")
