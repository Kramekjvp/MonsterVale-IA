"""Relatório de partida no formato do jogo. Port de ``jogo/src/core/match_log.gd``.

Consome os eventos da simulação e monta o mesmo JSON que o Monstervale grava
em ``user://partidas``. Com isso, uma partida jogada pela rede pode ser
repetida no próprio jogo pelo jogador gravado (``tests/e2e/recorded_player.gd``)
e assistida com arte e som.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class Relatorio:
    def __init__(self, id_fase: str, inicio: str | None = None) -> None:
        self.id_fase = id_fase
        self.inicio = inicio or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self.resultado = "playing"
        self.duracao = 0.0
        self.vidas_finais = 0
        self.ouro_final = 0
        self.estrelas = 0
        self.acoes: list[dict] = []
        self.ondas: list[dict] = []

    def consumir(self, eventos: list[dict], sim) -> None:
        for evento in eventos:
            tipo = evento["type"]
            if tipo == "unit_placed":
                self._acao("place", evento)
            elif tipo == "unit_upgraded":
                self._acao("upgrade", evento)
            elif tipo == "unit_dismissed":
                self._acao("dismiss", evento)
            elif tipo == "wave_started":
                self._abrir_onda(evento, sim)
            elif tipo == "wave_cleared":
                self._fechar_onda(evento)
            elif tipo == "monster_spawned":
                self._contar(evento["monster"], "spawned")
            elif tipo == "monster_killed":
                self._contar(evento["monster"], "killed")
                onda = self._onda_de(evento["monster"])
                if onda is not None:
                    onda["kill_gold"] += evento["monster"].ouro + int(evento.get("bonus_gold", 0))
            elif tipo == "monster_escaped":
                self._contar(evento["monster"], "escaped")
                onda = self._onda_de(evento["monster"])
                if onda is not None:
                    onda["lives_end"] = evento["lives"]
            elif tipo == "monster_hit":
                onda = self._onda_de(evento["monster"])
                if onda is not None:
                    onda["damage"][evento["source"]] = onda["damage"].get(evento["source"], 0) + evento["damage"]
            elif tipo == "unit_down":
                if self.ondas:
                    self.ondas[-1]["units_down"] += 1

    def terminar(self, resultado: str, sim) -> None:
        self.resultado = resultado
        self.duracao = sim.tempo
        self.vidas_finais = sim.vidas
        self.ouro_final = sim.ouro
        self.estrelas = sim.estrelas() if resultado == "won" else 0

    def como_dict(self) -> dict:
        return {
            "level": self.id_fase,
            "started_at": self.inicio,
            "result": self.resultado,
            "duration": self.duracao,
            "lives_final": self.vidas_finais,
            "gold_final": self.ouro_final,
            "stars": self.estrelas,
            "actions": [{k: v for k, v in a.items() if not k.startswith("_")} for a in self.acoes],
            "waves": self.ondas,
        }

    def salvar(self, caminho: Path) -> Path:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(self.como_dict(), indent=2), encoding="utf-8")
        return caminho

    def _acao(self, acao: str, evento: dict) -> None:
        humano = evento["unit"]
        self.acoes.append({
            "time": evento["time"],
            "action": acao,
            "unit": humano.tipo,
            "cell": [humano.celula[0], humano.celula[1]],
            "level": humano.nivel,
            "gold_after": evento["gold"],
            "wave": evento["waves_started"],
        })

    def _abrir_onda(self, evento: dict, sim) -> None:
        defensores: dict[str, int] = {}
        for humano in sim.humanos:
            chave = f"{humano.tipo} {humano.nivel}"
            defensores[chave] = defensores.get(chave, 0) + 1
        self.ondas.append({
            "number": evento["number"],
            "started_at": evento["time"],
            "cleared_at": None,
            "called_early": evento["called_early"],
            "early_bonus": evento["early_bonus"],
            "gold_start": evento["gold"],
            "gold_end": None,
            "lives_start": evento["lives"],
            "lives_end": evento["lives"],
            "defenders": defensores,
            "spawned": {},
            "killed": {},
            "escaped": {},
            "damage": {},
            "kill_gold": 0,
            "bonus": 0,
            "units_down": 0,
        })

    def _fechar_onda(self, evento: dict) -> None:
        onda = self.ondas[evento["number"] - 1]
        onda["cleared_at"] = evento["time"]
        onda["gold_end"] = evento["gold"]
        onda["lives_end"] = evento["lives"]
        onda["bonus"] = evento["bonus"]

    def _onda_de(self, monstro) -> dict | None:
        if monstro.onda is None:
            return None
        return self.ondas[monstro.onda["number"] - 1]

    def _contar(self, monstro, campo: str) -> None:
        onda = self._onda_de(monstro)
        if onda is not None:
            onda[campo][monstro.tipo] = onda[campo].get(monstro.tipo, 0) + 1
