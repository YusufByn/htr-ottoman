# Architecture

Structure du code et flux des données. Mis à jour à chaque étape terminée.
Dernière mise à jour : 2026-09-28.

## 1. Vue d'ensemble

```
data/raw/makhzan/  (zip + TSV, lecture seule)
   │
   ├──> analysis ───────────────────────────────> reports/  (inventaires, comparaisons)
   │
   └──> data (extraction, à venir) ──> data/interim/  (images + ALTO par manuscrit)
                                          │
              splits (à venir) ──> splits/│  (listes train / val / test figées)
                                          │
       normalize (NFD + 6 règles), appliqué en F4
                                          v
                                   data/processed/  (jeux prêts pour kraken, par split)
                                          │
                        train (à venir) ──> models/  (modèles affinés)
                                          │
                     evaluate (à venir) ──> reports/ + EXPERIMENTS.md  (CER)
```

Le pipeline part toujours de `data/raw/`, qui n'est jamais modifié. Chaque étape lit la sortie de la précédente et écrit dans son propre dossier.

## 2. Arborescence

```
htr-ottoman/
├── configs/              paramètres d'une expérience (YAML), un fichier par expérience
├── data/                 hors git
│   ├── raw/              sources telles que téléchargées, en lecture seule (chmod a-w)
│   ├── interim/          zips décompressés, ALTO bruts, avant normalisation
│   └── processed/        données prêtes pour kraken (ALTO normalisés NFD, jeux compilés par split)
├── models/               modèle de départ et modèles entraînés (hors git)
├── notebooks/            exploration visuelle uniquement, aucun code du pipeline n'en dépend
├── reports/              inventaires, métriques (versionné, CC BY-NC-SA)
│   └── figures/          graphiques générés par les modules d'analyse
├── scripts/              utilitaires (vérification d'environnement)
├── splits/               listes train/val/test figées, avec la seed (versionné)
├── src/htr_ottoman/      package Python du projet
│   ├── config.py         chemins du projet, définis une seule fois
│   ├── data/             téléchargement, extraction, lecture ALTO et métadonnées
│   ├── analysis/         inventaires et comparaisons descriptives
│   ├── normalize.py      l'unique fonction de normalisation (NFD + règles documentées)
│   ├── splits.py         (à venir) création des splits par œuvre
│   ├── train.py          (à venir) fine-tuning kraken piloté par une config
│   └── evaluate.py       (à venir) CER global, par écriture et par relecture
├── tests/                tests automatiques (pytest)
└── pyproject.toml, uv.lock, README.md, CLAUDE.md, DECISIONS.md, EXPERIMENTS.md, ARCHITECTURE.md, PROJECT.md
```

## 3. Flux des données

| Étape | Module | Entrées | Sorties | État |
|-------|--------|---------|---------|------|
| Téléchargement | `data` (à venir) | Zenodo, DOI 10.5281/zenodo.19861912 | `data/raw/makhzan/` + vérification MD5 | fait à la main le 2026-09-25 (voir README), module à venir |
| Inventaire | `analysis.inventory_ottoman` | TSV de métadonnées | `reports/ottoman_inventory.csv` | fait |
| Comparaison des sources | `analysis.compare_ottoman_sources` | TSV de métadonnées | sortie console | fait |
| Inventaire des caractères | `analysis.char_inventory` | zip MAKHZAN (ALTO lus dans le zip, lecture seule), TSV | `reports/ottoman_characters.csv` | fait |
| Extraction | `data` (à venir) | zip MAKHZAN, TSV | `data/interim/` | à venir |
| Découpage | `splits` (à venir) | TSV, décisions 1, 3, 6, 7 | `splits/` | à venir |
| Normalisation | `normalize` (fonction faite, appliquée aux données en F4) | `data/interim/` | `data/processed/` | à venir (F4) |
| Entraînement | `train` (à venir) | `data/processed/`, `configs/`, modèle de départ | `models/` | à venir |
| Évaluation | `evaluate` (à venir) | modèle, jeux val / test | `reports/`, `EXPERIMENTS.md` | à venir |

## 4. Modules du package

