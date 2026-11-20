"""Ambientes falsos para testar o coletor assíncrono. NÃO importe torch aqui (o filho importa este módulo)."""

from __future__ import annotations

import os

from monstervale_ia.mini_td import MiniTD


class MorreNoPasso(MiniTD):
    """Mata o processo sem aviso no n-ésimo step (como o Windows matando por falta de memória)."""

    def __init__(self, passo_fatal: int = 3) -> None:
        super().__init__()
        self.passo_fatal = passo_fatal
        self.passos = 0

    def step(self, acao):
        self.passos += 1
        if self.passos >= self.passo_fatal:
            os._exit(3)
        return super().step(acao)


class FalhaNoPasso(MiniTD):
    def step(self, acao):
        raise ValueError("falha de mentira no step")


def fabrica_que_levanta():
    raise ValueError("falha de mentira na criação")


def fabrica_que_morre():
    os._exit(5)
