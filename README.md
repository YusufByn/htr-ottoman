# htr-ottoman

Reconnaissance d'écriture manuscrite (HTR) sur des manuscrits en turc ottoman avec [kraken](https://kraken.re) : le modèle OpenITI d'ottoman **imprimé** est affiné sur les manuscrits ottomans d'OpenITI MAKHZAN, puis sa généralisation est mesurée sur des manuscrits jamais vus. Projet de recherche et portfolio.

## Résultats

CER (taux d'erreur par caractère) calculé après la même fonction `normalize` sur la vérité terrain et les prédictions, sur la segmentation des annotateurs (reconnaissance seule). Intervalles à 95 % par bootstrap sur les manuscrits.

| Jeu | Modèle de départ | Modèle affiné (F8) |
|-----|-----------------:|-------------------:|
| Validation (2 manuscrits, 412 lignes) | 27,76 % | **16,32 %** |
| Test interne (ACDC-Evaluation, 17 manuscrits, 544 lignes) | 37,03 % [33,4 ; 41,8] | **26,33 % [22,9 ; 31,1]** |
| dont naskh (7 manuscrits) | 35,16 % | 23,70 % |
| dont autres écritures (10 manuscrits) | 38,41 % | 28,26 % |

Sur le test interne, évalué une seule fois avec un protocole pré-enregistré puis clos (décisions 37 et 39), le gain est de 10,7 points [9,6 ; 11,7] et les 17 manuscrits progressent. Le résultat principal de généralisation est ce test interne : aucun jeu externe ne remplit les critères (décision 41, [DATASETS.md](DATASETS.md)). Détails : [PROJECT.md](PROJECT.md), [EXPERIMENTS.md](EXPERIMENTS.md), synthèses [SYNTHESE_F12.md](SYNTHESE_F12.md) et [SYNTHESE_F13.md](SYNTHESE_F13.md).

## Modèle publié

`ota_naskh_makhzan_v0.1.0.safetensors` (CC BY-NC-SA 4.0), carte du modèle : [MODEL_CARD.md](MODEL_CARD.md). C'est F8 (décision 44), dont seul le drapeau « anciens polygones » a été corrigé dans l'en-tête ; poids identiques à l'octet au modèle évalué, prédictions de la validation identiques à l'octet sans aucun forçage (décision 45). Le modèle n'est pas versionné ici (`models/` hors git) : il est déposé sur Zenodo.

## Limites principales

Entraînement 100 % naskh ; aucun test d'une autre provenance (le test interne vient de MAKHZAN, comme l'entraînement) ; 2 757 lignes d'entraînement ; CER non comparable sans `normalize` ; sortie texte de `kraken ocr` 7.1.1 inversée sur nos ALTO (prédictions par l'API Python). Liste complète : [PROJECT.md](PROJECT.md), section 7, et [MODEL_CARD.md](MODEL_CARD.md).

## Environnement

- macOS / Apple Silicon (backend PyTorch MPS)
- Python 3.13, dépendances gérées par `uv` (`pyproject.toml` + `uv.lock`)

```bash
uv sync                              # recrée .venv/ à partir de uv.lock
uv run kraken --version
uv run python scripts/check_mps.py   # vérifie le backend MPS
uv run pytest                        # lance les tests
```

Les traitements sont des modules du package `htr_ottoman`, lancés par `uv run python -m htr_ottoman.<module>`. Chaîne complète (données, préparation, baseline, affinage, évaluation, analyses, publication) : [ARCHITECTURE.md](ARCHITECTURE.md), section 8. Par exemple :

```bash
uv run python -m htr_ottoman.data.makhzan                      # téléchargement de MAKHZAN (6,1 Go), table des lignes
uv run python -m htr_ottoman.prepare                           # jeux compilés pour kraken
uv run python -m htr_ottoman.train configs/f8_finetune.yml     # affinage F8 (4 h 38 sur MacBook Air, MPS)
uv run python -m htr_ottoman.evaluate reports/f8_finetune/val/predictions.parquet --split val --output-dir reports/f8_finetune/val
```