| Module | Responsabilité | Point d'entrée | État |
|--------|----------------|----------------|------|
| `config` | Chemins du projet (`ROOT`, `DATA_RAW`, `SPLITS`, `REPORTS`, fichiers MAKHZAN). Tous les modules les importent d'ici. | aucun | fait |
| `analysis.inventory_ottoman` | Une ligne par manuscrit ottoman : titre, pages, écritures, langues, source, relecture, lignes, pages en couche modèle. S'arrête si une couche de transcription inconnue apparaît. | `uv run python -m htr_ottoman.analysis.inventory_ottoman` | fait |
| `analysis.compare_ottoman_sources` | Research contre ACDC-Evaluation : pages, lignes, écritures, relecture ; lignes par manuscrit et par œuvre. | `uv run python -m htr_ottoman.analysis.compare_ottoman_sources` | fait |
| `analysis.char_inventory` | Une ligne par caractère des lignes ottomanes : point de code, nom et catégorie Unicode, occurrences, lignes, manuscrits, Research / ACDC-Evaluation. Signale les anomalies d'espacement. Fournit aussi `iter_lines`, utilisé par les tests. | `uv run python -m htr_ottoman.analysis.char_inventory` | fait |
| `data` | Téléchargement avec vérification MD5, extraction, lecture ALTO. | à venir | à venir |
| `normalize` | `normalize(text)` : applique dans l'ordre les règles de `RULES` (1 NFD, 2 marques de direction, 3 voyelles, 4 ک→ك, 5 ی selon la position, 6 ZWNJ répétés, 7 espaces), puis NFD. Sortie toujours NFD, idempotente. Une fonction par règle, docstring et décision associées (5, 9 à 14). | import `from htr_ottoman.normalize import normalize` | fait |
| `splits` | Découpage par œuvre avec seed, écrit dans `splits/`. | à venir | à venir |
| `train` | Fine-tuning kraken à partir d'un fichier de `configs/`. | à venir | à venir |
| `evaluate` | CER global, par écriture et par catégorie de relecture. | à venir | à venir |

## 5. Configurations

À venir. Un fichier YAML par expérience dans `configs/`, lu par `train` et `evaluate`.

## 6. Conventions

- **Chemins** : toujours importés de `htr_ottoman.config`, jamais écrits en dur dans un module.
- **Données brutes** : `data/raw/` est en lecture seule (`chmod a-w`) ; aucun module n'y écrit.
- **Identifiants** : les fichiers MAKHZAN sont nommés `<DocID>_<DocPartID>.jpg` / `.xml` ; un Doc ID est un document eScriptorium, une œuvre est identifiée par `Title of Text` (décision 6).
- **Normalisation** : appliquée en un seul point, par `normalize`, à la vérité terrain et aux prédictions (décisions 5 et 8). Toute nouvelle règle : une fonction dans `RULES`, une docstring, un test, une décision. Les annotations de transcripteur ne sont pas normalisées mais filtrées en F4 (décision 15).
- **Valeurs multiples** dans les CSV de `reports/` : séparées par ` | `.
- **Seeds** : à venir, fixées dans les configs et dans les fichiers de `splits/`.
- **Lancement** : `uv run python -m htr_ottoman.<module>`.

## 7. Tests

| Fichier | Ce qui est testé | État |
|---------|------------------|------|
| `tests/test_config.py` | Le package s'importe, `ROOT` est la racine du projet, les chemins sont dans le projet. | fait |
| `tests/test_normalize.py` | Un test par règle (exemples réels آ, أ, ئ, ی selon la position), sortie NFD, idempotence ; et sur les 3 868 lignes ottomanes réelles (sauté si le zip MAKHZAN est absent). | fait (39 tests) |

Lancement : `uv run pytest`.

## 8. Reproduire de bout en bout

```bash
uv sync                                                        # environnement
uv run python scripts/check_mps.py                             # backend MPS
# téléchargement de MAKHZAN : à venir (module data) ; en attendant, voir README (URL et MD5)
uv run python -m htr_ottoman.analysis.inventory_ottoman
uv run python -m htr_ottoman.analysis.compare_ottoman_sources
uv run python -m htr_ottoman.analysis.char_inventory
# extraction, splits, application de la normalisation, entraînement, évaluation : à venir
uv run pytest
```
