# htr-ottoman

Reconnaissance d'écriture manuscrite (HTR) sur des manuscrits ottomans avec [kraken](https://kraken.re).

## Environnement

- macOS / Apple Silicon (backend PyTorch MPS)
- Environnement virtuel géré avec `uv` (`.venv/`)

```bash
source .venv/bin/activate
kraken --version
python scripts/check_mps.py
```

## Arborescence

- `data/` : images et transcriptions (non versionné)
- `models/` : modèles kraken téléchargés ou entraînés (non versionné)
- `scripts/` : scripts utilitaires