Documentation du projet : [PROJECT.md](PROJECT.md) (résumé, protocole, limites), [ROADMAP.md](ROADMAP.md) (tickets, avancement), [ARCHITECTURE.md](ARCHITECTURE.md) (code, flux des données), [DECISIONS.md](DECISIONS.md) (décisions méthodologiques), [EXPERIMENTS.md](EXPERIMENTS.md) (expériences), [DATASETS.md](DATASETS.md) (données ouvertes pour l'HTR ottoman manuscrit, recherche d'un test externe).

## Données

| Jeu | Version | Source | Licence | Emplacement |
|-----|---------|--------|---------|-------------|
| OpenITI MAKHZAN | 2026.1.2 (publiée le 2026-04-28) | Zenodo, DOI [10.5281/zenodo.19861912](https://doi.org/10.5281/zenodo.19861912) (concept DOI 10.5281/zenodo.16410105) | CC BY-NC-SA 4.0 | `data/raw/makhzan/` |
| Akis, jeu de test public (écarté comme test, décision 40) | commit `c7a6e5b425e640ef7ab2d85cd70c4e9fa1221838` (2024-09-14) | GitHub [verimsu/Akis-Ottoman-Dataset](https://github.com/verimsu/Akis-Ottoman-Dataset), zip stocké avec git LFS | Apache 2.0, citer Tasdemir et al., DAS 2024 | `data/raw/akis/` |

Téléchargement, extraction de la partie ottomane et table des lignes (idempotent, MD5 vérifiés) :

```bash
uv run python -m htr_ottoman.data.makhzan
```

Fichiers de la version 2026.1.2 (MD5 fournis par Zenodo) :

- `OpenITI-Makhzan_Data_2026-1-2.zip` (6,1 Go) : `347a06a5714091665b7292775840a0f0`
- `OpenITI-Makhzan_Metadata_2026-1-2.tsv` : `26e448803e90274a228ebee2a9df7e96`
- `OpenITI-Makhzan_ReleaseNotes_2026-1-2.pdf` : `490b22ec83b5e445c191c0bf671233e5`

Akis (vérification seulement, décision 40), téléchargé sans git-lfs depuis le serveur LFS de GitHub, SHA-256 vérifié contre le pointeur LFS :

```bash
uv run python -m htr_ottoman.data.akis
```

- `akis_dataset_test.zip` (584 379 296 octets) : SHA-256 `d98ddfc603c4a8c1b2a33775c5bdf3d41cbd86e24664e6435323665b2b12dbed`
- Citation : Tasdemir, Tandoğan, Akansu, Kızılırmak, Sen, Akcan, Kuru, Yanikoglu, « Automatic Transcription of Ottoman Documents Using Deep Learning », *Document Analysis Systems* (DAS 2024), Springer, p. 422-435, DOI 10.1007/978-3-031-70442-0_26.

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
- `reports/` : contenus dérivés de MAKHZAN (vérité terrain normalisée, prédictions, images de lignes de F13, statistiques), sous licence CC BY-NC-SA 4.0 comme la source ; détail et exceptions dans [reports/LICENCE.md](reports/LICENCE.md)

## Licences

| Contenu | Licence |
|---------|---------|
| Code (`src/`, `scripts/`, `tests/`, `configs/`) | MIT ([LICENSE](LICENSE)) |
| Contenus dérivés de MAKHZAN (`reports/`, `splits/`) | CC BY-NC-SA 4.0, comme MAKHZAN ; source, détail et exceptions dans [reports/LICENCE.md](reports/LICENCE.md) |
| Modèle publié `ota_naskh_makhzan_v0.1.0` (affiné sur MAKHZAN) | CC BY-NC-SA 4.0 ([MODEL_CARD.md](MODEL_CARD.md)) |
| Modèle de départ OpenITI ottoman imprimé (non redistribué, téléchargé par `htr_ottoman.base_model`) | CC0 1.0 |
| Données brutes MAKHZAN et Akis | non redistribuées (`data/` hors git) ; licences dans la section Données |
