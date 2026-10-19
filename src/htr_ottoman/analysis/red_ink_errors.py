"""F13, Q3, après la lecture à l'aveugle : lecture des points rouges par les modèles.

- Validation, Doc 2937 (points rouges • ramenés à « . », décision 21) : pour chaque
  « . » de la vérité terrain, son issue dans la prédiction de la baseline, de F8 (lag 5)
  et de F8 lag 15 seed 42 (prédictions sauvegardées) : lu (aligné sur un « . »),
  supprimé, ou remplacé (et par quoi). Alignement d'`error_analysis.align`, vérifié
  contre les S, D, I d'`evaluate`.
- Croisement, sur les 40 « . » de l'échantillon, entre le jugement de l'utilisateur
  sur l'image en gris (`jugements.csv`) et l'issue de chaque modèle.
- Test interne, Doc 3230 (trois points rouges ؞ ramenés à « . », décision 21),
  descriptif seulement (décision 39) : mêmes issues pour la baseline et F8 (lag 5),
  prédictions déjà sauvegardées.
- Aucun modèle chargé, aucune prédiction faite.

Sorties (reports/f13/q3_encre_rouge/) : points_2937.csv (une ligne par « . » et par
modèle), resume_2937.csv, croisement_gris.csv, doc3230_test_interne.csv.

Usage : uv run python -m htr_ottoman.analysis.red_ink_errors
"""
import pandas as pd

from htr_ottoman.analysis.error_analysis import align
from htr_ottoman.analysis.period_errors import MODELS
from htr_ottoman.analysis.rare_chars import check_alignment
from htr_ottoman.config import REPORTS, ROOT

PERIOD = "."
DOC_VAL, DOC_TEST = 2937, 3230
OUTPUT = REPORTS / "f13" / "q3_encre_rouge"
TEST_MODELS = {"baseline": REPORTS / "baseline" / "test_interne", "f8_finetune": REPORTS / "f8_finetune" / "test_interne"}
NOTE = "exploratoire, décision 39 (prédictions sauvegardées, descriptif)"
OUTCOMES = ("lu", "supprimé", "remplacé")


def period_outcomes(reference: str, hypothesis: str) -> list[dict]:
    """Issue de chaque « . » de la référence : index dans la référence, issue, caractère prédit."""
    rows, index = [], 0
    for r, h in align(reference, hypothesis):
        if r == PERIOD:
            outcome = "lu" if h == PERIOD else "supprimé" if not h else "remplacé"
            rows.append({"index_caractere": index, "issue": outcome, "predit": h})
        if r:
            index += 1
    return rows


def outcomes_table(directory, doc: int, model: str) -> pd.DataFrame:
    lines = pd.read_parquet(directory / "lignes.parquet")
    lines = lines[lines["doc_id"] == doc]
    check_alignment(lines, str(directory.relative_to(ROOT)))
    rows = [{"modele": model, "doc_id": doc, "part_id": l.part_id, "line_id": l.line_id, **o}
            for l in lines.itertuples() for o in period_outcomes(l.ref_norm, l.hyp_norm)]
    return pd.DataFrame(rows)


def summary(table: pd.DataFrame) -> pd.DataFrame:
    counts = table.groupby("modele")["issue"].value_counts().unstack(fill_value=0).reindex(columns=OUTCOMES, fill_value=0)
    counts.insert(0, "reference", counts.sum(axis=1))
    replaced = table[table["issue"] == "remplacé"].groupby("modele")["predit"].agg(
        lambda s: " ".join(f"{c} ×{n}" for c, n in s.value_counts().head(3).items()))
    return counts.assign(remplace_le_plus_par=replaced).fillna({"remplace_le_plus_par": ""}).reset_index()


def crossing(points: pd.DataFrame) -> pd.DataFrame:
    sample = pd.read_csv(OUTPUT / "echantillon.csv")
    judged = sample.merge(pd.read_csv(OUTPUT / "jugements.csv", keep_default_na=False), on="identifiant")
    merged = judged.merge(points, on=["line_id", "index_caractere"], how="left", validate="one_to_many")
    if merged["issue"].isna().any() or len(merged) != len(judged) * points["modele"].nunique():
        raise ValueError("Échantillon et issues des modèles non alignés")
    table = merged.groupby(["modele", "réponse gris"])["issue"].value_counts().unstack(fill_value=0)
    return table.reindex(columns=OUTCOMES, fill_value=0).reset_index()


def main() -> None:
    points = pd.concat([outcomes_table(path, DOC_VAL, name) for name, path in MODELS.items()], ignore_index=True)
    test = pd.concat([outcomes_table(path, DOC_TEST, name) for name, path in TEST_MODELS.items()], ignore_index=True)
    test_summary = summary(test).assign(note=NOTE)
    points.to_csv(OUTPUT / "points_2937.csv", index=False, lineterminator="\n")
    summary(points).to_csv(OUTPUT / "resume_2937.csv", index=False, lineterminator="\n")
    crossing(points).to_csv(OUTPUT / "croisement_gris.csv", index=False, lineterminator="\n")
    test_summary.to_csv(OUTPUT / "doc3230_test_interne.csv", index=False, lineterminator="\n")
    with pd.option_context("display.width", 200):
        print(summary(points).to_string(index=False))
        print(crossing(points).to_string(index=False))
        print(test_summary.drop(columns="note").to_string(index=False))
    print(f"-> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
