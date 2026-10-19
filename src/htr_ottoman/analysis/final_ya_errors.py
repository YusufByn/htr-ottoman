"""F13, Q4, après la lecture à l'aveugle : jugements par case et confusions ي / ى.

- Confusions (validation, prédictions sauvegardées de la baseline, de F8 (lag 5) et de
  F8 lag 15 seed 42) : pour chaque ي ou ى de la vérité terrain (ئ exclu), par
  manuscrit (2937, 2939), par lettre (sens de la confusion) et par position (fin de
  mot comme la règle 5 de `normalize`, milieu) : correct, confondu (l'autre lettre),
  autre (supprimée ou autre lettre). Alignement d'`error_analysis.align`, vérifié
  contre les S, D, I d'`evaluate`.
- Jugements de l'utilisateur (`jugements.csv`, jamais modifié) croisés avec les cases
  du tirage (`echantillon.csv`) : réponses oui / non / incertain par case, proportions
  brutes sur l'échantillon et proportions pondérées (poids de tirage) pour les 280 fins
  de mot de Doc 2937 ; la case ى × confondu (2 éléments, pris en entier) est aussi
  montrée à part, descriptive seulement.
- Lectures : lecture 1, réponses telles quelles ; lecture 2, mécanique, d'après les
  commentaires de l'utilisateur (MECHANICAL), selon les critères affichés sur la page ;
  lecture 3 = lecture 2 + RIGHT_DOTS en incertain (« autre lettre ? »), règle fixée par
  l'utilisateur après avoir vu les tableaux de la lecture 2 ; contrôle de sensibilité :
  lecture 2, lecture 3, et lecture 2 + RIGHT_DOTS en non (SENSITIVITY).
- Train (vérité terrain seulement, lignes gardées) : ي et ى en fin de mot et au milieu,
  par manuscrit (après `normalize`, ئ exclu), pour la piste F15 sur l'usage de ى en fin de mot.
- Aucun modèle chargé, aucune prédiction faite.

Sorties (reports/f13/q4_ya_final/) : confusions.csv, train_ya.csv, lecture_mecanique.csv,
jugements_par_case.csv, estimation_ponderee.csv.

Usage : uv run python -m htr_ottoman.analysis.final_ya_errors
"""
import unicodedata

import pandas as pd

from htr_ottoman.analysis.error_analysis import align
from htr_ottoman.analysis.final_ya import ANSWERS, HAMZA_ABOVE, OUTPUT
from htr_ottoman.analysis.period_errors import MODELS
from htr_ottoman.analysis.rare_chars import check_alignment
from htr_ottoman.config import ROOT
from htr_ottoman.normalize import ALEF_MAKSURA, YEH
from htr_ottoman.prepare import select_lines

DOCS = (2937, 2939)
OUTCOMES = ("correct", "confondu", "autre")
# Lecture 2 : seuls les commentaires qui décrivent une boîte décalée changent la réponse
# (critère de la page : marque hors de la boîte = incertain, « boîte décalée »).
MECHANICAL = {
    "q4_16": ("incertain", "boîte décalée : « le 2eme [point] est en dehors » de la boîte"),
    "q4_20": ("incertain", "boîte décalée : « les 2 points sont à 30% dans l'encadré » (réponse inchangée)"),
    "q4_38": ("incertain", "boîte décalée : « 2 points mais hors du cadre »"),
}
# Lecture 3, règle fixée après la lecture 2 : tout commentaire décrivant l'absence de deux points
# sous la fin du mot et deux points sous une partie plus à droite du mot.
RIGHT_DOTS = ("q4_14", "q4_15", "q4_19", "q4_27", "q4_37")
SENSITIVITY = {"lecture 2": None, "lecture 3": "incertain", "cinq en non": "non"}


def yeh_positions(text: str) -> dict[int, str]:
    """Index des ي et ى (hors ي + hamza, soit ئ) et leur position : fin (règle 5 de `normalize`) ou milieu."""
    positions = {}
    for i, c in enumerate(text):
        if c not in (YEH, ALEF_MAKSURA):
            continue
        j = i + 1
        while j < len(text) and unicodedata.category(text[j]).startswith("M"):
            j += 1
        if HAMZA_ABOVE in text[i + 1:j]:
            continue
        positions[i] = "fin" if j == len(text) or not unicodedata.category(text[j]).startswith("L") else "milieu"
    return positions


def yeh_outcomes(reference: str, hypothesis: str) -> list[dict]:
    positions, rows, index = yeh_positions(reference), [], 0
    for r, h in align(reference, hypothesis):
        if r and index in positions:
            other = ALEF_MAKSURA if r == YEH else YEH
            issue = "correct" if h == r else "confondu" if h == other else "autre"
            rows.append({"lettre": r, "position": positions[index], "issue": issue})
        if r:
            index += 1
    return rows


