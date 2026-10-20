"""F13, Q6, après la lecture : tableaux du plan pour Doc 3179 (test interne).

Mode exploratoire du test interne (décision 39, compléments du 2026-10-19 et du
2026-10-20) : prédictions déjà sauvegardées de la baseline et de F8 (lag 5) seulement,
lues après les contrôles d'`error_analysis.check_exploratory` (SHA-256, entrées, sortie
sous reports/f13/) ; tableaux par manuscrit repris du lancement exploratoire (b4bdb1b).
Aucun modèle chargé (ni `select_lines`, ni codec), aucune prédiction faite. Descriptif :
ni IC, ni verdict.

- Lignes de Doc 3179 : longueur (caractères de la vérité terrain), CER, S, D, I par
  modèle ; identifiant de lecture (q6_xx).
- Manuscrits : CER et taux de S, D, I (rapportés aux caractères) de chaque manuscrit du
  test interne ; Doc 3179 marqué.
- Catégories d'erreurs (celles de Q1) : points de CER de Doc 3179 et des autres
  manuscrits réunis.
- Pires lignes : règle d'`error_analysis` (au moins MIN_CHARS_WORST caractères, CER de
  F8 (lag 5) décroissant, N_WORST au plus).
- Croisement avec la lecture : CER (erreurs / caractères des lignes réunies) selon la
  réponse à D et à E ; « incertain » à part.

Sorties (reports/f13/q6_doc3179/, mention « exploratoire, décision 39 ») : lignes.csv,
manuscrits.csv, categories.csv, pires_lignes.csv, croisement_lecture.csv.

Usage : uv run python -m htr_ottoman.analysis.doc3179_results
"""
import pandas as pd

from htr_ottoman.analysis.doc3179 import DOC, OUTPUT
from htr_ottoman.analysis.error_analysis import (CATEGORIES, EXPLORATORY_INPUTS, EXPLORATORY_SPLIT, MENTION,
                                                 MIN_CHARS_WORST, N_WORST, check_exploratory, check_split)
from htr_ottoman.config import REPORTS, ROOT

EXPLORATORY_TABLES = REPORTS / "f13" / "q1_conventions" / "test_interne"  # lancement exploratoire (b4bdb1b)
MODELS = ("baseline", "f8_finetune")
CROSSED = ("D", "E")  # A, B, C et F : 13 « non » sur 13


def load_lines() -> pd.DataFrame:
    """Lignes de Doc 3179 des deux modèles, côte à côte, avec l'identifiant de lecture."""
    reference_dir, model_dir = EXPLORATORY_INPUTS
    check_exploratory(reference_dir, model_dir, OUTPUT)  # avant toute lecture
    tables = {}
    for directory in EXPLORATORY_INPUTS:
        lines = pd.read_parquet(directory / "lignes.parquet")
        check_split(lines, directory.parent.name, EXPLORATORY_SPLIT)
        tables[directory.parent.name] = lines[lines["doc_id"] == DOC].set_index("line_id")
    base, f8 = (tables[m] for m in MODELS)
    if set(base.index) != set(f8.index) or not base["ref_norm"].equals(f8.loc[base.index, "ref_norm"]):
        raise ValueError(f"Doc {DOC} : lignes ou vérité terrain différentes entre les deux modèles")
    sample = pd.read_csv(OUTPUT / "echantillon.csv").set_index("line_id")
    if set(sample.index) != set(base.index):
        raise ValueError(f"Doc {DOC} : lignes de la lecture différentes des lignes évaluées")
    out = pd.DataFrame({"identifiant": sample.loc[base.index, "identifiant"], "line_index": base["line_index"],
                        "caracteres": base["ref_chars"]}, index=base.index)
    for m in MODELS:
        t = tables[m].loc[base.index]
        out[f"cer_{m}"] = t["errors"] / t["ref_chars"]
        for col, label in (("substitutions", "S"), ("deletions", "D"), ("insertions", "I"), ("errors", "erreurs")):
            out[f"{label}_{m}"] = t[col]
    return out.sort_values("line_index").reset_index()


def manuscripts() -> pd.DataFrame:
    table = pd.read_csv(EXPLORATORY_TABLES / "par_manuscrit.csv").drop(columns="mention")
    for m in MODELS:
        for op in ("S", "D", "I"):
            table[f"taux_{op}_{m}"] = table[f"{op}_{m}"] / table["caracteres"]
    table.insert(1, "doc_3179", table["doc_id"] == DOC)
    return table.sort_values("cer_f8_finetune", ascending=False).reset_index(drop=True)


def categories() -> pd.DataFrame:
    by_doc = pd.read_csv(EXPLORATORY_TABLES / "categories_par_manuscrit.csv")
    chars = pd.read_csv(EXPLORATORY_TABLES / "par_manuscrit.csv").set_index("doc_id")["caracteres"]
    is_doc = by_doc["doc_id"] == DOC
    rows = {}
    for name, part, n in ((f"Doc {DOC}", by_doc[is_doc], chars[DOC]),
                          ("autres manuscrits", by_doc[~is_doc], chars.drop(DOC).sum())):
        errors = part.groupby("categorie")[[f"erreurs_{m}" for m in MODELS]].sum().reindex(CATEGORIES, fill_value=0)
        for m in MODELS:
            rows[(name, m)] = 100 * errors[f"erreurs_{m}"] / n
    table = pd.DataFrame(rows)
    table.loc["total"] = table.sum()
    table.columns = [f"points_cer {doc} {m}" for doc, m in table.columns]
    return table.rename_axis("categorie")


def worst(lines: pd.DataFrame) -> pd.DataFrame:
    long = lines[lines["caracteres"] >= MIN_CHARS_WORST]
    return long.sort_values(["cer_f8_finetune", "line_id"], ascending=[False, True]).head(N_WORST).reset_index(drop=True)


def crossing(lines: pd.DataFrame) -> pd.DataFrame:
    answers = pd.read_csv(OUTPUT / "jugements.csv", keep_default_na=False)
    if len(answers) != len(lines) or set(answers["identifiant"]) != set(lines["identifiant"]):
        raise ValueError("jugements.csv : une réponse par ligne de Doc 3179 attendue")
    merged = lines.merge(answers, on="identifiant", validate="one_to_one")
    rows = []
    for question in CROSSED:
        for answer, g in merged.groupby(question, sort=False):
            row = {"question": question, "réponse": answer, "lignes": len(g), "caracteres": int(g["caracteres"].sum()),
                   "identifiants": " ".join(sorted(g["identifiant"]))}
            for m in MODELS:
                row[f"cer_{m}"] = g[f"erreurs_{m}"].sum() / g["caracteres"].sum()
            rows.append(row)
    order = {"oui": 0, "non": 1, "incertain": 2}
    return pd.DataFrame(rows).sort_values(["question", "réponse"], key=lambda s: s.map(order).fillna(s)) \
        .reset_index(drop=True)


def main() -> None:
    lines = load_lines()
    outputs = {"lignes": lines, "manuscrits": manuscripts(), "categories": categories(), "pires_lignes": worst(lines),
               "croisement_lecture": crossing(lines)}
    for name, table in outputs.items():
        table.assign(mention=MENTION).to_csv(OUTPUT / f"{name}.csv", index=name == "categories",
                                             lineterminator="\n", float_format="%.6f")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        for name, table in outputs.items():
            print(f"== {name}\n{table.to_string(float_format=lambda x: f'{x:.3f}')}\n")
    print(f"-> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
