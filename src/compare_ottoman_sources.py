"""Compare les sous-ensembles ottomans Research et ACDC-Evaluation de MAKHZAN.

Lit uniquement le fichier de métadonnées et affiche : pages, lignes
transcrites / total, écritures, catégories de relecture, et la répartition
des lignes par manuscrit dans Research. Ne crée aucun split.

Usage : uv run python src/compare_ottoman_sources.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
METADATA = ROOT / "data/raw/makhzan/OpenITI-Makhzan_Metadata_2026-1-2.tsv"
LANGUAGE = "Ottoman Turkish"
SOURCES = ["Research", "ACDC-Evaluation"]


def load_pages() -> pd.DataFrame:
    df = pd.read_csv(METADATA, sep="\t", dtype=str, keep_default_na=False)
    pages = df[df["Language"].str.contains(LANGUAGE, regex=False)].copy()
    pages["transcribed"] = pages["Transcribed Lines Count"].astype(int)
    pages["total"] = pages["Total Lines Count"].astype(int)
    pages["Doc ID"] = pages["Doc ID"].astype(int)
    return pages


def overview(pages: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for src in SOURCES:
        p = pages[pages["Dataset Source"] == src]
        per_doc = p.groupby("Doc ID")["transcribed"].sum()
        rows[src] = {
            "manuscrits": p["Doc ID"].nunique(),
            "pages": len(p),
            "lignes transcrites": p["transcribed"].sum(),
            "lignes total": p["total"].sum(),
            "% transcrit": round(100 * p["transcribed"].sum() / p["total"].sum(), 1),
            "pages incomplètes": (p["transcribed"] < p["total"]).sum(),
            "lignes / page (médiane)": p["transcribed"].median(),
            "lignes / manuscrit (médiane)": per_doc.median(),
            "lignes / manuscrit (min-max)": f"{per_doc.min()}-{per_doc.max()}",
        }
    return pd.DataFrame(rows)


def by_column(pages: pd.DataFrame, col: str) -> pd.DataFrame:
    """Pages (et manuscrits) par valeur de `col`, pour chaque source."""
    p = pages[pages["Dataset Source"].isin(SOURCES)]
    g = p.groupby([col, "Dataset Source"]).agg(pages=("Doc Part ID", "size"), mss=("Doc ID", "nunique"))
    g["cell"] = g["pages"].astype(str) + " p. / " + g["mss"].astype(str) + " ms."
    return g["cell"].unstack(fill_value="-").reindex(columns=SOURCES, fill_value="-")


def research_by_doc(pages: pd.DataFrame) -> pd.DataFrame:
    p = pages[pages["Dataset Source"] == "Research"]
    d = (
        p.groupby("Doc ID")
        .agg(
            titre=("Title of Text", "first"),
            cote=("Call No", "first"),
            ecriture=("Script", lambda s: " | ".join(sorted(set(s)))),
            pages=("Doc Part ID", "size"),
            lignes=("transcribed", "sum"),
            total=("total", "sum"),
        )
        .sort_values("lignes", ascending=False)
    )
    d["% lignes"] = (100 * d["lignes"] / d["lignes"].sum()).round(1)
    d["% cumulé"] = d["% lignes"].cumsum().round(1)
    return d


def research_by_work(pages: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par œuvre (Title of Text), l'unité de découpage de la validation."""
    p = pages[pages["Dataset Source"] == "Research"]
    w = (
        p.groupby("Title of Text")
        .agg(
            manuscrits=("Doc ID", lambda s: " ".join(str(d) for d in sorted(set(s)))),
            n_ms=("Doc ID", "nunique"),
            pages=("Doc Part ID", "size"),
            lignes=("transcribed", "sum"),
            pages_couche_modele=("Transcription Layer Name", lambda s: (s != "manual").sum()),
        )
        .sort_values("lignes", ascending=False)
    )
    w["% lignes"] = (100 * w["lignes"] / w["lignes"].sum()).round(1)
    return w


def main() -> None:
    pd.set_option("display.width", 200)
    pages = load_pages()
    print("== Vue d'ensemble (ottoman)\n")
    print(overview(pages).to_string(), "\n")
    print("== Écritures (pages / manuscrits)\n")
    print(by_column(pages, "Script").to_string(), "\n")
    print("== Catégorie de relecture (pages / manuscrits)\n")
    print(by_column(pages, "Category").to_string(), "\n")
    print("== Research : lignes transcrites par manuscrit\n")
    print(research_by_doc(pages).to_string(), "\n")
    print("== Research : lignes transcrites par œuvre\n")
    print(research_by_work(pages).to_string())


if __name__ == "__main__":
    main()
