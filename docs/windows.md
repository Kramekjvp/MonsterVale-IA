# Rodar no Windows (desktop com a GTX 1650)

O WSL2 do desktop não inicia ("Falha catastrófica", `Wsl/Service/E_UNEXPECTED`, mesmo na versão estável 3.0.3), então o treino roda **direto no Windows**. O projeto é Python puro, e o Godot não é necessário para treinar (só para regenerar as respostas douradas e, no M7, para assistir à rede).

## 1. Programas (uma vez)

1. **Driver NVIDIA ≥ 580** (nvidia.com/drivers). Confira no PowerShell: `nvidia-smi`.
2. **Git for Windows**: git-scm.com. Também é necessário para o Claude Code.
3. **uv**, no PowerShell:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   Feche e abra o PowerShell depois.

## 2. Projeto

```powershell
cd $HOME
git clone --recurse-submodules https://github.com/Kramekjvp/MonsterVale-IA.git
cd MonsterVale-IA
uv sync
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
uv run pytest -m "not lento"
```

- O `uv sync` baixa o PyTorch com CUDA 13.2 de `download.pytorch.org` (configurado no `pyproject.toml`; o PyTorch do PyPI para Windows é só CPU). São alguns GB na primeira vez.
- No primeiro `uv sync`, o `uv` **atualiza o `uv.lock`** (a nuvem onde o projeto começou não acessa o repositório do PyTorch). Faça commit do `uv.lock` atualizado.
- O teste do PyTorch tem que mostrar `True NVIDIA GeForce GTX 1650`. Se der `False`, quase sempre é o driver.

## 3. Claude Code

Instale o Claude Code para Windows (docs.claude.com) e abra-o na pasta `MonsterVale-IA`. Ele lê o `CLAUDE.md`.

## Diferenças do Windows que o código precisa respeitar

- **Processos:** no Windows, os processos novos começam do zero (*spawn*), sem copiar o processo pai. Todo script que usa `ConfigPPO(assincrono=True)` ou `avaliar(..., processos>1)` precisa do bloco `if __name__ == "__main__":`, e as fábricas de ambiente precisam ser serializáveis (`functools.partial(AmbienteMonstervale, "level_01")`, não `lambda`).
- **Codificação:** sempre `encoding="utf-8"` ao ler e gravar texto (o padrão do Windows é cp1252).
- **Caminhos:** use `pathlib.Path`, nunca barras escritas à mão.
