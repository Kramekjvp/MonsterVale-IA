"""Ambiente Gymnasium do Monstervale, no modo "por fase de construção" (decisão 4).

Como a rede joga
----------------
O tempo para entre as ondas. A cada passo do ambiente, a rede escolhe UMA ação:

- posicionar uma classe numa célula, melhorar ou dispensar o humano de uma
  célula: o tempo NÃO anda, a recompensa é 0 e a rede escolhe de novo;
- chamar a onda: a simulação roda (a 1/60 s por quadro) até a onda acabar
  (campo limpo) ou a partida terminar, e a rede recebe a recompensa da onda.

Para não ficar construindo para sempre, depois de ``max_acoes_por_construcao``
ações a única ação permitida é chamar a onda.

Ações (decisão 5): lista plana de ``9 × 220 + 1 = 1981`` posições
---------------------------------------------------------------------
``indice = tipo × 220 + y × 20 + x``, com tipo 0..6 = posicionar a classe
CLASSES[tipo], 7 = melhorar, 8 = dispensar; o último índice (1980) é chamar a
onda. A máscara (``action_masks()``) diz quais são válidas agora. Essa ordem
"tipo × célula" é a mesma da saída convolucional da rede: um mapa 20×11 de
notas por tipo de ação, achatado.

Estado (decisão 6)
------------------
``grid``: 12 canais 11×20 (construível, caminho, progresso na rota, rota da
próxima onda, classe do humano one-hot ×7, nível/3).
``global``: ouro, vidas, ondas, composição da próxima onda, classes liberadas,
custos, bônus de chamar agora e ações restantes nesta construção.

Recompensa (decisão 7)
----------------------
Por onda: −(vidas perdidas ÷ vidas iniciais). No fim: vitória +1 e +0,5 por
estrela; derrota −1. Nada por abates nem por ouro.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from monstervale_ia.dados_jogo import carregar_catalogo, carregar_fase
from monstervale_ia.mapa import Mapa
from monstervale_ia.relatorio import Relatorio
from monstervale_ia.simulacao import Simulacao

PASSO = 1.0 / 60.0
COLUNAS, LINHAS = 20, 11
CELULAS = COLUNAS * LINHAS
CLASSES = ["archer", "warrior", "mage", "spearman", "druid", "monk", "rogue"]
MONSTROS = [
    "goblin", "goblin_fast", "goblin_shield", "skeleton", "skeleton_knight",
    "slime", "slime_king", "slime_medium", "slime_small", "wolf",
]
TIPO_MELHORAR = len(CLASSES)  # 7
TIPO_DISPENSAR = len(CLASSES) + 1  # 8
TIPOS_POR_CELULA = len(CLASSES) + 2  # 9
ACAO_CHAMAR = TIPOS_POR_CELULA * CELULAS  # 1980
N_ACOES = ACAO_CHAMAR + 1  # 1981

CANAIS = [
    "construivel", "caminho", "progresso_rota", "rota_proxima_onda",
    *[f"classe_{c}" for c in CLASSES], "nivel",
]
N_GLOBAL = 1 + 1 + 1 + len(MONSTROS) + len(CLASSES) + len(CLASSES) + 1 + 1  # 29

# Escalas para deixar os números perto de [0, 1] (redes aprendem melhor assim).
ESCALA_OURO = 1000.0
ESCALA_MONSTROS = 50.0
ESCALA_CUSTO = 100.0
ESCALA_BONUS = 10.0
QUADROS_MAXIMOS_POR_ONDA = 60 * 60 * 10  # 10 minutos de jogo: só uma trava de segurança


@dataclass(frozen=True)
class Recompensas:
    vitoria: float = 1.0
    por_estrela: float = 0.5
    derrota: float = -1.0


def acao_para_texto(acao: int) -> str:
    """Descrição legível de uma ação (para depurar e para relatórios)."""
    if acao == ACAO_CHAMAR:
        return "chamar onda"
    tipo, celula = divmod(acao, CELULAS)
    y, x = divmod(celula, COLUNAS)
    if tipo < len(CLASSES):
        return f"posicionar {CLASSES[tipo]} em ({x},{y})"
    return f"{'melhorar' if tipo == TIPO_MELHORAR else 'dispensar'} ({x},{y})"


def indice_acao(tipo: int, x: int, y: int) -> int:
    return tipo * CELULAS + y * COLUNAS + x


class AmbienteMonstervale(gym.Env):
    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        fase: str = "level_01",
        max_acoes_por_construcao: int = 10,
        recompensas: Recompensas = Recompensas(),
        gravar: bool = False,
        render_mode: str | None = None,
    ) -> None:
        self.fase = fase
        self.max_acoes_por_construcao = max_acoes_por_construcao
        self.recompensas = recompensas
        self.gravar = gravar
        self.render_mode = render_mode
        self._catalogo = carregar_catalogo()
        self._dados_fase = carregar_fase(fase)
        self.mapa = Mapa.carregar(fase)
        self._canais_fixos, self._celulas_rotas = self._preparar_mapa()
        self._classes_liberadas = np.array(
            [c in self._dados_fase["classes"] for c in CLASSES], dtype=np.float32
        )
        self._custos = np.array(
            [float(self._catalogo["units"][c]["levels"][0]["cost"]) for c in CLASSES], dtype=np.float32
        )

        self.action_space = spaces.Discrete(N_ACOES)
        self.observation_space = spaces.Dict({
            "grid": spaces.Box(0.0, 1.0, shape=(len(CANAIS), LINHAS, COLUNAS), dtype=np.float32),
            "global": spaces.Box(0.0, np.inf, shape=(N_GLOBAL,), dtype=np.float32),
        })

        self.sim: Simulacao | None = None
        self.relatorio: Relatorio | None = None
        self.quadro = 0
        self._acoes_nesta_construcao = 0
        self.historico: list[tuple[int, int]] = []  # (quadro, ação): reproduz a partida inteira

    # --- API do Gymnasium -------------------------------------------------------

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)  # o jogo é determinístico; a semente só vale para quem sorteia ações
        self.sim = Simulacao(self._catalogo, self._dados_fase)
        self.sim.registrar_eventos = self.gravar
        self.relatorio = Relatorio(self.fase) if self.gravar else None
        self.quadro = 0
        self._acoes_nesta_construcao = 0
        self.historico = []
        return self._observacao(), self._info()

    def step(self, acao: int):
        assert self.sim is not None, "chame reset() antes de step()"
        acao = int(acao)
        if not self.action_masks()[acao]:
            raise ValueError(f"ação inválida agora: {acao_para_texto(acao)}")
        self.historico.append((self.quadro, acao))

        if acao != ACAO_CHAMAR:
            self._construir(acao)
            self._acoes_nesta_construcao += 1
            self._consumir_eventos()
            return self._observacao(), 0.0, False, False, self._info()

        vidas_antes = self.sim.vidas
        self.sim.chamar_onda()
        self._consumir_eventos()
        truncado = self._rodar_onda()
        self._acoes_nesta_construcao = 0

        recompensa = -(vidas_antes - self.sim.vidas) / self.sim.vidas_iniciais()
        terminou = self.sim.estado != "playing"
        if self.sim.estado == "won":
            recompensa += self.recompensas.vitoria + self.recompensas.por_estrela * self.sim.estrelas()
        elif self.sim.estado == "lost":
            recompensa += self.recompensas.derrota
        if (terminou or truncado) and self.relatorio is not None:
            self.relatorio.terminar(self.sim.estado, self.sim)
        return self._observacao(), float(recompensa), terminou, truncado, self._info()

    def action_masks(self) -> np.ndarray:
        """Quais das 1981 ações são válidas agora (formato usado pelo MaskablePPO)."""
        sim = self.sim
        mascara = np.zeros(N_ACOES, dtype=bool)
        if sim is None or sim.estado != "playing":
            return mascara
        mascara[ACAO_CHAMAR] = sim.pode_chamar_onda()
        if self._acoes_nesta_construcao >= self.max_acoes_por_construcao:
            return mascara
        for k, classe in enumerate(CLASSES):
            if not self._classes_liberadas[k] or sim.ouro < sim.custo_humano(classe):
                continue
            for x, y in self.mapa.construiveis:
                if sim.humano_em((x, y)) is None:
                    mascara[indice_acao(k, x, y)] = True
        for humano in sim.humanos:
            x, y = humano.celula
            if humano.pode_melhorar() and sim.ouro >= humano.custo_melhoria():
                mascara[indice_acao(TIPO_MELHORAR, x, y)] = True
            mascara[indice_acao(TIPO_DISPENSAR, x, y)] = True
        return mascara

    def render(self) -> str | None:
        if self.render_mode != "ansi" or self.sim is None:
            return None
        return self.desenho()

    # --- Ações ------------------------------------------------------------------

    def _construir(self, acao: int) -> None:
        tipo, celula = divmod(acao, CELULAS)
        y, x = divmod(celula, COLUNAS)
        if tipo < len(CLASSES):
            ok = self.sim.posicionar(CLASSES[tipo], (x, y)) is not None
        elif tipo == TIPO_MELHORAR:
            ok = self.sim.melhorar(self.sim.humano_em((x, y)))
        else:
            self.sim.dispensar(self.sim.humano_em((x, y)))
            ok = True
        # A máscara garante que só ações válidas chegam aqui; se falhar, é bug.
        assert ok, f"ação marcada como válida falhou: {acao_para_texto(acao)}"

    def _rodar_onda(self) -> bool:
        """Roda a simulação até a onda acabar. Devolve True se bateu na trava de tempo."""
        for _ in range(QUADROS_MAXIMOS_POR_ONDA):
            self.sim.passo(PASSO)
            self.quadro += 1
            self._consumir_eventos()
            if self.sim.estado != "playing" or self.sim.campo_limpo():
                return False
        return True

    def _consumir_eventos(self) -> None:
        if self.relatorio is not None:
            self.relatorio.consumir(self.sim.esvaziar_eventos(), self.sim)

    # --- Observação -------------------------------------------------------------

    def _preparar_mapa(self) -> tuple[np.ndarray, list[set]]:
        fixos = np.zeros((3, LINHAS, COLUNAS), dtype=np.float32)
        for x, y in self.mapa.construiveis:
            fixos[0, y, x] = 1.0
        celulas_rotas = []
        for i in range(len(self.mapa.rotas)):
            celulas = self.mapa.celulas_da_rota(i)
            celulas_rotas.append(set(celulas))
            for j, (x, y) in enumerate(celulas):
                fixos[1, y, x] = 1.0
                # 0 na entrada → 1 na vila; onde as rotas se juntam, vale o maior
                fixos[2, y, x] = max(fixos[2, y, x], j / max(len(celulas) - 1, 1))
        return fixos, celulas_rotas

    def _observacao(self) -> dict[str, np.ndarray]:
        sim = self.sim
        grid = np.zeros((len(CANAIS), LINHAS, COLUNAS), dtype=np.float32)
        grid[0:3] = self._canais_fixos
        for indice in sim.rotas_proxima_onda():
            for x, y in self._celulas_rotas[indice]:
                grid[3, y, x] = 1.0
        for humano in sim.humanos:
            x, y = humano.celula
            grid[4 + CLASSES.index(humano.tipo), y, x] = 1.0
            grid[4 + len(CLASSES), y, x] = humano.nivel / 3.0

        previa = sim.previa_proxima_onda()
        globais = np.concatenate([
            [sim.ouro / ESCALA_OURO,
             sim.vidas / sim.vidas_iniciais(),
             sim.ondas_iniciadas() / sim.total_ondas()],
            [previa.get(m, 0) / ESCALA_MONSTROS for m in MONSTROS],
            self._classes_liberadas,
            self._custos / ESCALA_CUSTO,
            [sim.bonus_chamada_antecipada() / ESCALA_BONUS,
             (self.max_acoes_por_construcao - self._acoes_nesta_construcao) / self.max_acoes_por_construcao],
        ]).astype(np.float32)
        return {"grid": grid, "global": globais}

    def _info(self) -> dict[str, Any]:
        sim = self.sim
        return {
            "fase": self.fase,
            "quadro": self.quadro,
            "onda": sim.ondas_iniciadas(),
            "vidas": sim.vidas,
            "ouro": sim.ouro,
            "estado": sim.estado,
            "estrelas": sim.estrelas() if sim.estado == "won" else 0,
            "mascara": self.action_masks(),
        }

    # --- Visualização e gravação -------------------------------------------------

    def desenho(self) -> str:
        """O mapa em texto, com os humanos: letra da classe e nível (A2 = arqueiro nível 2)."""
        letras = {"archer": "A", "warrior": "G", "mage": "M", "spearman": "L", "druid": "D", "monk": "N", "rogue": "R"}
        linhas = self.mapa.desenho().split("\n")
        grade = [list(l) for l in linhas]
        for humano in self.sim.humanos:
            x, y = humano.celula
            grade[y + 1][x + 3] = letras[humano.tipo] if humano.nivel == 1 else str(humano.nivel)
        cabecalho = (
            f"{self.fase}  onda {self.sim.ondas_iniciadas()}/{self.sim.total_ondas()}  "
            f"vidas {self.sim.vidas}  ouro {self.sim.ouro}  ({self.sim.estado})"
        )
        return "\n".join([cabecalho, *("".join(l) for l in grade)])

    def salvar_relatorio(self, caminho: Path, para_repetir: bool = True) -> Path:
        """Grava a partida no formato do jogo (precisa de gravar=True).

        Com ``para_repetir``, ajusta os tempos para o jogador gravado do jogo
        (jogo/tests/e2e/recorded_player.gd) repetir a partida no mesmo quadro:
        ele anota o início de cada onda no passo SEGUINTE ao da chamada, e mede
        as ações a partir daí, ou seja, um quadro atrasado. As ações de onda ≥ 1
        saem com 1/60 s a menos, o que cancela o atraso exatamente.
        """
        if self.relatorio is None:
            raise RuntimeError("crie o ambiente com gravar=True para salvar relatórios")
        if self.relatorio.resultado == "playing" and self.sim.estado != "playing":
            self.relatorio.terminar(self.sim.estado, self.sim)
        if para_repetir:
            for acao in self.relatorio.acoes:
                if acao["wave"] >= 1 and not acao.get("_ajustada"):
                    acao["time"] -= PASSO
                    acao["_ajustada"] = True
        caminho = self.relatorio.salvar(caminho)
        return caminho

    def historico_como_roteiro(self) -> list[list]:
        """O histórico de ações no formato de monstervale_ia/roteiro.py (quadro, ação, ...)."""
        roteiro = []
        for quadro, acao in self.historico:
            if acao == ACAO_CHAMAR:
                roteiro.append([quadro, "call"])
                continue
            tipo, celula = divmod(acao, CELULAS)
            y, x = divmod(celula, COLUNAS)
            if tipo < len(CLASSES):
                roteiro.append([quadro, "place", CLASSES[tipo], x, y])
            else:
                roteiro.append([quadro, "upgrade" if tipo == TIPO_MELHORAR else "dismiss", x, y])
        return roteiro
