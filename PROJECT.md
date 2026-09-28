# Projet HTR ottoman

Résumé du projet et état d'avancement. Mis à jour à chaque étape terminée.
Dernière mise à jour : 2026-09-28.

## 1. Résumé

Reconnaissance automatique d'écriture manuscrite (HTR) sur des manuscrits en turc ottoman, avec kraken.
On part d'un modèle entraîné sur de l'**imprimé** ottoman (OpenITI) et on l'affine sur les manuscrits ottomans de MAKHZAN.

**Question de recherche** : dans quelle mesure ce modèle affiné généralise-t-il à des manuscrits jamais vus, d'abord sur le test interne (ACDC-Evaluation), puis sur un jeu externe (Akis) ?

Projet de recherche et portfolio.

## 2. Données et modèle de départ

| Ressource | Version | Rôle | Licence |
|-----------|---------|------|---------|
| OpenITI MAKHZAN, partie ottomane | 2026.1.2, DOI 10.5281/zenodo.19861912 | entraînement, validation, test interne | CC BY-NC-SA 4.0 |
| Akis | à venir | test final externe | Apache 2.0, citer Tasdemir et al., DAS 2024 |
| Modèle OpenITI ottoman imprimé | DOI 10.5281/zenodo.7050342 (kraken, CER annoncé 4,22 %). Lignes de 120 px en niveaux de gris, lignes de base, NFD ; codec de 196 caractères | modèle de départ | CC0 |

Tout modèle dérivé de MAKHZAN est sous CC BY-NC-SA. Détails et MD5 : [README](README.md).

## 3. Protocole d'évaluation

| Jeu | Contenu | Manuscrits | Pages | Lignes transcrites | Décisions |
|-----|---------|-----------:|------:|-------------------:|-----------|
| Entraînement | Research, sauf l'œuvre de validation (6 œuvres) | 11 | 199 | 2 771 | 2, 3, 6 |
| Validation | *Manāfi' al-nās fī al-ṭibb* (Doc 2937, 2939) | 2 | 19 | 436 | 7 |
| Test interne | ACDC-Evaluation ottoman, jamais utilisé pour le réglage ; 7 pages multilingues marquées | 17 | 30 | 555 | 1, 19 |
| Test final | Akis, évaluation finale uniquement | à venir | à venir | à venir | CLAUDE.md |

