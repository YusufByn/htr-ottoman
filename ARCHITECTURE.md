# Architecture

Structure du code et flux des données. Mis à jour à chaque étape terminée.
Dernière mise à jour : 2026-09-28.

## 1. Vue d'ensemble

```
data/raw/makhzan/  (zip + TSV, lecture seule)
   │
   ├──> analysis ───────────────────────────────> reports/  (inventaires, comparaisons)
   │
   └──> data.makhzan ──> data/interim/makhzan/  (images + ALTO par manuscrit, table des lignes)
                                          │
                        splits ──> splits/│  (train / val / test_interne, une ligne par page)
                                          │
  prepare : normalize + compilation (anciens polygones)
                                          v
                                   data/processed/  (jeux prêts pour kraken, par split)
                                          │
        train (configs/*.yml) ──> models/  (modèles affinés) + reports/training/, reports/figures/
                                          │
            predict + evaluate ──> reports/ + EXPERIMENTS.md  (CER ; baseline : reports/baseline/)
```

Le pipeline part toujours de `data/raw/`, qui n'est jamais modifié. Chaque étape lit la sortie de la précédente et écrit dans son propre dossier.

## 2. Arborescence

```
htr-ottoman/
├── configs/              une expérience d'entraînement par fichier YAML (f8_finetune.yml)
├── data/                 hors git
│   ├── raw/              sources telles que téléchargées, en lecture seule (chmod a-w)
│   ├── interim/          zips décompressés, ALTO bruts, avant normalisation
│   └── processed/        makhzan/alto/ (ALTO normalisés), makhzan/<jeu>.arrow et <jeu>.lst
├── models/               modèle de départ (openiti_ottoman_print/) et modèles entraînés (hors git)
├── notebooks/            exploration visuelle uniquement, aucun code du pipeline n'en dépend
├── reports/              inventaires, métriques (versionné, CC BY-NC-SA)
│   ├── baseline/         F7 : prédictions et CER du modèle de départ, un dossier par jeu (val/, test_interne/)
│   ├── f8_finetune/      F8 : prédictions et CER du modèle affiné sur la validation (val/)
│   ├── training/         métriques par époque de chaque entraînement retenu (<config>.csv)
│   └── figures/          graphiques générés par les modules d'analyse
├── scripts/              utilitaires (vérification d'environnement)
├── splits/               listes train/val/test figées, avec la seed (versionné)
├── src/htr_ottoman/      package Python du projet
│   ├── config.py         chemins du projet, définis une seule fois
│   ├── data/             download.py (MD5, idempotent), alto.py (lecture ALTO), makhzan.py, annotations.py
│   ├── analysis/         inventaires et comparaisons descriptives
│   ├── base_model.py     modèle de départ : téléchargement, chargement kraken, codec
│   ├── normalize.py      l'unique fonction de normalisation (NFD + règles documentées)
│   ├── splits.py         découpage par œuvre, fichiers de splits/ et contrôle d'étanchéité
│   ├── prepare.py        ALTO normalisés, compilation Arrow pour kraken, vérifications
│   ├── predict.py        prédictions ligne par ligne (API kraken, BiDi)
│   ├── evaluate.py       CER micro global et ventilé, bootstrap par manuscrit
│   └── train.py          fine-tuning kraken piloté par une config de configs/
├── tests/                tests automatiques (pytest)
└── pyproject.toml, uv.lock, README.md, CLAUDE.md, DECISIONS.md, EXPERIMENTS.md, ARCHITECTURE.md, PROJECT.md
```

## 3. Flux des données

