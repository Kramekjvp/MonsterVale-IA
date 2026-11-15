"""PPO com máscara de ações, escrito do zero no estilo CleanRL (decisões 8 e 9).

O ciclo de treino, repetido até acabar o orçamento de passos:

1. COLETA: N ambientes jogam T passos cada com a política atual, guardando
   estado, máscara, ação, log-probabilidade, valor estimado e recompensa.
2. VANTAGEM (GAE): para cada passo, "quão melhor que o esperado" foi a ação:
       δ_t = r_t + γ·V(s_{t+1}) − V(s_t)
       A_t = δ_t + γ·λ·A_{t+1}
   γ (gamma) desconta o futuro; λ (lambda) troca viés por variância.
3. ATUALIZAÇÃO: algumas épocas de descida do gradiente em minilotes, com a
   perda do PPO:
       razão = π_novo(a|s) / π_velho(a|s)
       L_política = −mín(razão·A, recorte(razão, 1−ε, 1+ε)·A)
   O recorte (clip) impede a política de mudar demais de uma vez: é a "trava"
   que torna o PPO estável. Somam-se a perda do valor (erro quadrático contra
   o retorno) e um bônus de entropia (incentivo a continuar explorando).

Referência para conferir número por número:
https://github.com/vwxyzjn/cleanrl/blob/master/cleanrl/ppo.py
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
from torch import nn

from monstervale_ia.rede import NOTA_PROIBIDA, RedePolitica


@dataclass
class ConfigPPO:
    total_passos: int = 200_000  # passos de decisão somados em todos os ambientes
    n_ambientes: int = 8
    passos_por_coleta: int = 128  # T: passos de cada ambiente antes de cada atualização
    taxa_aprendizado: float = 2.5e-4
    anelar_taxa: bool = True  # a taxa cai linearmente até 0 no fim do treino
    gamma: float = 0.99
    lambda_gae: float = 0.95
    epocas: int = 4
    minilotes: int = 4
    recorte: float = 0.2  # ε do PPO
    coef_entropia: float = 0.01
    coef_valor: float = 0.5
    norma_max_gradiente: float = 0.5
    semente: int = 1
    assincrono: bool = False  # ambientes em processos separados (use no desktop)
    dispositivo: str = "auto"  # "auto", "cpu" ou "cuda"
    pasta: str = "resultados/treinos/teste"
    avaliar_a_cada: int = 0  # atualizações entre avaliações (0 = nunca)
    rede: dict = field(default_factory=dict)  # argumentos extras de RedePolitica

    @property
    def tamanho_lote(self) -> int:
        return self.n_ambientes * self.passos_por_coleta

    @property
    def atualizacoes(self) -> int:
        return max(1, self.total_passos // self.tamanho_lote)


def escolher_dispositivo(nome: str) -> torch.device:
    if nome == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(nome)


def _tensores(obs: dict, disp: torch.device) -> tuple[torch.Tensor, torch.Tensor]:
    return (
        torch.as_tensor(obs["grid"], dtype=torch.float32, device=disp),
        torch.as_tensor(obs["global"], dtype=torch.float32, device=disp),
    )


def criar_rede(env: gym.Env, tipos_por_celula: int, **kwargs) -> RedePolitica:
    espaco = env.observation_space
    return RedePolitica(
        canais_grid=espaco["grid"].shape[0],
        tamanho_global=espaco["global"].shape[0],
        tipos_por_celula=tipos_por_celula,
        **kwargs,
    )


def vantagens_gae(
    recompensas: np.ndarray, valores: np.ndarray, terminados: np.ndarray,
    valor_seguinte: np.ndarray, gamma: float, lambd: float,
) -> tuple[np.ndarray, np.ndarray]:
    """GAE. Arrays [T, N]; terminados[t] = a partida acabou NO passo t.

    Devolve (vantagens, retornos), com retornos = vantagens + valores (o alvo do valor).
    """
    t_total = recompensas.shape[0]
    vantagens = np.zeros_like(recompensas)
    ultima = np.zeros(recompensas.shape[1], dtype=np.float32)
    for t in reversed(range(t_total)):
        proximo_valor = valor_seguinte if t == t_total - 1 else valores[t + 1]
        continua = 1.0 - terminados[t]  # partida acabou: não há futuro para descontar
        delta = recompensas[t] + gamma * proximo_valor * continua - valores[t]
        ultima = delta + gamma * lambd * continua * ultima
        vantagens[t] = ultima
    return vantagens, vantagens + valores


class Registro:
    """Escreve métricas no TensorBoard e num CSV simples."""

    def __init__(self, pasta: Path) -> None:
        from torch.utils.tensorboard import SummaryWriter

        self.escritor = SummaryWriter(str(pasta))
        self.csv = (pasta / "metricas.csv").open("w", encoding="utf-8")
        self.csv.write("passo,nome,valor\n")

    def __call__(self, nome: str, valor: float, passo: int) -> None:
        self.escritor.add_scalar(nome, valor, passo)
        self.csv.write(f"{passo},{nome},{valor}\n")

    def fechar(self) -> None:
        self.escritor.close()
        self.csv.close()


def treinar(
    fabrica_env: Callable[[], gym.Env],
    tipos_por_celula: int,
    config: ConfigPPO,
    avaliacao: Callable[[RedePolitica, int], dict] | None = None,
) -> tuple[RedePolitica, list[dict]]:
    """Treina uma política e devolve (rede, histórico de atualizações)."""
    pasta = Path(config.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "config.json").write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    registro = Registro(pasta)

    np.random.seed(config.semente)
    torch.manual_seed(config.semente)
    disp = escolher_dispositivo(config.dispositivo)

    vetor = gym.vector.AsyncVectorEnv if config.assincrono else gym.vector.SyncVectorEnv
    # SAME_STEP: quando uma partida acaba, o próprio step já devolve o início da próxima.
    envs = vetor([fabrica_env] * config.n_ambientes, autoreset_mode=gym.vector.AutoresetMode.SAME_STEP)
    rede = criar_rede(envs.envs[0] if not config.assincrono else fabrica_env(), tipos_por_celula, **config.rede).to(disp)
    otimizador = torch.optim.Adam(rede.parameters(), lr=config.taxa_aprendizado, eps=1e-5)

    T, N = config.passos_por_coleta, config.n_ambientes
    espaco = envs.single_observation_space
    grids = torch.zeros((T, N, *espaco["grid"].shape), device=disp)
    globais = torch.zeros((T, N, *espaco["global"].shape), device=disp)
    n_acoes = envs.single_action_space.n
    mascaras = torch.zeros((T, N, n_acoes), dtype=torch.bool, device=disp)
    acoes = torch.zeros((T, N), dtype=torch.long, device=disp)
    logprobs = torch.zeros((T, N), device=disp)
    recompensas = np.zeros((T, N), dtype=np.float32)
    terminados = np.zeros((T, N), dtype=np.float32)
    valores = np.zeros((T, N), dtype=np.float32)

    obs, _ = envs.reset(seed=config.semente)
    grid, glob = _tensores(obs, disp)
    mascara = torch.as_tensor(np.stack(envs.call("action_masks")), device=disp)
    retorno_corrente = np.zeros(N)
    passos_corrente = np.zeros(N, dtype=int)
    passo_global = 0
    inicio = time.time()
    historico: list[dict] = []
    partidas_recentes: list[dict] = []

    for atualizacao in range(1, config.atualizacoes + 1):
        if config.anelar_taxa:
            fracao = 1.0 - (atualizacao - 1) / config.atualizacoes
            otimizador.param_groups[0]["lr"] = fracao * config.taxa_aprendizado

        # 1. COLETA ---------------------------------------------------------------
        for t in range(T):
            passo_global += N
            grids[t], globais[t], mascaras[t] = grid, glob, mascara
            with torch.no_grad():
                dist, valor = rede.distribuicao(grid, glob, mascara)
                acao = dist.sample()
            acoes[t], logprobs[t] = acao, dist.log_prob(acao)
            valores[t] = valor.cpu().numpy()

            obs, r, term, trunc, info = envs.step(acao.cpu().numpy())
            fim = np.logical_or(term, trunc)
            recompensas[t], terminados[t] = r, fim
            retorno_corrente += r
            passos_corrente += 1
            for i in np.flatnonzero(fim):
                partida = {"retorno": float(retorno_corrente[i]), "passos": int(passos_corrente[i])}
                final = info.get("final_info", {})
                for chave in ("estrelas", "vidas", "onda", "tracado"):
                    if chave in final and final.get(f"_{chave}", np.ones(N, bool))[i]:
                        partida[chave] = float(final[chave][i])
                partidas_recentes.append(partida)
                retorno_corrente[i] = 0.0
                passos_corrente[i] = 0
            grid, glob = _tensores(obs, disp)
            mascara = torch.as_tensor(np.stack(envs.call("action_masks")), device=disp)

        # 2. VANTAGEM (GAE) ---------------------------------------------------------
        with torch.no_grad():
            _, valor_seguinte = rede(grid, glob)
        vantagens, retornos = vantagens_gae(
            recompensas, valores, terminados, valor_seguinte.cpu().numpy(), config.gamma, config.lambda_gae
        )

        # 3. ATUALIZAÇÃO ---------------------------------------------------------------
        b_grid, b_glob = grids.reshape(-1, *grids.shape[2:]), globais.reshape(-1, *globais.shape[2:])
        b_mascara, b_acao, b_logp = mascaras.reshape(-1, n_acoes), acoes.reshape(-1), logprobs.reshape(-1)
        b_vant = torch.as_tensor(vantagens.reshape(-1), device=disp)
        b_ret = torch.as_tensor(retornos.reshape(-1), device=disp)
        tamanho_minilote = config.tamanho_lote // config.minilotes
        fracoes_recortadas, kls = [], []
        for _ in range(config.epocas):
            ordem = torch.randperm(config.tamanho_lote, device=disp)
            for inicio_ml in range(0, config.tamanho_lote, tamanho_minilote):
                ml = ordem[inicio_ml:inicio_ml + tamanho_minilote]
                dist, valor = rede.distribuicao(b_grid[ml], b_glob[ml], b_mascara[ml])
                logp_novo = dist.log_prob(b_acao[ml])
                log_razao = logp_novo - b_logp[ml]
                razao = log_razao.exp()
                with torch.no_grad():
                    kls.append(((razao - 1) - log_razao).mean().item())  # KL aproximado
                    fracoes_recortadas.append(((razao - 1).abs() > config.recorte).float().mean().item())

                vant = b_vant[ml]
                vant = (vant - vant.mean()) / (vant.std() + 1e-8)  # normalizar estabiliza o passo
                perda_politica = torch.max(
                    -vant * razao, -vant * torch.clamp(razao, 1 - config.recorte, 1 + config.recorte)
                ).mean()
                perda_valor = 0.5 * ((valor - b_ret[ml]) ** 2).mean()
                entropia = _entropia_mascarada(dist, b_mascara[ml]).mean()
                perda = perda_politica - config.coef_entropia * entropia + config.coef_valor * perda_valor

                otimizador.zero_grad()
                perda.backward()
                nn.utils.clip_grad_norm_(rede.parameters(), config.norma_max_gradiente)
                otimizador.step()

        # Registro ------------------------------------------------------------------
        var_ret = np.var(retornos)
        variancia_explicada = np.nan if var_ret == 0 else 1 - np.var(retornos - valores) / var_ret
        linha = {
            "atualizacao": atualizacao, "passo": passo_global,
            "passos_por_segundo": passo_global / (time.time() - inicio),
            "perda_politica": perda_politica.item(), "perda_valor": perda_valor.item(),
            "entropia": entropia.item(), "kl": float(np.mean(kls)),
            "fracao_recortada": float(np.mean(fracoes_recortadas)),
            "variancia_explicada": float(variancia_explicada),
            "taxa": otimizador.param_groups[0]["lr"],
        }
        if partidas_recentes:
            linha["partidas"] = len(partidas_recentes)
            for chave in partidas_recentes[0]:
                linha[f"partida/{chave}"] = float(np.mean([p[chave] for p in partidas_recentes if chave in p]))
            partidas_recentes = []
        if avaliacao and config.avaliar_a_cada and atualizacao % config.avaliar_a_cada == 0:
            for chave, valor_av in avaliacao(rede, passo_global).items():
                linha[f"avaliacao/{chave}"] = valor_av
        for chave, valor_l in linha.items():
            if chave not in ("atualizacao", "passo") and np.isfinite(valor_l):
                registro(chave, valor_l, passo_global)
        historico.append(linha)

    torch.save({"rede": rede.state_dict(), "config": asdict(config)}, pasta / "rede.pt")
    registro.fechar()
    envs.close()
    return rede, historico


def _entropia_mascarada(dist, mascara: torch.Tensor) -> torch.Tensor:
    """Entropia só das ações válidas (as proibidas têm probabilidade 0 e não contam)."""
    p = dist.probs
    logp = torch.where(mascara, dist.logits, torch.zeros_like(dist.logits))
    return -(p * logp).sum(-1)


@torch.no_grad()
def escolher(rede: RedePolitica, obs: dict, mascara: np.ndarray, gulosa: bool, rng=None, disp=None) -> int:
    """Uma ação para UM ambiente. Gulosa = a de maior probabilidade; senão, sorteada."""
    disp = disp or next(rede.parameters()).device
    grid = torch.as_tensor(obs["grid"][None], dtype=torch.float32, device=disp)
    glob = torch.as_tensor(obs["global"][None], dtype=torch.float32, device=disp)
    notas, _ = rede(grid, glob)
    notas = notas[0].masked_fill(~torch.as_tensor(mascara, device=disp), NOTA_PROIBIDA)
    if gulosa:
        return int(notas.argmax())
    gerador = None
    if rng is not None:
        gerador = torch.Generator(device=disp)
        gerador.manual_seed(int(rng.integers(2**31)))
    return int(torch.multinomial(torch.softmax(notas, 0), 1, generator=gerador))
