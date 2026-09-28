"""MAKHZAN : téléchargement, extraction de la partie ottomane, table des lignes.

Trois étapes, chacune idempotente (relancer ne refait rien d'inutile) :
1. download : télécharge les fichiers de l'enregistrement Zenodo dans
   data/raw/makhzan/ et vérifie leur MD5 (remplace le curl du 2026-09-25) ;
2. extract : extrait les zips des manuscrits ottomans vers data/interim/makhzan/<DocID>/ ;
3. build_lines : écrit data/interim/makhzan/ottoman_lines.parquet, une ligne par
   TextLine, puis vérifie les effectifs par rapport au TSV.

Usage : uv run python -m htr_ottoman.data.makhzan
"""
import json
import os
import shutil
import urllib.request
import zipfile

import pandas as pd

from htr_ottoman.config import (
    MAKHZAN_INTERIM,
    MAKHZAN_LINES,
    MAKHZAN_METADATA,
    MAKHZAN_RAW,
    MAKHZAN_ZIP,
    ROOT,
)
from htr_ottoman.data.alto import read_alto
from htr_ottoman.data.download import ensure_file, writable_dir

RECORD_ID = "19861912"
VERSION = "2026.1.2"
API = f"https://zenodo.org/api/records/{RECORD_ID}"

# Une page est ottomane si "Ottoman Turkish" figure dans sa langue (pages multilingues comprises).
LANGUAGE = "Ottoman Turkish"

# Couches de transcription nommées d'après un modèle kraken (décisions 4 et 16).
MODEL_LAYERS = {"gen2-print-n7m5-union-ft_best", "kraken:39_from_pretrain_2_best"}
KNOWN_LAYERS = MODEL_LAYERS | {"manual", "METS Import | export"}


# 1. Téléchargement ---------------------------------------------------------

def download() -> None:
    with urllib.request.urlopen(API) as r:
        record = json.load(r)
    if record["metadata"].get("version") != VERSION:
        raise RuntimeError(f"Version Zenodo {record['metadata'].get('version')}, attendue {VERSION}")
    for f in record["files"]:
        algo, md5 = f["checksum"].split(":")
        assert algo == "md5", f["checksum"]
        url = f.get("links", {}).get("self") or f"{API}/files/{f['key']}/content"
        status = ensure_file(url, MAKHZAN_RAW / f["key"], md5)
        print(f"  {status:10} {f['key']} (MD5 OK)")
    MAKHZAN_RAW.chmod(0o555)  # le dossier aussi reste en lecture seule


# 2. Extraction ---------------------------------------------------------------

def load_metadata() -> pd.DataFrame:
    return pd.read_csv(MAKHZAN_METADATA, sep="\t", dtype=str, keep_default_na=False)


def ottoman_pages(meta: pd.DataFrame) -> pd.DataFrame:
    return meta[meta["Language"].str.contains(LANGUAGE, regex=False)]


def extract(doc_ids: list[str]) -> None:
    """Extrait Doc<ID>.zip (emboîté dans le zip MAKHZAN) vers MAKHZAN_INTERIM/<ID>/."""
    MAKHZAN_INTERIM.mkdir(parents=True, exist_ok=True)
    done = skipped = 0
    with zipfile.ZipFile(MAKHZAN_ZIP) as outer:
        for doc_id in doc_ids:
            dest = MAKHZAN_INTERIM / doc_id
            if dest.is_dir():
                skipped += 1
                continue
            tmp = MAKHZAN_INTERIM / f"{doc_id}.tmp"
            if tmp.exists():
                shutil.rmtree(tmp)  # reste d'une extraction interrompue (data/interim/ seulement)
            with outer.open(f"Doc{doc_id}.zip") as f, zipfile.ZipFile(f) as inner:
                for name in inner.namelist():
                    if "/" in name or "\\" in name or name.startswith("."):
                        raise ValueError(f"Doc{doc_id}.zip : nom de fichier inattendu {name!r}")
                inner.extractall(tmp)
            os.replace(tmp, dest)
            done += 1
    print(f"  extraction : {done} manuscrits extraits, {skipped} déjà présents")


