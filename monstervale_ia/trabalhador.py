"""Processo de UM ambiente do coletor assíncrono.

Este módulo NÃO pode importar torch (nem nada que importe, como ppo.py e rede.py): o spawn
do Windows cria um interpretador novo por filho, e cada import de torch reserva ~1,3 GB de
memória "commit". Com 24 ambientes isso esgotou o commit e os filhos morreram na importação.
"""

from __future__ import annotations

import os
import sys
import traceback

import numpy as np

CHAVES_FINAIS = ("estrelas", "vidas", "onda", "tracado")


def trabalhador(conexao, fabrica_env, semente: int) -> None:
    """Recebe ações, faz step e o autoreset, devolve tudo de uma vez.

    Protocolo: primeiro manda ("pronto", diagnostico, obs, mascara) (o handshake, depois de
    criar e resetar o ambiente); depois, para cada ("passo", acao), manda
    (obs, mascara, r, term, trunc, info_final). Em erro manda ("erro", traceback).
    """
    try:
        env = fabrica_env()
        obs, _ = env.reset(seed=semente)
        diagnostico = {"pid": os.getpid(), "torch_importado": "torch" in sys.modules}
        conexao.send(("pronto", diagnostico, obs, np.asarray(env.action_masks(), dtype=bool)))
        while True:
            comando, acao = conexao.recv()
            if comando == "fechar":
                break
            obs, r, term, trunc, info = env.step(acao)
            info_final = None
            if term or trunc:
                info_final = {c: float(info[c]) for c in CHAVES_FINAIS if c in info}
                obs, _ = env.reset()  # autoreset (SAME_STEP): o obs devolvido já é o da próxima partida
            conexao.send((obs, np.asarray(env.action_masks(), dtype=bool), float(r), bool(term), bool(trunc), info_final))
        env.close()
    except BaseException:  # noqa: BLE001 - o principal precisa saber por que o trabalhador morreu
        try:
            conexao.send(("erro", traceback.format_exc()))
        except Exception:
            pass
    finally:
        conexao.close()
