# htr-ottoman

Reconnaissance d'écriture manuscrite (HTR) sur des manuscrits ottomans avec [kraken](https://kraken.re).

## Environnement

- macOS / Apple Silicon (backend PyTorch MPS)
- Python 3.13, dépendances gérées par `uv` (`pyproject.toml` + `uv.lock`)

```bash
uv sync                              # recrée .venv/ à partir de uv.lock
uv run kraken --version
uv run python scripts/check_mps.py   # vérifie le backend MPS
```

## Arborescence

- `data/` : images et transcriptions (non versionné)
- `models/` : modèles kraken téléchargés ou entraînés (non versionné)
- `scripts/` : scripts utilitaires
