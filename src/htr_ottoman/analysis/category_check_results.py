"""F13, Q1, après la lecture : taux d'accord par catégorie et sommes conventions / lecture.

Lit les jugements de l'utilisateur (JUDGMENTS, emplacement choisi par l'utilisateur ;
100 réponses non vides oui / non / incertain, une par entrée d'`echantillon.csv`, sinon
arrêt), l'échantillon de `category_check` (modèle, catégorie, poids) et les tableaux
déjà calculés d'`error_analysis` : test interne en mode exploratoire
(reports/f13/q1_conventions/test_interne/categories.csv) et validation (F12, étape 1,
reports/erreurs/f8_finetune_baseline/val/categories.csv). Aucune prédiction lue ni
faite, aucun modèle. Comptes et taux seulement : ni IC, ni verdict.

- Taux d'accord d'une catégorie = oui / nombre d'entrées tirées.
- Taux global brut = oui / 100 ; pondéré = somme des poids des oui / somme des poids
  (poids = taille de la catégorie, deux modèles réunis, / nombre tiré).
- Par modèle : comptes seulement (pas de taux par modèle, précision du 2026-10-20).
- Sommes de points de CER par groupe, sous les deux regroupements : celui du plan
  (124a7c8) et celui de la précision du 2026-10-20 (9563904, espace à part).

Sorties (reports/f13/q1_conventions/, mention « exploratoire, décision 39 ») :
accord_par_categorie.csv, accord_par_modele.csv, accord_global.csv, regroupements.csv.

Usage : uv run python -m htr_ottoman.analysis.category_check_results
"""
import pandas as pd

from htr_ottoman.analysis.category_check import ANSWERS, OUTPUT as SAMPLE_DIR
from htr_ottoman.analysis.error_analysis import CATEGORIES, MENTION
from htr_ottoman.config import REPORTS, ROOT

Q1 = REPORTS / "f13" / "q1_conventions"
JUDGMENTS = Q1 / "jugements.csv"
TEST = Q1 / "test_interne" / "categories.csv"
VALIDATION = REPORTS / "erreurs" / "f8_finetune_baseline" / "val" / "categories.csv"
MODELS = ("baseline", "f8_finetune")
GROUPINGS = {
    "plan (124a7c8)": {
        "conventions": ["espace", "séparateur .", "ي / ى", "ئ", "chiffre", "ponctuation"],
        "lecture": ["même squelette (points)", "autre substitution", "autre suppression", "autre insertion"],
    },
    "précision du 2026-10-20 (9563904)": {
        "conventions": ["séparateur .", "ponctuation", "ئ", "ي / ى"],
        "lecture": ["chiffre", "même squelette (points)", "autre substitution", "autre suppression", "autre insertion"],
        "espace (à part)": ["espace"],
    },
}


def judged() -> pd.DataFrame:
    sample = pd.read_csv(SAMPLE_DIR / "echantillon.csv")
    answers = pd.read_csv(JUDGMENTS, keep_default_na=False)
    if (len(answers) != 100 or answers["identifiant"].tolist() != sample["identifiant"].tolist()
            or not answers["réponse"].isin(ANSWERS).all()):
        raise ValueError(f"{JUDGMENTS} : il faut 100 réponses oui / non / incertain, "
                         "une par entrée d'echantillon.csv, dans le même ordre")
    return sample.merge(answers, on="identifiant", validate="one_to_one")


def answer_counts(table: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    counts = table.groupby(keys, sort=False)["réponse"].value_counts().unstack(fill_value=0)
    counts = counts.reindex(columns=ANSWERS, fill_value=0)
    counts.insert(0, "tirées", counts.sum(axis=1))
    return counts


def by_category(table: pd.DataFrame) -> pd.DataFrame:
    counts = answer_counts(table, ["categorie"]).reindex(CATEGORIES)
    counts.insert(0, "erreurs (deux modèles)", table.groupby("categorie")["taille_categorie"].first())
    counts["taux d'accord"] = counts["oui"] / counts["tirées"]
    return counts


def by_model(table: pd.DataFrame) -> pd.DataFrame:
    counts = answer_counts(table, ["categorie", "modele"])
    return counts.reindex(pd.MultiIndex.from_product([CATEGORIES, MODELS]), fill_value=0)


def overall(table: pd.DataFrame) -> pd.DataFrame:
    yes = table["réponse"] == "oui"
    return pd.DataFrame([{"tirées": len(table), "oui": int(yes.sum()), "taux brut": yes.mean(),
                          "taux pondéré": table.loc[yes, "poids"].sum() / table["poids"].sum()}])


def groupings(categories: pd.DataFrame) -> pd.DataFrame:
    test = pd.read_csv(TEST, index_col=0)
    val = pd.read_csv(VALIDATION, index_col=0)
    rows = []
    for grouping, groups in GROUPINGS.items():
        for group, members in groups.items():
            row = {"regroupement": grouping, "groupe": group, "catégories": ", ".join(members)}
            for split, table in (("test interne", test), ("validation", val)):
                for model in MODELS:
                    row[f"points {split} {model}"] = table.loc[members, f"points_cer_{model}"].sum()
                row[f"gain {split}"] = row[f"points {split} baseline"] - row[f"points {split} f8_finetune"]
                total_gain = (table.loc["total", "points_cer_baseline"] - table.loc["total", "points_cer_f8_finetune"])
                row[f"part du gain {split}"] = row[f"gain {split}"] / total_gain
            judged_members = categories.loc[members]
            row["oui / tirées"] = f"{int(judged_members['oui'].sum())} / {int(judged_members['tirées'].sum())}"
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    table = judged()
    categories = by_category(table)
    models = by_model(table)
    total = overall(table)
    groups = groupings(categories)
    for name, out, index in (("accord_par_categorie", categories, True), ("accord_par_modele", models, True),
                             ("accord_global", total, False), ("regroupements", groups, False)):
        out.assign(mention=MENTION).to_csv(Q1 / f"{name}.csv", index=index, lineterminator="\n",
                                           float_format="%.6f")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        for out in (categories, models, total, groups):
            print(out.to_string(float_format=lambda x: f"{x:.3f}"), "\n")
    print(f"-> {Q1.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
