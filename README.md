# htr-ottoman

Reconnaissance d'écriture manuscrite (HTR) sur des manuscrits ottomans avec [kraken](https://kraken.re).

## Environnement

- macOS / Apple Silicon (backend PyTorch MPS)
- Python 3.13, dépendances gérées par `uv` (`pyproject.toml` + `uv.lock`)

```bash
uv sync                              # recrée .venv/ à partir de uv.lock
uv run kraken --version
uv run python scripts/check_mps.py   # vérifie le backend MPS
uv run pytest                        # lance les tests
```

Les traitements sont des modules du package `htr_ottoman` :

```bash
uv run python -m htr_ottoman.analysis.inventory_ottoman        # -> reports/ottoman_inventory.csv
uv run python -m htr_ottoman.analysis.compare_ottoman_sources  # Research vs ACDC-Evaluation
```

Documentation du projet : [PROJECT.md](PROJECT.md) (résumé, protocole), [ROADMAP.md](ROADMAP.md) (tickets, avancement), [ARCHITECTURE.md](ARCHITECTURE.md) (code, flux des données), [DECISIONS.md](DECISIONS.md) (décisions méthodologiques), [EXPERIMENTS.md](EXPERIMENTS.md) (expériences).

## Données

| Jeu | Version | Source | Licence | Emplacement |
|-----|---------|--------|---------|-------------|
| OpenITI MAKHZAN | 2026.1.2 (publiée le 2026-04-28) | Zenodo, DOI [10.5281/zenodo.19861912](https://doi.org/10.5281/zenodo.19861912) (concept DOI 10.5281/zenodo.16410105) | CC BY-NC-SA 4.0 | `data/raw/makhzan/` |

Fichiers de la version 2026.1.2 (MD5 fournis par Zenodo) :

- `OpenITI-Makhzan_Data_2026-1-2.zip` (6,1 Go) : `347a06a5714091665b7292775840a0f0`
- `OpenITI-Makhzan_Metadata_2026-1-2.tsv` : `26e448803e90274a228ebee2a9df7e96`
- `OpenITI-Makhzan_ReleaseNotes_2026-1-2.pdf` : `490b22ec83b5e445c191c0bf671233e5`

## Arborescence

Détail dans [ARCHITECTURE.md](ARCHITECTURE.md).

- `configs/` : paramètres des expériences
- `data/` : données (non versionné) ; `raw/` en lecture seule, `interim/`, `processed/`
- `models/` : modèles kraken téléchargés ou entraînés (non versionné)
- `splits/` : découpages train/val/test figés
- `src/htr_ottoman/` : package Python, traitements de données
- `scripts/` : utilitaires (vérification d'environnement, etc.)
- `notebooks/` : exploration visuelle uniquement
- `tests/` : tests automatiques
- `reports/` : métadonnées dérivées de MAKHZAN (inventaires, statistiques), sous licence CC BY-NC-SA 4.0 comme la source
