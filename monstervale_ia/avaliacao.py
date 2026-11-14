"""Avaliação de agentes: resultados por fase, variante perturbada e régua humana.

Usado pelas linhas de base (M4) e, depois, para decidir se uma fase foi
"dominada" (decisão 12 do plano):

- a política gulosa vence com 3★, e
- a política com sorteio tira 3★ em ≥ 80% de 100 partidas;
- em todo relatório: robustez na variante perturbada e comparação com a
  melhor partida humana.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from monstervale_ia.agentes import Agente, jogar
from monstervale_ia.ambiente import AmbienteMonstervale
from monstervale_ia.dados_jogo import carregar_fase

RAIZ = Path(__file__).resolve().parent.parent
PARTIDAS_HUMANAS = RAIZ / "testes" / "referencias" / "partidas.json"
LIMIARES_ESTRELAS = [0.5, 0.9]


# --- Variante perturbada -----------------------------------------------------------------

def perturbar_fase(fase: dict, semente: int, tempo: float = 0.10, monstros: int = 1) -> dict:
    """Cópia da fase com cada grupo de cada onda levemente alterado.

    Intervalo e atraso de surgimento multiplicados por um valor em [1 − tempo, 1 + tempo];
    quantidade de monstros somada de −monstros a +monstros (mínimo 1). As regras e o
    mapa não mudam: só a "partitura" das ondas. Serve para medir se o agente
    joga ou só decorou a sequência exata de um jogo determinístico.
    """
    rng = np.random.default_rng(semente)
    nova = copy.deepcopy(fase)
    for onda in nova["waves"]:
        for grupo in onda["groups"]:
            grupo["interval"] = float(grupo["interval"]) * rng.uniform(1 - tempo, 1 + tempo)
            grupo["delay"] = float(grupo["delay"]) * rng.uniform(1 - tempo, 1 + tempo)
            grupo["count"] = max(1, int(grupo["count"]) + int(rng.integers(-monstros, monstros + 1)))
    return nova


def ambiente(fase: str, perturbacao: int | None = None, gravar: bool = False) -> AmbienteMonstervale:
    env = AmbienteMonstervale(fase, gravar=gravar)
    if perturbacao is not None:
        env._dados_fase = perturbar_fase(carregar_fase(fase), perturbacao)
    return env


# --- Resultados ---------------------------------------------------------------------------

@dataclass
class Resultado:
    fase: str
    agente: str
    partidas: int
    vitorias: float  # fração
    tres_estrelas: float  # fração
    estrelas_media: float
    vidas_media: float
    onda_media: float
    retorno_medio: float
    minutos_medio: float

    def linha(self) -> str:
        return (
            f"| {self.agente} | {self.partidas} | {self.vitorias:.0%} | {self.tres_estrelas:.0%} | "
            f"{self.estrelas_media:.2f} | {self.vidas_media:.1f} | {self.onda_media:.1f} | "
            f"{self.retorno_medio:+.2f} | {self.minutos_medio:.1f} |"
        )


CABECALHO = (
    "| Agente | Partidas | Vitórias | 3★ | Estrelas (média) | Vidas | Onda | Retorno | Minutos |\n"
    "|---|---|---|---|---|---|---|---|---|"
)


def _uma(args) -> dict:
    fase, fabrica, semente, perturbacao = args
    return jogar(ambiente(fase, perturbacao), fabrica(), semente)


def avaliar(
    fase: str,
    nome: str,
    fabrica: Callable[[], Agente],
    sementes: list[int],
    perturbacoes: list[int | None] | None = None,
    processos: int = 1,
) -> Resultado:
    """Joga uma partida por (semente, perturbação) e resume.

    `fabrica` cria um agente novo por partida (agentes podem guardar estado).
    Sem `perturbacoes`, usa o jogo original.
    """
    perturbacoes = perturbacoes or [None]
    tarefas = [(fase, fabrica, s, p) for p in perturbacoes for s in sementes]
    if processos > 1:
        with ProcessPoolExecutor(processos) as pool:
            resumos = list(pool.map(_uma, tarefas))
    else:
        resumos = [_uma(t) for t in tarefas]
    n = len(resumos)
    return Resultado(
        fase=fase, agente=nome, partidas=n,
        vitorias=sum(r["estado"] == "won" for r in resumos) / n,
        tres_estrelas=sum(r["estrelas"] == 3 for r in resumos) / n,
        estrelas_media=float(np.mean([r["estrelas"] for r in resumos])),
        vidas_media=float(np.mean([r["vidas"] for r in resumos])),
        onda_media=float(np.mean([r["onda"] for r in resumos])),
        retorno_medio=float(np.mean([r["retorno"] for r in resumos])),
        minutos_medio=float(np.mean([r["quadro"] for r in resumos])) / 3600,
    )


# --- Régua humana -------------------------------------------------------------------------

def estrelas_por_vidas(vidas: int, vidas_iniciais: int = 20) -> int:
    razao = vidas / vidas_iniciais
    return 3 if razao >= LIMIARES_ESTRELAS[1] else 2 if razao >= LIMIARES_ESTRELAS[0] else 1


def melhor_humano(fase: str) -> dict | None:
    """A melhor partida humana da fase, repetida nas regras de hoje (testes/referencias/partidas.json).

    Melhor = venceu com mais vidas; no empate, a mais rápida.
    """
    partidas = json.loads(PARTIDAS_HUMANAS.read_text())
    vitorias = [(nome, p) for nome, p in partidas.items() if p["level"] == fase and p["state"] == "won"]
    if not vitorias:
        return None
    nome, p = max(vitorias, key=lambda np_: (np_[1]["lives"], -np_[1]["frames"]))
    return {
        "partida": nome, "vidas": p["lives"], "estrelas": estrelas_por_vidas(p["lives"]),
        "ouro_final": p["gold"], "minutos": p["frames"] / 3600,
    }


def salvar(resultados: list[Resultado], caminho: Path) -> None:
    caminho.write_text(json.dumps([asdict(r) for r in resultados], indent=2), encoding="utf-8")
