"""Découpage train / validation / test interne des pages ottomanes de MAKHZAN.

Règles (DECISIONS.md) :
- test_interne = pages ACDC-Evaluation (décision 1) ;
- val = œuvre *Manāfi' al-nās fī al-ṭibb* (décisions 2, 6, 7) ;
- train = le reste de Research.
Le groupe de découpage est l'œuvre (Title of Text) : toutes ses copies vont dans
le même jeu (décision 6). Doc 86 et 89, même cote, restent ensemble (décision 3).
Les pages multilingues sont gardées et marquées (décision 19).

L'affectation ne dépend d'aucun tirage aléatoire. La seed est enregistrée dans
les fichiers pour les tirages futurs (ordre des exemples, sous-échantillonnage).

Un fichier CSV par jeu dans splits/, une ligne par page, avec un en-tête en
commentaire. Pas de date dans l'en-tête : deux générations sont identiques
octet pour octet.

Usage : uv run python -m htr_ottoman.splits
"""
import io

import pandas as pd

from htr_ottoman.config import SPLITS
from htr_ottoman.data.makhzan import LANGUAGE, RECORD_ID, VERSION, load_metadata, ottoman_pages

SEED = 42
SPLIT_NAMES = ["train", "val", "test_interne"]
VALIDATION_WORK = "Manāfi' al-nās fī al-ṭibb"
LINKED_DOCS = [{"86", "89"}]  # même cote, toujours dans le même jeu (décision 3)
COLUMNS = ["doc_id", "part_id", "work", "script", "dataset_source", "is_multilingual"]


def assign(pages: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par page, avec son jeu. `pages` : lignes ottomanes du TSV."""
    source = pages["Dataset Source"]
    work = pages["Title of Text"]
    unexpected = set(source) - {"ACDC-Evaluation", "Research"}
    if unexpected:
        raise ValueError(f"Source de données inattendue pour des pages ottomanes : {unexpected}")

    split = pd.Series("train", index=pages.index)
    split[(source == "Research") & (work == VALIDATION_WORK)] = "val"
    split[source == "ACDC-Evaluation"] = "test_interne"

    return pd.DataFrame(
        {
            "doc_id": pages["Doc ID"].astype(int),
            "part_id": pages["Doc Part ID"].astype(int),
            "work": work,
            "script": pages["Script"],
            "dataset_source": source,
            "is_multilingual": pages["Language"] != LANGUAGE,
            "shelfmark": pages["Repository"].str.strip() + " :: " + pages["Call No"].str.strip(),
            "split": split,
        }
    ).sort_values(["doc_id", "part_id"], ignore_index=True)


def validate(assignment: pd.DataFrame, n_pages: int) -> None:
    """Vérifie l'étanchéité du découpage. Lève ValueError au premier problème."""
    if assignment["part_id"].duplicated().any() or len(assignment) != n_pages:
        raise ValueError("Chaque page ottomane doit être affectée exactement une fois")
    for group in ["work", "doc_id", "shelfmark"]:
        n_splits = assignment.groupby(group)["split"].nunique()
        shared = n_splits[n_splits > 1]
        if not shared.empty:
            raise ValueError(f"{group} partagé(e) entre plusieurs jeux : {list(shared.index)}")
    for docs in LINKED_DOCS:
        splits = set(assignment.loc[assignment["doc_id"].astype(str).isin(docs), "split"])
        if len(splits) > 1:
            raise ValueError(f"Doc {sorted(docs)} répartis sur {splits} (décision 3)")
    val_works = set(assignment.loc[assignment["split"] == "val", "work"])
    if val_works != {VALIDATION_WORK}:
        raise ValueError(f"Validation : œuvres {val_works}, attendu {VALIDATION_WORK}")


def render(assignment: pd.DataFrame, name: str) -> str:
    """Contenu du fichier splits/<name>.csv (en-tête en commentaire, puis CSV)."""
    header = [
        f"# Jeu : {name}",
        f"# Source : OpenITI MAKHZAN {VERSION}, Zenodo record {RECORD_ID}, pages ottomanes",
        "# Règles : DECISIONS.md, décisions 1, 3, 6, 7, 19 ; groupe de découpage = œuvre (Title of Text)",
        f"# Seed : {SEED}",
        "# Généré par : uv run python -m htr_ottoman.splits",
    ]
    buf = io.StringIO()
    assignment.loc[assignment["split"] == name, COLUMNS].to_csv(buf, index=False, lineterminator="\n")
    return "\n".join(header) + "\n" + buf.getvalue()


def load_split(name: str) -> pd.DataFrame:
    """Relit splits/<name>.csv (utilisé par les étapes suivantes)."""
    return pd.read_csv(SPLITS / f"{name}.csv", comment="#", dtype={"doc_id": int, "part_id": int})


def summary(assignment: pd.DataFrame, pages: pd.DataFrame) -> pd.DataFrame:
    lines = pages.set_index(pages["Doc Part ID"].astype(int))["Transcribed Lines Count"].astype(int)
    a = assignment.assign(lines=assignment["part_id"].map(lines))
    return a.groupby("split").agg(
        manuscrits=("doc_id", "nunique"),
        oeuvres=("work", "nunique"),
        pages=("part_id", "size"),
        lignes_transcrites=("lines", "sum"),
        pages_multilingues=("is_multilingual", "sum"),
    ).reindex(SPLIT_NAMES)


def main() -> None:
    pages = ottoman_pages(load_metadata())
    assignment = assign(pages)
    validate(assignment, len(pages))
    SPLITS.mkdir(exist_ok=True)
    for name in SPLIT_NAMES:
        (SPLITS / f"{name}.csv").write_text(render(assignment, name), encoding="utf-8")
    print(summary(assignment, pages).to_string())
    print(f"-> {', '.join(f'splits/{n}.csv' for n in SPLIT_NAMES)} (étanchéité vérifiée)")


if __name__ == "__main__":
    main()