def confusions() -> pd.DataFrame:
    rows = []
    for model, directory in MODELS.items():
        lines = pd.read_parquet(directory / "lignes.parquet")
        if set(lines["split"]) != {"val"}:
            raise ValueError("Prédictions de la validation seulement")
        check_alignment(lines, str(directory.relative_to(ROOT)))
        lines = lines[lines["doc_id"].isin(DOCS)]
        rows += [{"modele": model, "doc_id": l.doc_id, **o}
                 for l in lines.itertuples() for o in yeh_outcomes(l.ref_norm, l.hyp_norm)]
    table = pd.DataFrame(rows).groupby(["modele", "doc_id", "lettre", "position"])["issue"].value_counts()
    table = table.unstack(fill_value=0).reindex(columns=OUTCOMES, fill_value=0)
    table.insert(0, "reference", table.sum(axis=1))
    return table.reset_index()


def train_counts() -> pd.DataFrame:
    lines = select_lines()
    lines = lines[(lines["split"] == "train") & lines["exclusion"].isna()]
    rows = [{"doc_id": l.doc_id, "lettre": l.norm[i], "position": p}
            for l in lines.itertuples() for i, p in yeh_positions(l.norm).items()]
    table = pd.DataFrame(rows).groupby(["doc_id", "position"])["lettre"].value_counts().unstack(fill_value=0)
    table = table.reindex(columns=[YEH, ALEF_MAKSURA], fill_value=0).unstack("position", fill_value=0)
    table.columns = [f"{l} {p}" for l, p in table.columns]
    table.loc["total"] = table.sum()
    return table.reset_index()


def judged() -> pd.DataFrame:
    sample = pd.read_csv(OUTPUT / "echantillon.csv")
    answers = pd.read_csv(OUTPUT / "jugements.csv", keep_default_na=False)
    if answers["identifiant"].tolist() != sample["identifiant"].tolist() or (answers["réponse"] == "").any():
        raise ValueError("jugements.csv incomplet ou non aligné sur l'échantillon")
    merged = sample.merge(answers, on="identifiant", validate="one_to_one")
    merged["lecture 1"] = merged["réponse"]
    merged["lecture 2"] = [MECHANICAL.get(i, (r, ""))[0] for i, r in zip(merged["identifiant"], merged["réponse"])]
    merged["règle lecture 2"] = [MECHANICAL.get(i, ("", ""))[1] for i in merged["identifiant"]]
    for name, answer in SENSITIVITY.items():
        if answer:
            merged[name] = merged["lecture 2"].where(~merged["identifiant"].isin(RIGHT_DOTS), answer)
    merged["règle lecture 3"] = ["deux points sous une partie plus à droite du mot : incertain, « autre lettre ? »"
                                 if i in RIGHT_DOTS else "" for i in merged["identifiant"]]
    return merged


def by_case(table: pd.DataFrame, reading: str) -> pd.DataFrame:
    counts = table.groupby(["case", "taille_case", "n_case", "poids"])[reading].value_counts()
    counts = counts.unstack(fill_value=0).reindex(columns=ANSWERS, fill_value=0).reset_index()
    for a in ANSWERS:
        counts[f"{a} (brut)"] = (counts[a] / counts["n_case"]).round(3)
    return counts.assign(lecture=reading)


def weighted(table: pd.DataFrame, reading: str) -> pd.DataFrame:
    """Proportions pondérées (estimation pour la population) et brutes, par lettre et pour les 280 fins de mot."""
    table = table.assign(lettre=table["case"].str[0])
    groups = [(f"{l} (fins de mot correctes ou confondues)", table[table["lettre"] == l]) for l in (YEH, ALEF_MAKSURA)]
    groups.append(("toutes (280 fins de mot de Doc 2937)", table))
    rows = []
    for name, group in groups:
        row = {"lecture": reading, "groupe": name, "population": round(group["poids"].sum()), "tirés": len(group)}
        for a in ANSWERS:
            hit = group[reading] == a
            row[f"{a} (pondéré)"] = round(group.loc[hit, "poids"].sum() / group["poids"].sum(), 3)
            row[f"{a} (brut)"] = round(hit.mean(), 3)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    conf = confusions()
    table = judged()
    readings = ("lecture 1", *SENSITIVITY)
    cases = pd.concat([by_case(table, r) for r in readings], ignore_index=True)
    estimates = pd.concat([weighted(table, r) for r in readings], ignore_index=True)
    conf.to_csv(OUTPUT / "confusions.csv", index=False, lineterminator="\n")
    train = train_counts()
    train.to_csv(OUTPUT / "train_ya.csv", index=False, lineterminator="\n")
    table[["identifiant", "case", *readings, "règle lecture 2", "règle lecture 3"]].to_csv(
        OUTPUT / "lecture_mecanique.csv", index=False, lineterminator="\n")
    cases.to_csv(OUTPUT / "jugements_par_case.csv", index=False, lineterminator="\n")
    estimates.to_csv(OUTPUT / "estimation_ponderee.csv", index=False, lineterminator="\n")
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print(train.to_string(index=False))
        print(cases.to_string(index=False))
        print(estimates.to_string(index=False))
        print(table.loc[table["case"] == f"{ALEF_MAKSURA} × confondu", ["identifiant", "lecture 1", "commentaire"]]
              .to_string(index=False))
    print(f"-> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
