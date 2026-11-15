"""Avalia uma rede treinada pelo critério da decisão 12 do plano.

- Dominada = a gulosa vence com 3★ E a sorteada tira 3★ em ≥ 80% de 100 partidas.
- Robustez: a gulosa nas 10 variantes perturbadas da fase.
- Comparação com a melhor partida humana (vidas, ouro sobrando, minutos).

O arquivo da rede é o do treino: ``{"rede": state_dict, "config": asdict(ConfigPPO)}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache, partial
from pathlib import Path

import numpy as np
import torch

from monstervale_ia.agentes import Agente, jogar
from monstervale_ia.ambiente import TIPOS_POR_CELULA, AmbienteMonstervale
from monstervale_ia.avaliacao import Resultado, ambiente, avaliar, melhor_humano
from monstervale_ia.ppo import criar_rede, escolher
from monstervale_ia.rede import RedePolitica

SEMENTES_SORTEADA = list(range(100))
PERTURBACOES = list(range(10))
MINIMO_TRES_ESTRELAS = 0.80


def carregar_rede(caminho: str | Path, fase: str) -> RedePolitica:
    """Recria a rede a partir do arquivo salvo no treino (CPU, modo de avaliação)."""
    dados = torch.load(caminho, map_location="cpu", weights_only=False)
    rede = criar_rede(AmbienteMonstervale(fase), TIPOS_POR_CELULA, **dados["config"].get("rede", {}))
    rede.load_state_dict(dados["rede"])
    return rede.eval()


@lru_cache(maxsize=2)
def _rede_do_processo(caminho: str, fase: str) -> RedePolitica:
    """Carrega a rede uma vez por processo (a fábrica só leva o caminho, nunca a rede)."""
    torch.set_num_threads(1)
    return carregar_rede(caminho, fase)


def criar_agente(caminho: str, fase: str, gulosa: bool) -> Agente:
    rede = _rede_do_processo(caminho, fase)

    def agir(env: AmbienteMonstervale, rng: np.random.Generator) -> int:
        with torch.no_grad():
            return escolher(rede, env._observacao(), env.action_masks(), gulosa, rng)

    return agir


def fabrica_agente(caminho: str | Path, fase: str, gulosa: bool):
    """Fábrica serializável (partial de função de módulo) para ``avaliar`` com processos."""
    return partial(criar_agente, str(caminho), fase, gulosa)


@dataclass
class Veredito:
    dominada: bool
    gulosa_venceu_3_estrelas: bool
    tres_estrelas_sorteada: float
    minimo: float = MINIMO_TRES_ESTRELAS


def criterio_dominada(
    caminho: str | Path, fase: str, processos: int = 1, sementes: list[int] | None = None
) -> tuple[Resultado, Resultado, Veredito]:
    """Devolve (gulosa, sorteada, veredito). A gulosa joga a semente 0 (é determinística)."""
    gulosa = avaliar(fase, "rede gulosa", fabrica_agente(caminho, fase, True), [0])
    sorteada = avaliar(
        fase, "rede sorteada", fabrica_agente(caminho, fase, False),
        SEMENTES_SORTEADA if sementes is None else sementes, processos=processos,
    )
    gulosa_ok = gulosa.tres_estrelas == 1.0
    veredito = Veredito(gulosa_ok and sorteada.tres_estrelas >= MINIMO_TRES_ESTRELAS, gulosa_ok, sorteada.tres_estrelas)
    return gulosa, sorteada, veredito


def robustez_gulosa(caminho: str | Path, fase: str, processos: int = 1, perturbacoes: list[int] | None = None) -> Resultado:
    return avaliar(
        fase, "rede gulosa, perturbada", fabrica_agente(caminho, fase, True), [0],
        PERTURBACOES if perturbacoes is None else perturbacoes, processos=processos,
    )


def comparar_com_humano(gulosa: Resultado, fase: str) -> dict | None:
    humano = melhor_humano(fase)
    if humano is None:
        return None
    return {
        "humano": humano,
        "agente": {"vidas": gulosa.vidas_media, "ouro_final": gulosa.ouro_medio, "minutos": gulosa.minutos_medio},
    }


def exportar_partida_gulosa(caminho: str | Path, fase: str, destino: Path) -> Path:
    """Joga a gulosa gravando e salva a partida no formato do jogo (para o M7 assistir no Godot)."""
    env = ambiente(fase, gravar=True)
    jogar(env, criar_agente(str(caminho), fase, True), 0)
    return env.salvar_relatorio(destino)