| Étape | Module | Entrées | Sorties | État |
|-------|--------|---------|---------|------|
| Téléchargement | `data.makhzan` (`download`) | API Zenodo, record 19861912, version 2026.1.2 | `data/raw/makhzan/` (3 fichiers, MD5 vérifiés, lecture seule) | fait |
| Inventaire | `analysis.inventory_ottoman` | TSV de métadonnées | `reports/ottoman_inventory.csv` | fait |
| Comparaison des sources | `analysis.compare_ottoman_sources` | TSV de métadonnées | sortie console | fait |
| Inventaire des caractères | `analysis.char_inventory` | zip MAKHZAN (ALTO lus dans le zip, lecture seule), TSV | `reports/ottoman_characters.csv` | fait |
| Extraction | `data.makhzan` (`extract`) | zip MAKHZAN, TSV | `data/interim/makhzan/<DocID>/` (30 manuscrits ottomans) | fait |
| Table des lignes | `data.makhzan` (`build_lines`, `check_lines`) | `data/interim/makhzan/`, TSV | `data/interim/makhzan/ottoman_lines.parquet` (3 868 lignes) | fait |
| Modèle de départ | `base_model` | API Zenodo, record 7050342 | `models/openiti_ottoman_print/` (MD5 vérifiés, lecture seule) | fait |
| Couverture du codec | `analysis.codec_coverage` | table des lignes, `splits/`, modèle de départ | `reports/codec_coverage.csv` | fait |
| Découpage | `splits` | TSV, décisions 1, 3, 6, 7, 19, 20 | `splits/train.csv`, `val.csv`, `test_interne.csv` | fait |
| Préparation pour kraken | `prepare` (avec `normalize`, `data.annotations`) | table des lignes, `splits/`, images de `data/interim/` | `data/processed/makhzan/` (248 ALTO normalisés, `train.arrow` 2 757 lignes, `val.arrow` 412, `test_interne.arrow` 544, manifestes `.lst`), `reports/processed_datasets.csv` | fait |
| Entraînement | `train` | `configs/<config>.yml`, `data/processed/makhzan/{train,val}.lst`, modèle de départ | `models/<config>/` (checkpoints, `best_<score>.safetensors`, `commande.txt`, `ketos.log`, `run.json`, journal TensorBoard), `reports/training/<config>.csv`, `reports/figures/<config>_courbes.png`, ligne dans `EXPERIMENTS.md` ; essai : tout dans `models/<config>_essai/` | fait (F8 : 91 époques, 4 h 38) |
| Prédiction | `predict` | modèle, ALTO normalisés d'un jeu (`data/processed/makhzan/alto/`, segmentation de la vérité terrain, décision 31 ; découpe « anciens polygones » imposée, décision 36) | parquet (part_id, line_id, pred) ; baseline : `reports/baseline/<jeu>/predictions.parquet` ; modèle F8 : `reports/f8_finetune/val/` | fait |
| Évaluation | `evaluate` | prédictions, table des lignes, `splits/` | dossier de CSV (global, par écriture, relecture, couche modèle, manuscrit, multilinguisme) + `lignes.parquet` ; baseline : `reports/baseline/<jeu>/` ; résultat consigné dans `EXPERIMENTS.md` | fait |

## 4. Modules du package

