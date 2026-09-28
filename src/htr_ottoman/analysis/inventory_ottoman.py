"""Inventaire des manuscrits ottomans de MAKHZAN, une ligne par Doc ID.

Lit uniquement le fichier de métadonnées (data/raw/ n'est jamais modifié) et
écrit reports/ottoman_inventory.csv.

Usage : uv run python -m htr_ottoman.analysis.inventory_ottoman
"""
import pandas as pd

from htr_ottoman.config import MAKHZAN_METADATA as METADATA
from htr_ottoman.config import REPORTS, ROOT
from htr_ottoman.data.makhzan import KNOWN_LAYERS, LANGUAGE, MODEL_LAYERS

OUTPUT = REPORTS / "ottoman_inventory.csv"

SEP = " | "  # séparateur des valeurs multiples ("clean; once vetted" contient déjà ";")


def distinct(values: pd.Series) -> str:
    return SEP.join(sorted({v for v in values.dropna() if v.strip()}))


def main() -> None:
    df = pd.read_csv(METADATA, sep="\t", dtype=str, keep_default_na=False)
    unknown = set(df["Transcription Layer Name"]) - KNOWN_LAYERS
    if unknown:
        raise ValueError(f"Couches de transcription inconnues : {unknown}")

    pages = df[df["Language"].str.contains(LANGUAGE, regex=False)].copy()
    pages["transcribed"] = pages["Transcribed Lines Count"].astype(int)
    pages["total"] = pages["Total Lines Count"].astype(int)
    pages["model_layer"] = pages["Transcription Layer Name"].isin(MODEL_LAYERS)
    # Titre de l'œuvre, à défaut titre du volume.
    pages["title"] = pages["Title of Text"].where(pages["Title of Text"] != "", pages["Title of Volume"])

    inv = (
        pages.groupby("Doc ID")
        .agg(
            title=("title", distinct),
            n_pages=("Doc Part ID", "nunique"),
            scripts=("Script", distinct),
            languages=("Language", distinct),
            dataset_source=("Dataset Source", distinct),
            category=("Category", distinct),
            transcribed_lines=("transcribed", "sum"),
            total_lines=("total", "sum"),
            n_pages_model_layer=("model_layer", "sum"),
        )
        .reset_index()
        .rename(columns={"Doc ID": "doc_id"})
    )
    inv["doc_id"] = inv["doc_id"].astype(int)
    inv = inv.sort_values("doc_id")

    OUTPUT.parent.mkdir(exist_ok=True)
    inv.to_csv(OUTPUT, index=False)
    print(f"{len(inv)} manuscrits, {inv['n_pages'].sum()} pages -> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