- Découpage par œuvre : toutes les copies d'une œuvre sont dans le même jeu (décision 6).
- Les lignes sans transcription sont exclues de l'entraînement.
- Les lignes contenant des annotations de transcripteur (`{...}`, `(؟)`, environ 43) sont exclues de l'entraînement et de l'évaluation (décision 15). Lignes compilées pour kraken après ces exclusions : train 2 763, validation 412, test interne 544 (`reports/processed_datasets.csv`).
- **Métrique** : CER (taux d'erreur par caractère), calculé sur vérité terrain et prédictions passées par la même fonction `normalize` : NFD, voyelles supprimées, ک et ی unifiés, séparateurs de vers unifiés en ".", ڛ → س, espaces et invisibles nettoyés (décisions 5, 9 à 14, 21, 22). CER micro, espaces comptés (décision 28), rapporté au global, par écriture, par catégorie de relecture, par couche gen2 et par manuscrit, avec un intervalle de confiance à 95 % par bootstrap sur les manuscrits quand le groupe en compte au moins 3 (décision 30). Référence : `evaluate` ; `ketos test` en contrôle (décision 29).
- Découpage figé dans `splits/train.csv`, `val.csv`, `test_interne.csv` (une ligne par page, seed 42), étanchéité vérifiée par les tests (décision 20).
- CER du test interne rapporté avec et sans les pages multilingues (décision 19).

## 4. Fonctionnalités

| Fonctionnalité | État |
|----------------|------|
| Vérification de l'environnement (kraken, MPS) : `scripts/check_mps.py` | fait |
| Inventaire des manuscrits ottomans : `analysis.inventory_ottoman` | fait |
| Comparaison Research / ACDC-Evaluation, par manuscrit et par œuvre : `analysis.compare_ottoman_sources` | fait |
| Téléchargement de MAKHZAN avec vérification MD5, idempotent : `data.makhzan` | fait |
| Extraction des 30 manuscrits ottomans et table des lignes (Parquet, 3 868 lignes) : `data.makhzan` | fait |
| Inventaire des caractères des lignes ottomanes : `analysis.char_inventory` | fait |
| Normalisation (NFD + 8 règles) et 43 tests : `normalize` | fait |
| Création des splits, contrôle d'étanchéité : `splits` | fait |
| Préparation pour kraken : ALTO normalisés, jeux compilés (anciens polygones), vérification de lecture : `prepare` | fait |
| Modèle de départ : téléchargement, chargement, codec : `base_model` | fait |
| Couverture du codec par MAKHZAN : `analysis.codec_coverage` | fait |
| Prédiction ligne par ligne (API kraken) : `predict` | fait |
| Évaluation (CER micro ventilé, bootstrap par manuscrit) : `evaluate` | fait |
| Fine-tuning kraken | à venir |

## 5. État d'avancement

Voir [ROADMAP.md](ROADMAP.md) : liste des tickets F0 à F14, avec leurs dépendances et leur statut.

## 6. Résultats clés

Premier repère (contrôle de F5, pas encore la baseline officielle) : modèle de départ sans affinage, validation, **CER 27,8 %** (`evaluate`). La baseline complète, avec le test interne, vient en F7. Le détail de chaque expérience est consigné dans [EXPERIMENTS.md](EXPERIMENTS.md).

## 7. Limites et questions ouvertes

- **Poids de *Revnaḳ-ı Būstān*** : environ 63 % des lignes d'entraînement (1 755 / 2 771), surtout Doc 3263. Expérience possible plus tard pour limiter sa part.
- **Écart d'écriture** : l'entraînement est 100 % naskh, alors que 10 des 17 manuscrits du test interne ne le sont pas (divani, ta'liq, nastaliq, riq'a, mixtes). Le CER global du test interne mélangera la performance sur le naskh et la capacité à généraliser à d'autres écritures ; d'où le CER par écriture.
- **Couche `gen2-print`** : 18 pages (Doc 83, Doc 6398) pré-transcrites par un modèle puis corrigées, sans documentation (décision 4). Indice : leur texte est le seul en NFD, comme la sortie des modèles OpenITI (décision 16). Qualité de la correction inconnue, effet à tester.
- **Doc 86 et Doc 89** : même cote, dates différentes ; traités comme un seul manuscrit (décision 3).
- **Relecture** : toutes les pages Research n'ont été relues qu'une fois, donc sont moins fiables que les pages relues deux fois.
- **Conventions de transcription** inégales selon les transcripteurs d'après l'article JOHD. `normalize` corrige les différences d'encodage (ک / ك, ی / ي ى, voyelles), mais pas les choix de lecture (hamza sur yāʾ gardée ou non, kāf / gāf).
- **Lettres sans points** (ڡ, ٮ, ں) : transcription diplomatique de Doc 3178 (test interne), absente de l'entraînement. Ces lignes seront probablement pénalisées.
- **Unicode** : MAKHZAN est en NFC, le modèle de départ en NFD ; résolu par `normalize` (décision 5).
- **Conventions d'encodage du modèle de départ** : il écrit ی et ک (imprimé OpenITI) là où MAKHZAN écrit ي/ى et ك. Sans les règles 4 et 5, sa baseline serait pénalisée d'environ 8 points (décision 29) ; tout CER calculé sans `normalize`, comme celui de `ketos test`, n'est pas comparable.
- **Peu de données** : 2 763 lignes d'entraînement compilées.
- **Outil** : la sortie texte de `kraken ocr` 7.1.1 est inversée sur nos ALTO ; les prédictions passent par l'API Python ou `ketos test` (skill kraken).
- **Modèle de départ** entraîné sur de l'imprimé, pas sur des manuscrits. Son codec couvre 99,92 à 100 % des caractères de MAKHZAN après normalisation ; restent inconnus `#` et ZWNJ (train, décision 23) et les lettres sans points de Doc 3178 (décision 24).

## 8. Prochaines étapes

Voir [ROADMAP.md](ROADMAP.md). Ticket suivant : F7 (baseline), dont toutes les dépendances sont remplies (F4, F5, F6).

Journal des décisions : [DECISIONS.md](DECISIONS.md).