| Module | Responsabilité | Point d'entrée | État |
|--------|----------------|----------------|------|
| `config` | Chemins du projet (`ROOT`, `DATA_RAW`, `SPLITS`, `REPORTS`, `BASELINE_REPORTS`, fichiers MAKHZAN). Tous les modules les importent d'ici. | aucun | fait |
| `analysis.inventory_ottoman` | Une ligne par manuscrit ottoman : titre, pages, écritures, langues, source, relecture, lignes, pages en couche modèle. S'arrête si une couche de transcription inconnue apparaît. | `uv run python -m htr_ottoman.analysis.inventory_ottoman` | fait |
| `analysis.compare_ottoman_sources` | Research contre ACDC-Evaluation : pages, lignes, écritures, relecture ; lignes par manuscrit et par œuvre. | `uv run python -m htr_ottoman.analysis.compare_ottoman_sources` | fait |
| `analysis.char_inventory` | Une ligne par caractère des lignes ottomanes : point de code, nom et catégorie Unicode, occurrences, lignes, manuscrits, Research / ACDC-Evaluation. Signale les anomalies d'espacement. Fournit aussi `iter_lines`, utilisé par les tests. | `uv run python -m htr_ottoman.analysis.char_inventory` | fait |
| `data.download` | `ensure_file(url, dest, md5)` : fichier présent et valide, rien n'est fait ; MD5 faux, erreur sans rien supprimer ; absent, téléchargement via `.part`, vérification, lecture seule. `data/raw/` rendu modifiable le temps d'écrire, puis restauré. | aucun (utilisé par `data.makhzan`) | fait |
| `data.alto` | `read_alto(xml)` : `Page` (image, taille) et ses `Line` (id, bloc, texte brut, ligne de base, polygone, `is_empty`). | aucun | fait |
| `data.makhzan` | Constantes MAKHZAN (version, `LANGUAGE`, `MODEL_LAYERS`, `KNOWN_LAYERS`) ; `download`, `extract` (dossier temporaire puis renommage, noms de fichiers contrôlés), `build_lines`, `check_lines` (effectifs par page égaux au TSV). | `uv run python -m htr_ottoman.data.makhzan` | fait |
| `normalize` | `normalize(text)` : applique dans l'ordre les règles de `RULES` (1 NFD, 2 marques de direction, 3 voyelles, 4 ک→ك, 5 ی selon la position, 8 séparateurs de vers → ".", 9 ڛ→س, 6 ZWNJ répétés, 7 espaces), puis NFD. Sortie toujours NFD, idempotente. Une fonction par règle, docstring et décision associées (5, 9 à 14, 21, 22). Le numéro d'une règle est un identifiant, pas son rang. | import `from htr_ottoman.normalize import normalize` | fait |
| `base_model` | `download` (Zenodo, `ensure_file`), `load` (kraken `load_models`, lit l'ancien `.mlmodel` ; avertissements bénins de coremltools masqués), `codec_labels`, `codec_chars` (ensemble des caractères du codec, chargé une fois). Modèle : lignes de 120 px, niveaux de gris, lignes de base, anciens polygones, NFD. | `uv run python -m htr_ottoman.base_model` | fait |
| `analysis.codec_coverage` | Caractères des lignes transcrites après `normalize`, par jeu, comparés au codec ; lignes annotées comptées à part. | `uv run python -m htr_ottoman.analysis.codec_coverage` | fait |
| `data.annotations` | `has_annotation(text)` : accolades et `(؟)` (décision 15), utilisé par la couverture du codec et par F4. | aucun | fait |
| `prepare` | `select_lines` (exclut vides et annotées ; pour le train, lignes hors codec du modèle de départ, décision 33), `write_page_alto` (texte passé par `normalize`, lignes exclues retirées, image désignée par chemin relatif), `compile_split` (`build_binary_dataset`, anciens polygones, un seul processus), `check_split` (nombre de lignes, NFD, texte attendu, statut des polygones), `verify_with_kraken` (lecture par la classe de jeu de l'entraînement, aucune ligne remplacée). Constantes `LEGACY_POLYGONS`, `KRAKEN_TEXT_OPTIONS` (réutilisées par F7 et F8). | `uv run python -m htr_ottoman.prepare` | fait |
| `splits` | `assign` (règles fixes : ACDC-Evaluation → test_interne, *Manāfi' al-nās* → val, reste de Research → train), `validate` (chaque page une fois, aucune œuvre, Doc ID ni cote partagés, Doc 86 et 89 ensemble), `render` (en-tête sans date : fichiers identiques octet pour octet), `load_split` pour les étapes suivantes. `SEED = 42`. | `uv run python -m htr_ottoman.splits` | fait |
| `train` | `load_config`, `check` (réglages de texte de la décision 26, validation imposée, jamais le test interne ni dans la config ni dans les manifestes, seed 42), `to_args` (clés = noms longs des options de ketos, clé inconnue refusée), `build_command` (ajoute `-v`, `--output`, journal TensorBoard ; essai = 1 époque), `validate_with_ketos` (analyse des options sans lancement), `git_commit` (refuse de lancer si du travail n'est pas committé, hors EXPERIMENTS.md), `experiment_row` (ligne « en cours » d'EXPERIMENTS.md au lancement), `read_metrics` (perte, précision de validation kraken et durées par époque, depuis TensorBoard), `plot_curves`, `write_outputs`, `plot_only` (`--plot-only` : métriques et courbes relues dans le journal d'un entraînement terminé, sans entraîner). Compte les lignes remplacées par kraken et les avertissements du mode déterministe. | `uv run python -m htr_ottoman.train configs/<config>.yml [--trial] [--plot-only]` | fait |
| `predict` | `predict_split(modèle, jeu)` : `RecognitionTaskModel.predict` page par page sur les ALTO normalisés, `bidi_reordering` du projet (ordre logique), découpe imposée par le projet (`prepare.LEGACY_POLYGONS`), pas lue dans le modèle : kraken 7.1.1 perd ce drapeau à la conversion (décision 36). | `uv run python -m htr_ottoman.predict --model … --split … --output …` | fait |
| `evaluate` | `edit_counts` (Levenshtein détaillé S/D/I), `score_lines` (`normalize` des deux côtés), `summarize` (CER micro, effectifs, bootstrap par manuscrit si au moins 3), `attach_metadata` (vérifie une prédiction par ligne compilée), `report` (global, écriture, relecture, couche modèle, manuscrit, avec et sans multilingue). | `uv run python -m htr_ottoman.evaluate PRED.parquet --split … --output-dir …` | fait |

## 5. Configurations

Un fichier YAML par expérience d'entraînement dans `configs/`, lu par `train`. Deux sections : `ketos` (options globales, avant `train`) et `train` (options de `ketos train`). Les clés sont les noms longs des options de ketos sans les tirets (`lrate`, `batch-size`, `reorder`), les chemins sont relatifs à la racine. Le format natif de ketos (`--config`) n'est pas utilisé : il ignore une clé inconnue avec un simple avertissement. `train` ajoute lui-même la sortie, le journal TensorBoard et `-v`. Premier fichier : `configs/f8_finetune.yml` (décisions 33 à 35).

## 6. Conventions

- **Chemins** : toujours importés de `htr_ottoman.config`, jamais écrits en dur dans un module.
- **Données brutes** : `data/raw/` est en lecture seule (`chmod a-w`) ; aucun module n'y écrit.
- **Identifiants** : les fichiers MAKHZAN sont nommés `<DocID>_<DocPartID>.jpg` / `.xml` ; un Doc ID est un document eScriptorium, une œuvre est identifiée par `Title of Text` (décision 6).
- **Normalisation** : appliquée en un seul point, par `normalize`, à la vérité terrain et aux prédictions (décisions 5 et 8). Toute nouvelle règle : une fonction dans `RULES`, une docstring, un test, une décision. Les annotations de transcripteur ne sont pas normalisées mais filtrées en F4 (décision 15).
- **Valeurs multiples** dans les CSV de `reports/` : séparées par ` | `.
- **Seeds** : `SEED = 42` dans `splits.py`, écrite dans l'en-tête des fichiers de `splits/` ; les configs d'entraînement la reprendront. L'affectation aux jeux ne dépend d'aucun tirage.
- **kraken** : toujours lire la skill `.claude/skills/kraken/` avant de l'utiliser. Réglages de texte : `prepare.KRAKEN_TEXT_OPTIONS` ; découpe : anciens polygones ; prédictions via l'API Python ou `ketos test`, pas `kraken ocr` ; tout code qui lance kraken tourne dans un module avec `if __name__ == "__main__":` (processus parallèles).
- **Fichiers générés versionnés** (`splits/`, `reports/`) : jamais de date ni d'élément variable dans leur contenu, pour que la régénération soit vérifiable par comparaison.
- **Lancement** : `uv run python -m htr_ottoman.<module>`.
- **Dépendances** (`pyproject.toml`) : kraken 7.1.1, pandas, tensorboard (journal des métriques d'entraînement, lu par `train`), matplotlib (courbes).

## 7. Tests

| Fichier | Ce qui est testé | État |
|---------|------------------|------|
| `tests/test_alto.py` | Lecture d'un ALTO minimal écrit à la main : texte, ligne vide, ligne de base, polygone. | fait (3 tests) |
| `tests/test_download.py` | Les quatre cas du téléchargement et le dossier en lecture seule restauré, sans réseau (URL `file://`). | fait (5 tests) |
| `tests/test_makhzan.py` | Table des lignes : 248 pages, 30 manuscrits, effectifs identiques au TSV, `check_lines` détecte une incohérence, 18 pages en couche modèle, aucune métadonnée vide (sauté si la table est absente). | fait (4 tests) |
| `tests/test_splits.py` | Fichiers identiques à une régénération, étanchéité (œuvre, Doc ID, cote), Doc 86 et 89 ensemble, chaque page une fois, effectifs, pages multilingues, `validate` détecte une fuite. | fait (16 tests) |
| `tests/test_annotations.py` | `has_annotation` sur des cas réels (illisible, restitution, note, incertitude) et des lignes ordinaires. | fait (8 tests) |
| `tests/test_base_model.py` | MD5 du modèle, chargement, entrée (120 px, niveaux de gris, lignes de base, NFD), codec de 196 caractères (sauté si le modèle est absent). | fait (3 tests) |
| `tests/test_prepare.py` | Effectifs compilés et exclusions (dont 6 lignes hors codec du train), train entièrement couvert par le codec, texte des `.arrow` (NFD, sans annotation, anciens polygones), réglages de texte de kraken sans effet, ALTO normalisés relus par kraken, lecture d'un échantillon par kraken, réglages identiques au modèle de départ (sauté si les jeux sont absents). | fait (15 tests) |
| `tests/test_evaluate.py` | Cas calculés à la main (identiques, S, D, I, vides, kitten/sitting), retournement, NFC/NFD, normalize des deux côtés, espaces, agrégation micro, concordance torchmetrics, bootstrap (reproductible, rien sous 3 manuscrits), bout en bout sur la validation (CER nul, prédiction manquante détectée), tableaux de chaque évaluation versionnée (`reports/<modèle>/<jeu>/`) redonnés à partir de ses prédictions. | fait (24 tests) |
| `tests/test_predict.py` | Découpe « anciens polygones » imposée à chaque modèle présent (départ, essai, F8), même quand le drapeau enregistré dit le contraire (sauté si les modèles sont absents). | fait (3 tests) |
| `tests/test_train.py` | Noms longs et booléens, clés inconnues ou réservées refusées, config F8 valide et acceptée par ketos, essai (1 époque) et dossiers séparés, garde-fous (réglages de texte, seed, test interne, validation manquante), valeur refusée par ketos, fichiers non committés hors journal, ligne d'EXPERIMENTS.md, métriques et durées lues dans un journal TensorBoard synthétique, graphique. | fait (17 tests) |
| `tests/test_config.py` | Le package s'importe, `ROOT` est la racine du projet, les chemins sont dans le projet. | fait |
| `tests/test_normalize.py` | Un test par règle (exemples réels آ, أ, ئ, ی selon la position, séparateurs de vers, ڛ), sortie NFD, idempotence ; et sur les 3 868 lignes ottomanes réelles (sauté si le zip MAKHZAN est absent). | fait (43 tests) |

Lancement : `uv run pytest`.

## 8. Reproduire de bout en bout

```bash
uv sync                                                        # environnement
uv run python scripts/check_mps.py                             # backend MPS
uv run python -m htr_ottoman.data.makhzan                      # téléchargement, extraction, table des lignes
uv run python -m htr_ottoman.analysis.inventory_ottoman
uv run python -m htr_ottoman.analysis.compare_ottoman_sources
uv run python -m htr_ottoman.analysis.char_inventory
uv run python -m htr_ottoman.splits                            # splits/*.csv
uv run python -m htr_ottoman.base_model                        # modèle de départ (16 Mo)
uv run python -m htr_ottoman.analysis.codec_coverage
uv run python -m htr_ottoman.prepare                           # data/processed/makhzan/*.arrow (environ 2 min)
# baseline (F7), environ 40 s par jeu, redonne les fichiers versionnés de reports/baseline/
uv run python -m htr_ottoman.predict --model models/openiti_ottoman_print/ottoman_best.mlmodel --split val --output reports/baseline/val/predictions.parquet
uv run python -m htr_ottoman.evaluate reports/baseline/val/predictions.parquet --split val --output-dir reports/baseline/val
uv run python -m htr_ottoman.predict --model models/openiti_ottoman_print/ottoman_best.mlmodel --split test_interne --output reports/baseline/test_interne/predictions.parquet
uv run python -m htr_ottoman.evaluate reports/baseline/test_interne/predictions.parquet --split test_interne --output-dir reports/baseline/test_interne
uv run python -m htr_ottoman.train configs/f8_finetune.yml --trial  # essai court, 1 époque, models/f8_finetune_essai/
uv run python -m htr_ottoman.train configs/f8_finetune.yml          # entraînement complet (F8 : 4 h 38, 91 époques, MPS)
uv run python -m htr_ottoman.predict --model models/f8_finetune/best_0.8365.safetensors --split val --output reports/f8_finetune/val/predictions.parquet
uv run python -m htr_ottoman.evaluate reports/f8_finetune/val/predictions.parquet --split val --output-dir reports/f8_finetune/val
uv run pytest
```
