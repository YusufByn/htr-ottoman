"""F13, Q5, après la lecture à l'aveugle : « . » oubliés et ajoutés sur la validation.

Pour la baseline, F8 (lag 5) et F8 lag 15 seed 42, prédictions déjà sauvegardées
(`reports/<modèle>/val/lignes.parquet`), validation seulement : chaque prédiction
normalisée est alignée sur sa vérité terrain (`error_analysis.align`, celui
d'`evaluate`, vérifié ligne par ligne contre ses S, D, I). Pour chaque manuscrit :
« . » de référence, lus (alignés sur un « . »), oubliés (supprimés ou remplacés),
ajoutés (insérés, ou écrits à la place d'un autre caractère), « . » écrits.
Aucun modèle chargé, aucune prédiction faite.

Sortie : reports/f13/q5_points/validation_points.csv.

Usage : uv run python -m htr_ottoman.analysis.period_errors
"""
import pandas as pd

from htr_ottoman.analysis.error_analysis import align
from htr_ottoman.analysis.rare_chars import check_alignment
from htr_ottoman.config import REPORTS, ROOT

PERIOD = "."
SPLIT = "val"
MODELS = {"baseline": REPORTS / "baseline" / SPLIT, "f8_finetune": REPORTS / "f8_finetune" / SPLIT,
          "f8_lag15_seed42": REPORTS / "f8_lag15_seed42" / SPLIT}
OUTPUT = REPORTS / "f13" / "q5_points" / "validation_points.csv"


def counts(pairs: list[tuple[str, str]]) -> dict[str, int]:
    return {
        "reference": sum(r == PERIOD for r, _ in pairs),
        "lus": sum(r == PERIOD and h == PERIOD for r, h in pairs),
        "oublies_supprimes": sum(r == PERIOD and not h for r, h in pairs),
        "oublies_remplaces": sum(bool(r == PERIOD and h and h != PERIOD) for r, h in pairs),
        "ajoutes_inseres": sum(not r and h == PERIOD for r, h in pairs),
        "ajoutes_a_la_place": sum(bool(r and r != PERIOD and h == PERIOD) for r, h in pairs),
        "ecrits": sum(h == PERIOD for _, h in pairs),
    }


def model_table(name: str, directory) -> pd.DataFrame:
    lines = pd.read_parquet(directory / "lignes.parquet")
    if set(lines["split"]) != {SPLIT}:
        raise ValueError(f"{directory} : jeu {sorted(set(lines['split']))}, validation seulement")
    check_alignment(lines, str(directory.relative_to(ROOT)))
    rows = []
    for doc, group in [(str(d), g) for d, g in lines.groupby("doc_id")] + [("tout", lines)]:
        pairs = [p for line in group.itertuples() for p in align(line.ref_norm, line.hyp_norm)]
        rows.append({"modele": name, "doc_id": doc, **counts(pairs)})
    return pd.DataFrame(rows)


def main() -> None:
    table = pd.concat([model_table(name, path) for name, path in MODELS.items()], ignore_index=True)
    table.to_csv(OUTPUT, index=False, lineterminator="\n")
    print(table.to_string(index=False))
    print(f"-> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
