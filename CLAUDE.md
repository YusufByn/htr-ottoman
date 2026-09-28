# Projet HTR ottoman

## Objectif
Affiner le modèle kraken ottoman imprimé d'OpenITI sur la partie ottomane de MAKHZAN, puis mesurer sa généralisation sur le jeu de test Akis. Projet de recherche et portfolio.

## Façon de travailler
- L'utilisateur débute en ML : expliquer brièvement chaque concept et chaque commande avant de l'exécuter.
- Une étape à la fois. En français, réponses courtes, pas de cadratins.
- En cas d'erreur, montrer l'erreur exacte avant de corriger.

## Environnement
- Python 3.13, dépendances gérées par uv (pyproject.toml + uv.lock). Toujours lancer les commandes via `uv run`.
- Recréer l'environnement : `uv sync`.
- Accélération GPU via MPS (Apple Silicon).

## Règles méthodologiques (non négociables)
- Découpage train/val/test par manuscrit, jamais par page. Le split est figé dans des fichiers versionnés (splits/) avec une seed.
- Le jeu de test Akis ne sert qu'à l'évaluation finale, jamais au réglage.
- Exclure de l'entraînement les lignes sans transcription.
- Toute normalisation de texte passe par une seule fonction (src/normalize.py), appliquée de la même façon à la vérité terrain et aux prédictions. Chaque règle est documentée.
- Conserver pour chaque page sa catégorie de relecture (relue une ou deux fois) et son écriture (naskh, ta'liq, etc.).

## Reproductibilité
- Tout entraînement ou évaluation est consigné dans EXPERIMENTS.md.
- Toute décision méthodologique est consignée dans DECISIONS.md (date, décision, justification).
- Tout traitement passe par un script dans src/, aucune manipulation manuelle non tracée.
- src/ contient les traitements de données, scripts/ les utilitaires (vérification d'environnement, etc.).

## Données et licences
- data/ et models/ hors git. data/raw/ ne doit jamais être modifié ni supprimé.
- MAKHZAN : CC BY-NC-SA, tout modèle dérivé sous la même licence.
- Akis : Apache 2.0, citer Tasdemir et al., DAS 2024.
- Modèle de départ : OpenITI ottoman imprimé, DOI 10.5281/zenodo.7050342, CC0, vérité terrain en NFD.
- Demander avant tout téléchargement de plus de 1 Go ou tout entraînement long.
