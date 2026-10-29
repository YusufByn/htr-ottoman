# Inventaire de RiqaTestset (F15, décision 46)

Date : 2026-10-29. Aucune prédiction, aucun modèle chargé (kraken jamais importé, `tests/test_riqa.py`). Chiffres agrégés seulement : ni image ni transcription (décision 46). Données : Osmanlica.com, usage académique autorisé le 2026-10-23 ; citer leurs publications.

Commandes : `uv run python -I -m htr_ottoman.data.riqa`, puis `uv run python -I -m htr_ottoman.analysis.riqa_inventory`. Détails : [unites.csv](unites.csv), [caracteres.csv](caracteres.csv), [resume.json](resume.json).

## 1. Fichier

- `data/raw/riqa/RiqaTestset.zip`, 9 789 642 octets, SHA-256 `7368010513b50c46459b0c3ef4afd826e4d75ab78c967808ef3a60abb3d39305` (vérifié par `data.riqa` avant toute lecture). Dates internes du zip : 2026-02-03.
- Extrait dans `data/interim/riqa/` (le dossier racine `riqa/` du zip) ; `data/raw/riqa/` inchangé.

## 2. Contenu et formats

- **Fichiers** : `images/` (1 575 PNG), `ottoman/` (1 575 `.gt.txt`, écriture arabe), `turkish/` (1 575 `.gt.txt`, translittération latine, non analysée), `metrics.json`. **Aucune licence, aucun README, aucune métadonnée** (ni document, ni date, ni main, ni source).
- **`metrics.json`** : scores annoncés par Osmanlica.com pour son propre système sur ce jeu, sans prédictions : OCR CER 6,65 % (normalisé 6,14 %), WER 27,9 % ; translittération CER 11,3 % ; normalisation non décrite. Ce ne sont pas des chiffres comparables aux nôtres tant que leur normalisation est inconnue.
- **Images** : **déjà découpées en lignes**, une image par ligne, sans ligne de base ni coordonnées dans la page. Toutes en mode `L` (gris) et **binarisées** (2 niveaux, 1 575 sur 1 575). Hauteur : 18 à 403 px (médiane 84) ; largeur : 46 à 5 068 px (médiane 1 477).
- **Vérité terrain** : un fichier texte UTF-8 par ligne, même nom que l'image ; aucun BOM, aucun `\r`, aucun saut de ligne final.
- **Unicode** : 1 557 lignes sans caractère composable, 18 en **NFC** (آ, ئ, ۀ précomposés) ; aucune en NFD.

## 3. Effectifs

| | Nombre |
|---|---|
| Unités (préfixe UUID des noms de fichiers) | 85 |
| Lignes | 1 575 (2 à 62 par unité, médiane 20) |
| Caractères, texte brut | 141 792 |
| Caractères après `normalize` | 141 497 (3 à 219 par ligne, médiane 89 avant normalisation) |
| Lignes vides | 0 |
| Lignes annotées au sens de la décision 15 (`{`, `}`, `(؟)`) | 0 |

- **Documents** : les 85 unités correspondent aux « 85 pages » de la page du jeu et aux « documents » de RikaOCR. Rien n'indique si plusieurs unités viennent du même document ou de la même main : un intervalle de confiance par unité supposerait 85 unités indépendantes, ce qui n'est pas vérifiable (limite à écrire au pré-enregistrement).
- **Numérotation** : commence à 0 dans 71 unités, à 1 dans 14 ; **trous dans 24 unités sur 85** (lignes absentes de la page, sans explication).

## 4. Caractères et codec du modèle de départ (196 entrées)

| | Types | Occurrences |
|---|---|---|
| Texte brut | 71 | 141 792 |
| Brut, hors codec | 4 (آ, ئ, ۀ précomposés ; ZWNJ) | 27 |
| Après `normalize` | 69 | 141 497 |
| Après `normalize`, **hors codec** | **1** (ZWNJ, U+200C) | 8 (8 lignes, 0,006 %) |
| Après `normalize`, **absents du train** | **24** | 950 (0,67 %) |

- **Effet de `normalize`** : 1 549 lignes sur 1 575 modifiées. Surtout la règle 5 : les 12 285 ی (yāʾ persan) deviennent ي (8 696) ou ى (3 603) ; aucun ک. NFD décompose les 3 آ, 14 ئ et 2 ۀ (d'où 2 ە de plus) ; 4 ḥarakāt supprimées ; 310 espaces en trop retirées.
- **Hors codec** : seul le ZWNJ (8 occurrences), déjà hors codec pour MAKHZAN (décision 11). Erreur garantie sur ces 8 caractères pour la baseline.
- **Dans le codec mais absents du train** (24 types) : le modèle affiné ne les a jamais vus.
  - **۔ (U+06D4, point final arabe) : 485 occurrences, 365 lignes, 49 unités**, dont 80 en fin de ligne. Absent de MAKHZAN ; convention de ponctuation du transcripteur ou signe écrit sur l'image : à vérifier.
  - **ە (U+06D5) : 42** (40 bruts + 2 issus de ۀ) ; F13 a déjà noté ە comme convention possible (piste de F15).
  - Chiffres arabes ٢ à ٩ : 109 au total.
  - Ponctuation : guillemets " “ ” ‘ (118, 73 lignes, 19 unités), `:` (27), ؛ (23), ؟ (23, 22 lignes), `-` (22), `!` (12), `=` (1).
  - **Crochets `[…]` (18 lignes, 8 unités) et parenthèses `(…)` (14 lignes, 7 unités)**, segments de 5 à 52 caractères ; **`_` (14, 13 lignes, 4 unités)**. Ce peuvent être des signes de la page ou des annotations de transcripteur (restitution, lecture incertaine, passage illisible) : non détectés par la règle de la décision 15, à vérifier sur les images.

## 5. Points pour le pré-enregistrement

1. **Images binarisées** : MAKHZAN (entraînement de F8) est en gris ; écart de domaine à mentionner, sans traitement des images (aucun réglage sur ce jeu).
2. **Découpe** : lignes déjà découpées, sans ligne de base ; `predict` impose l'ancien extracteur sur lignes de base (décision 36). Piste notée dans la décision 46 : mesurer sur la validation l'effet d'une découpe en rectangles.
3. **Crochets, parenthèses, `_`, ۔, guillemets** : vérifier sur les images s'ils sont écrits ; décider avant toute prédiction s'ils restent dans le texte (aucune règle de `normalize` ajoutée sans décision).
4. **Unité de l'intervalle de confiance** : 85 unités, indépendance non vérifiable.
5. **Trous de numérotation** (24 unités) : question à joindre à celle du 2026-10-29 sur l'origine de la vérité terrain.