# 3. Table des lignes ---------------------------------------------------------

def build_lines(pages: pd.DataFrame) -> pd.DataFrame:
    unknown = set(pages["Transcription Layer Name"]) - KNOWN_LAYERS
    if unknown:
        raise ValueError(f"Couches de transcription inconnues : {unknown}")

    rows = []
    for doc_id, part_id in zip(pages["Doc ID"], pages["Doc Part ID"]):
        alto_path = MAKHZAN_INTERIM / doc_id / f"{doc_id}_{part_id}.xml"
        page = read_alto(alto_path.read_bytes())
        image_path = alto_path.with_name(page.image_filename)
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        for i, line in enumerate(page.lines):
            rows.append(
                {
                    "doc_id": int(doc_id),
                    "part_id": int(part_id),
                    "line_index": i,
                    "line_id": line.line_id,
                    "text": line.text,
                    "is_empty": line.is_empty,
                    "image_path": str(image_path.relative_to(ROOT)),
                    "alto_path": str(alto_path.relative_to(ROOT)),
                    "_part": part_id,
                }
            )
    lines = pd.DataFrame(rows)

    # Métadonnées de page jointes par Doc Part ID
    page_meta = pages.rename(
        columns={
            "Doc Part ID": "_part",
            "Title of Text": "work",
            "Script": "script",
            "Category": "category",
            "Dataset Source": "dataset_source",
            "Language": "language",
            "Transcription Layer Name": "layer",
        }
    )[["_part", "work", "script", "category", "dataset_source", "language", "layer"]]
    lines = lines.merge(page_meta, on="_part", how="left", validate="many_to_one")
    lines["is_model_layer"] = lines["layer"].isin(MODEL_LAYERS)
    columns = [
        "doc_id", "part_id", "line_index", "line_id", "work", "script", "category",
        "dataset_source", "language", "layer", "is_model_layer", "text", "is_empty",
        "image_path", "alto_path",
    ]
    return lines[columns].sort_values(["doc_id", "part_id", "line_index"]).reset_index(drop=True)


def check_lines(lines: pd.DataFrame, pages: pd.DataFrame) -> None:
    """Vérifie les effectifs de la table par rapport au TSV (critères d'acceptation de F2)."""
    n_pages, n_docs = lines["part_id"].nunique(), lines["doc_id"].nunique()
    if (n_pages, n_docs) != (len(pages), pages["Doc ID"].nunique()):
        raise ValueError(f"{n_pages} pages / {n_docs} manuscrits, attendu {len(pages)} / {pages['Doc ID'].nunique()}")
    counts = lines.groupby("part_id").agg(total=("line_id", "size"), transcribed=("is_empty", lambda e: (~e).sum()))
    expected = pages.set_index(pages["Doc Part ID"].astype(int))[["Total Lines Count", "Transcribed Lines Count"]].astype(int)
    expected.columns = ["total", "transcribed"]
    diff = counts.join(expected, rsuffix="_tsv")
    bad = diff[(diff["total"] != diff["total_tsv"]) | (diff["transcribed"] != diff["transcribed_tsv"])]
    if not bad.empty:
        raise ValueError(f"Effectifs différents du TSV pour {len(bad)} pages :\n{bad}")


def main() -> None:
    print("1. Téléchargement (data/raw/makhzan/)")
    download()
    meta = load_metadata()
    pages = ottoman_pages(meta)
    doc_ids = sorted(set(pages["Doc ID"]), key=int)
    print(f"2. Extraction de {len(doc_ids)} manuscrits ottomans (data/interim/makhzan/)")
    extract(doc_ids)
    print("3. Table des lignes")
    lines = build_lines(pages)
    check_lines(lines, pages)
    lines.to_parquet(MAKHZAN_LINES, index=False)
    print(
        f"  {len(lines)} lignes ({(~lines['is_empty']).sum()} transcrites), "
        f"{lines['part_id'].nunique()} pages, {lines['doc_id'].nunique()} manuscrits : "
        f"effectifs identiques au TSV -> {MAKHZAN_LINES.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
