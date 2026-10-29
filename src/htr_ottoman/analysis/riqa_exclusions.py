"""RiqaTestset : lignes exclues du critère principal d'après la lecture des signes (décision 49),
sans aucune prédiction ni aucun modèle.

Croise reports/riqa/lecture/jugements.csv (réponses de l'utilisateur) avec echantillon.csv
(identifiant, ligne, unité, famille), lus seulement, jamais modifiés. Règle fixée avant le
croisement (décision 49) : réponse « oui », ligne gardée ; réponse « non » (commentaires
« doute » et « illisible » compris), ligne exclue. Une ligne à plusieurs entrées (une par
famille) est exclue dès qu'une de ses entrées est « non ».

Sortie : reports/riqa/lecture/exclusions.csv, une ligne par réponse « non » : identifiant,
line_id, unité, famille. Jamais de transcription (décision 46). Les commentaires et les
chiffres agrégés sont seulement affichés.

Usage : uv run python -I -m htr_ottoman.analysis.riqa_exclusions
"""
import pandas as pd

from htr_ottoman.analysis.riqa_reading import ANSWERS, HEADER, NAMES, OUTPUT
from htr_ottoman.config import RIQA_LINES, ROOT
from htr_ottoman.normalize import normalize

COLUMNS = ("identifiant", "line_id", "unite", "famille")
FLAGS = ("doute", "illisible")  # commentaires prévus par le critère de la page, qui vont avec « non »


def cross(judgements: pd.DataFrame, sample: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par entrée, réponse et commentaire joints ; contrôle que les deux fichiers concordent."""
    if list(judgements.columns) != list(HEADER):
        raise ValueError(f"jugements.csv : colonnes inattendues {list(judgements.columns)}")
    if sorted(judgements["identifiant"]) != sorted(sample["identifiant"]) or judgements["identifiant"].duplicated().any():
        raise ValueError("jugements.csv et echantillon.csv n'ont pas les mêmes identifiants")
    bad = set(judgements["réponse"]) - set(ANSWERS)
    if bad:
        raise ValueError(f"réponses inattendues : {sorted(bad)}")
    table = sample.merge(judgements, on="identifiant", validate="one_to_one")
    table["commentaire"] = table["commentaire"].fillna("").str.strip()
    table["signale"] = table["commentaire"].str.lower().str.contains("|".join(FLAGS))
    return table


def summary(table: pd.DataFrame) -> pd.DataFrame:
    """Par forme : oui, non, et parmi les non ceux qui portent « doute » ou « illisible »."""
    non = table["réponse"] == "non"
    rows = [{"forme": NAMES[f], "oui": int((g["réponse"] == "oui").sum()), "non": int((g["réponse"] == "non").sum()),
             "non_doute_ou_illisible": int((g["signale"] & non[g.index]).sum())}
            for f, g in table.groupby("famille", sort=True)]
    out = pd.DataFrame(rows)
    return pd.concat([out, out.drop(columns="forme").sum().to_frame().T.assign(forme="total")], ignore_index=True)


def main() -> None:
    judgements = pd.read_csv(OUTPUT / "jugements.csv", dtype=str, keep_default_na=False)
    sample = pd.read_csv(OUTPUT / "echantillon.csv", dtype={"identifiant": str, "line_id": str, "unite": str})
    table = cross(judgements, sample)

    exclusions = table.loc[table["réponse"] == "non", list(COLUMNS)].sort_values("identifiant")
    exclusions.to_csv(OUTPUT / "exclusions.csv", index=False, lineterminator="\n")

    print("1. Réponses par forme")
    print(summary(table).to_string(index=False))

    print("\n2. Commentaires")
    for r in table[table["commentaire"] != ""].sort_values("identifiant").itertuples():
        print(f"  {r.identifiant} ({NAMES[r.famille]}, {r.réponse}) : {r.commentaire}")

    lines = pd.read_parquet(RIQA_LINES)
    n_chars = lines["text"].map(normalize).str.len()
    excluded = lines["line_id"].isin(exclusions["line_id"])
    print("\n3. Exclusions (décision 49)")
    print(f"  réponses « non » : {len(exclusions)}")
    print(f"  lignes exclues : {excluded.sum()} sur {len(lines)}")
    print(f"  unités touchées : {lines.loc[excluded, 'unit'].nunique()} sur {lines['unit'].nunique()}")
    print(f"  caractères exclus (après normalize) : {n_chars[excluded].sum()} sur {n_chars.sum()}"
          f" ({n_chars[excluded].sum() / n_chars.sum():.2%})")
    print(f"-> {(OUTPUT / 'exclusions.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
