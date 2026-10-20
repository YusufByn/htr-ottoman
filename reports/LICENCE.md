# Licence et source des contenus de `reports/`

Le code du projet est sous licence MIT ([LICENSE](../LICENSE)). Les contenus de `reports/` ne le sont pas : ils sont dérivés de données, et suivent la licence de leur source.

## Contenus dérivés de MAKHZAN : CC BY-NC-SA 4.0

Sauf exceptions listées plus bas, tout le contenu de `reports/` est dérivé d'OpenITI MAKHZAN et est diffusé sous la même licence, [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (attribution, pas d'usage commercial, partage dans les mêmes conditions).

**Source** : Parkes Allen, J., Mullan, J., Nigst, L., Barber, M., Shahid Khan, T., Seydi, M., Chen, D., Weng, Y., Vogler, N., Murel, J., Eshera, O., Berg-Kirkpatrick, T., Smith, D., Bowen Savant, S., Thomas Miller, M., Verkinderen, P. *OpenITI MAKHZAN*, version 2026.1.2, Zenodo, 2026-04-28, DOI [10.5281/zenodo.19861912](https://doi.org/10.5281/zenodo.19861912).

Ce que contiennent ces fichiers :

- **texte de la vérité terrain** de MAKHZAN, normalisé par `htr_ottoman.normalize` : `lignes.parquet` des dossiers d'évaluation (`baseline/`, `f8_finetune/`, `f8_finetune_seed43/`, `f8_finetune_seed44/`, `f8_lag15_seed*/`, `f12_*/`), `erreurs/`, `f13/` ;
- **prédictions** des modèles sur les lignes de MAKHZAN (`predictions.parquet`) ;
- **images de lignes** de MAKHZAN, intégrées dans les pages de lecture de F13 : `f13/q3_encre_rouge/`, `f13/q4_ya_final/`, `f13/q5_points/`, `f13/q6_doc3179/` (`lecture_a_l_aveugle.html`) ;
- **métadonnées et statistiques** : inventaires (`ottoman_inventory.csv`, `ottoman_characters.csv`), couverture du codec (`codec_coverage.csv`), jeux préparés (`processed_datasets.csv`, `train_sans_gen2.csv`), CER et comparaisons (`*/global.csv`, `par_*.csv`, `comparaisons/`, `bruit/`), courbes et métriques d'entraînement (`training/`, `figures/`), analyses de F13 (`f13/`).

Les fichiers de découpage `splits/` (identifiants et métadonnées des pages de MAKHZAN) sont sous la même licence.

## Exceptions

| Fichier | Source | Licence |
|---|---|---|
| `akis_characters.csv`, `akis_sources.csv` | Akis, jeu de test public ([verimsu/Akis-Ottoman-Dataset](https://github.com/verimsu/Akis-Ottoman-Dataset), commit `c7a6e5b`) | Apache 2.0 ; citer Tasdemir et al., « Automatic Transcription of Ottoman Documents Using Deep Learning », DAS 2024, DOI 10.1007/978-3-031-70442-0_26 |
| `codec_modele_depart.json` | codec du modèle OpenITI ottoman imprimé (B. Kiessling, DOI [10.5281/zenodo.7050342](https://doi.org/10.5281/zenodo.7050342)) | CC0 1.0 |
| `f14/tenseurs/` | comparaison des poids des modèles affinés sur MAKHZAN (aucun texte ni image) | CC BY-NC-SA 4.0, comme les modèles |

## Modèle publié

Le modèle affiné sur MAKHZAN (`ota_naskh_makhzan_v0.1.0`, décisions 44 et 45) est aussi sous CC BY-NC-SA 4.0 : voir [MODEL_CARD.md](../MODEL_CARD.md).
