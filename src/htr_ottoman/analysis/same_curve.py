"""Contrôle de déterminisme : deux entraînements aux mêmes réglages et à la même seed
doivent avoir les mêmes métriques, époque par époque (F12, décision 43).

Compare la perte d'entraînement et la précision de validation de kraken (donc
son CER) de deux fichiers de métriques écrits par `train`
(reports/training/<config>.csv, ou models/<config>/metriques.csv pour un essai),
à la précision où ils sont écrits (6 décimales), de l'époque 1 à `--until`.
La règle d'arrêt n'entre pas dans le calcul d'une époque : F8 (lag 5) et
f8_lag15_seed42 doivent donc suivre la même courbe jusqu'à l'arrêt de F8.

Contrôle prévu : f8_lag15_seed42 contre F8 jusqu'à l'époque 91.
Code de sortie 1 si les courbes diffèrent, ou si l'une s'arrête avant `--until`.

Usage : uv run python -m htr_ottoman.analysis.same_curve --reference reports/training/f8_finetune.csv --run reports/training/f8_lag15_seed42.csv --until 91
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

COLUMNS = ["perte_train", "val_accuracy"]


def compare_curves(reference: pd.DataFrame, run: pd.DataFrame, until: int) -> dict:
    """Époques comparées, première époque différente (None si aucune) et plus grands écarts."""
    epochs = min(until, len(reference), len(run))
    ref = reference.set_index("epoque").loc[1:epochs, COLUMNS]
    new = run.set_index("epoque").loc[1:epochs, COLUMNS]
    if list(ref.index) != list(range(1, epochs + 1)) or list(new.index) != list(ref.index):
        raise ValueError("Époques manquantes ou désordonnées")
    differs = (ref != new).any(axis=1)
    return {
        "epoques_comparees": epochs,
        "attendues": until,
        "premiere_difference": int(differs.idxmax()) if differs.any() else None,
        **{f"ecart_max_{c}": float((ref[c] - new[c]).abs().max()) for c in COLUMNS},
        "identiques": bool(epochs == until and not differs.any()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference", type=Path, required=True, help="métriques par époque de référence (CSV)")
    parser.add_argument("--run", type=Path, required=True, help="métriques par époque à contrôler (CSV)")
    parser.add_argument("--until", type=int, required=True, help="dernière époque comparée")
    args = parser.parse_args()
    result = compare_curves(pd.read_csv(args.reference), pd.read_csv(args.run), args.until)
    for key, value in result.items():
        print(f"{key} : {value}")
    print("-> courbes identiques" if result["identiques"] else "-> COURBES DIFFÉRENTES ou arrêt avant --until")
    sys.exit(0 if result["identiques"] else 1)


if __name__ == "__main__":
    main()
