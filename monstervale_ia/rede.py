"""A rede neural: política (o que fazer) e valor (quão boa é a situação). Decisão 5.

Formato
-------
Entrada: ``grid`` (C × A × L) e ``global`` (G). O vetor global é "pintado" em
todas as células (G canais constantes) e concatenado ao grid, para que cada
célula saiba o ouro, as vidas etc. na hora de dar a nota.

Tronco: convoluções 3×3 com ``padding=1``, que mantêm o tamanho A × L. Com 4
camadas, cada célula "enxerga" 9×9 células em volta (o alcance do arqueiro
nível 3 é ~3,5 células).

Cabeças:
- política espacial: convolução 1×1 → T mapas A × L (uma nota por tipo de ação
  e célula), achatados como ``tipo × (A·L) + y·L + x``, a mesma ordem das
  ações do ambiente;
- "chamar onda": média do tronco + vetor global → MLP → 1 nota;
- valor: média + máximo do tronco + vetor global → MLP → 1 número.

Por ser totalmente convolucional, a MESMA rede serve para grids 5×5 (mini-TD)
e 11×20 (Monstervale), e um mapa novo não exige mudar nada (etapa D).
"""

from __future__ import annotations

import torch
from torch import nn
from torch.distributions import Categorical

# Nota dada às ações proibidas pela máscara: na prática, probabilidade zero.
NOTA_PROIBIDA = -1e8


def _camada(entrada: int, saida: int) -> nn.Module:
    return nn.Sequential(nn.Conv2d(entrada, saida, 3, padding=1), nn.ReLU())


class RedePolitica(nn.Module):
    def __init__(
        self,
        canais_grid: int,
        tamanho_global: int,
        tipos_por_celula: int,
        largura: int = 64,
        camadas: int = 4,
        oculta: int = 128,
    ) -> None:
        super().__init__()
        self.tipos_por_celula = tipos_por_celula
        entrada = canais_grid + tamanho_global
        blocos = [_camada(entrada, largura)] + [_camada(largura, largura) for _ in range(camadas - 1)]
        self.tronco = nn.Sequential(*blocos)
        self.cabeca_espacial = nn.Conv2d(largura, tipos_por_celula, 1)
        self.cabeca_chamar = nn.Sequential(
            nn.Linear(largura + tamanho_global, oculta), nn.ReLU(), nn.Linear(oculta, 1)
        )
        self.cabeca_valor = nn.Sequential(
            nn.Linear(2 * largura + tamanho_global, oculta), nn.ReLU(), nn.Linear(oculta, 1)
        )
        # Inicialização do CleanRL: saídas da política começam quase iguais
        # (exploração uniforme), a do valor começa perto de 0.
        for camada in self.modules():
            if isinstance(camada, (nn.Conv2d, nn.Linear)):
                nn.init.orthogonal_(camada.weight, 2**0.5)
                nn.init.zeros_(camada.bias)
        nn.init.orthogonal_(self.cabeca_espacial.weight, 0.01)
        nn.init.orthogonal_(self.cabeca_chamar[-1].weight, 0.01)
        nn.init.orthogonal_(self.cabeca_valor[-1].weight, 1.0)

    def _tronco(self, grid: torch.Tensor, globais: torch.Tensor) -> torch.Tensor:
        n, _, a, l = grid.shape
        pintado = globais[:, :, None, None].expand(n, globais.shape[1], a, l)
        return self.tronco(torch.cat([grid, pintado], dim=1))

    def forward(self, grid: torch.Tensor, globais: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Devolve (notas de todas as ações [N, T·A·L + 1], valor [N])."""
        f = self._tronco(grid, globais)
        media = f.mean(dim=(2, 3))
        maximo = f.amax(dim=(2, 3))
        espacial = self.cabeca_espacial(f).flatten(1)  # [N, T, A, L] → [N, T·A·L]
        chamar = self.cabeca_chamar(torch.cat([media, globais], dim=1))
        valor = self.cabeca_valor(torch.cat([media, maximo, globais], dim=1)).squeeze(1)
        return torch.cat([espacial, chamar], dim=1), valor

    def distribuicao(self, grid, globais, mascara) -> tuple[Categorical, torch.Tensor]:
        """Distribuição só sobre as ações válidas (máscara), e o valor."""
        notas, valor = self(grid, globais)
        notas = notas.masked_fill(~mascara, NOTA_PROIBIDA)
        return Categorical(logits=notas), valor
