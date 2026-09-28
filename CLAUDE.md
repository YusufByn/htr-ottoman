# Projet HTR ottoman

## Objectif
Affiner le modèle kraken ottoman imprimé d'OpenITI sur la partie ottomane de MAKHZAN, puis mesurer sa généralisation sur un jeu de test externe de manuscrits, en cours de choix (F10). Akis est écarté : transcriptions en alphabet latin, imprimé (décision 40). Projet de recherche et portfolio.

## Façon de travailler
- L'utilisateur débute en ML : expliquer brièvement chaque concept et chaque commande avant de l'exécuter.
- Une étape à la fois. En français, réponses courtes, pas de cadratins.
- En cas d'erreur, montrer l'erreur exacte avant de corriger.

## Tickets (ROADMAP.md)
- Quand l'utilisateur dit « fais Fx » : lire le ticket Fx dans ROADMAP.md et passer son statut à « en cours ».
- Expliquer le concept prévu dans le ticket avant de coder.
- S'arrêter à chaque point de décision du ticket et demander à l'utilisateur.
- À la fin : mettre à jour le statut du ticket, ARCHITECTURE.md, PROJECT.md et les journaux concernés (DECISIONS.md, EXPERIMENTS.md).

## Environnement
- Python 3.13, dépendances gérées par uv (pyproject.toml + uv.lock). Toujours lancer les commandes via `uv run`.
- Recréer l'environnement : `uv sync`.
- Accélération GPU via MPS (Apple Silicon).

## Règles méthodologiques (non négociables)
- Découpage train/val/test par manuscrit, jamais par page. Le split est figé dans des fichiers versionnés (splits/) avec une seed.
- Le jeu de test externe ne sert qu'à l'évaluation finale, jamais au réglage. Un jeu retenu comme test ne pourra plus jamais servir à l'entraînement (F15 compris).
- Exclure de l'entraînement les lignes sans transcription.
- Toute normalisation de texte passe par une seule fonction (src/htr_ottoman/normalize.py), appliquée de la même façon à la vérité terrain et aux prédictions. Chaque règle est documentée.
- Conserver pour chaque page sa catégorie de relecture (relue une ou deux fois) et son écriture (naskh, ta'liq, etc.).

## Reproductibilité
- Tout entraînement ou évaluation est consigné dans EXPERIMENTS.md.
- Toute décision méthodologique est consignée dans DECISIONS.md (date, décision, justification).
- ARCHITECTURE.md et PROJECT.md sont mis à jour à chaque étape terminée.
- Tout traitement passe par un module du package src/htr_ottoman/, aucune manipulation manuelle non tracée. Lancement : `uv run python -m htr_ottoman.<module>`.
- src/htr_ottoman/ contient les traitements de données, scripts/ les utilitaires (vérification d'environnement, etc.).
- notebooks/ sert uniquement à l'exploration visuelle : aucun code du pipeline n'en dépend.
- Les chemins du projet sont définis une seule fois dans src/htr_ottoman/config.py.
- Tests dans tests/, lancés avec `uv run pytest`.

## Données et licences
- data/ et models/ hors git. data/raw/ ne doit jamais être modifié ni supprimé.
- MAKHZAN : CC BY-NC-SA, tout modèle dérivé sous la même licence.
- Akis : Apache 2.0, citer Tasdemir et al., DAS 2024. Téléchargé et inventorié en F10, écarté comme test (décision 40).
- Modèle de départ : OpenITI ottoman imprimé, DOI 10.5281/zenodo.7050342, CC0, vérité terrain en NFD.
- Demander avant tout téléchargement de plus de 1 Go ou tout entraînement long.
