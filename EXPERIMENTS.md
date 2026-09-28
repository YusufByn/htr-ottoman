# Journal des expériences

| Date | Commit | Données | Modèle de départ | Paramètres | CER val | CER test | Remarques |
|------|--------|---------|------------------|------------|---------|----------|-----------|
| 2026-09-28 | eff4c74 + F4 non committé | train (2 763 lignes) / val (412), `data/processed/makhzan/*.arrow`, anciens polygones | OpenITI ottoman imprimé (10.5281/zenodo.7050342) | **Test technique F4, non retenu.** `ketos -d auto -s 42 train --load … -f binary --resize union -N 1 --quit fixed -B 16 -u NFD -n --reorder`, MPS | 22,1 % (précision caractère kraken 0,779, ordre d'affichage) | non mesuré | Vérifie la chaîne complète et mesure la durée : 1 époque = 1 min 50 d'entraînement, 9 min au total. `--resize union` seulement pour l'essai (choix du codec en F8). CER calculé par kraken, pas par `evaluate` (F5) : non comparable aux expériences suivantes. Modèle jeté. |
