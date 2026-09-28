"""Akis : téléchargement et extraction du jeu de test public.

Source : https://github.com/verimsu/Akis-Ottoman-Dataset, licence Apache 2.0.
Citer : Tasdemir et al., « Automatic Transcription of Ottoman Documents Using
Deep Learning », DAS 2024, LNCS, p. 422-435 (DOI 10.1007/978-3-031-70442-0_26).

Le zip est stocké avec git LFS : le dépôt ne contient qu'un pointeur (SHA-256 et
taille). On le télécharge depuis le serveur LFS de GitHub pour un commit figé,
sans installer git-lfs, et on vérifie son SHA-256 contre le pointeur.

Étapes, chacune idempotente :
1. download : pointeur, zip, README et LICENSE dans data/raw/akis/, lecture seule ;
2. extract : contenu du zip vers data/interim/akis/ ;
3. build_lines : data/interim/akis/akis_lines.parquet, une ligne par image de
   ligne (Akis fournit des lignes déjà découpées), texte brut non normalisé.

Seule la partie test d'Akis est publique ; elle ne sert qu'à l'évaluation finale (CLAUDE.md).

Usage : uv run python -m htr_ottoman.data.akis
"""
import os
import re
import shutil
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
from PIL import Image

from htr_ottoman.config import AKIS_INTERIM, AKIS_LINES, AKIS_RAW, AKIS_ZIP, ROOT
from htr_ottoman.data.download import ensure_file

REPO = "verimsu/Akis-Ottoman-Dataset"
COMMIT = "c7a6e5b425e640ef7ab2d85cd70c4e9fa1221838"  # 2024-09-14, dernier commit du dépôt au 2026-09-28
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}"
LFS_URL = f"https://media.githubusercontent.com/media/{REPO}/{COMMIT}"

# Pointeur LFS de akis_dataset_test.zip au commit COMMIT
ZIP_SHA256 = "d98ddfc603c4a8c1b2a33775c5bdf3d41cbd86e24664e6435323665b2b12dbed"
ZIP_SIZE = 584_379_296
# Petits fichiers versionnés normalement, SHA-256 relevés le 2026-09-28
SMALL_FILES = {
    "LICENSE": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
    "README.md": "d3d7dba138d3546eb087178cbe160b9a0f27e785c5a3b5d734e46a97f4892406",
}


def read_pointer() -> dict[str, str]:
    """Lit le pointeur LFS du zip au commit figé : {"oid": ..., "size": ...}."""
    with urllib.request.urlopen(f"{RAW_URL}/{AKIS_ZIP.name}") as r:
        text = r.read().decode()
    fields = dict(line.split(" ", 1) for line in text.splitlines() if line)
    return {"oid": fields["oid"].removeprefix("sha256:"), "size": fields["size"]}


def download() -> None:
    pointer = read_pointer()
    if (pointer["oid"], int(pointer["size"])) != (ZIP_SHA256, ZIP_SIZE):
        raise RuntimeError(f"Pointeur LFS inattendu : {pointer}")
    status = ensure_file(f"{LFS_URL}/{AKIS_ZIP.name}", AKIS_ZIP, ZIP_SHA256, algo="sha256")
    if AKIS_ZIP.stat().st_size != ZIP_SIZE:
        raise RuntimeError(f"{AKIS_ZIP} : {AKIS_ZIP.stat().st_size} octets, attendu {ZIP_SIZE}")
    print(f"  {status:10} {AKIS_ZIP.name} (SHA-256 et taille conformes au pointeur LFS)")
    for name, sha256 in SMALL_FILES.items():
        status = ensure_file(f"{RAW_URL}/{name}", AKIS_RAW / name, sha256, algo="sha256")
        print(f"  {status:10} {name} (SHA-256 OK)")
    AKIS_RAW.chmod(0o555)  # le dossier aussi reste en lecture seule


def extract() -> None:
    """Extrait le zip vers AKIS_INTERIM (dossier temporaire puis renommage)."""
    if AKIS_INTERIM.is_dir():
        print(f"  extraction : {AKIS_INTERIM} déjà présent")
        return
    tmp = AKIS_INTERIM.with_name(AKIS_INTERIM.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)  # reste d'une extraction interrompue (data/interim/ seulement)
    with zipfile.ZipFile(AKIS_ZIP) as z:
        for name in z.namelist():
            if name.startswith("/") or ".." in name.split("/"):
                raise ValueError(f"{AKIS_ZIP.name} : nom de fichier inattendu {name!r}")
        z.extractall(tmp)
    os.replace(tmp, AKIS_INTERIM)
    print(f"  extraction : {AKIS_INTERIM}")


# Nom d'une ligne : <source>-<page>_<ligne>, la page pouvant porter un suffixe -A / -B
# (ex. R-AM-01-AS-1888-086-B_03). L'année d'édition termine le code de source, sauf HRG_01.
LINE_NAME = re.compile(r"^(?P<source>.+)-(?P<page>\d+(?:-[AB])?)_(?P<line>\d+)$")
YEAR = re.compile(r"-(\d{4})$")


def read_pairs() -> list[tuple[str, str]]:
    """Paires (image, transcription) de files.txt, dans l'ordre du fichier."""
    lines = (AKIS_INTERIM / "files.txt").read_text(encoding="utf-8").splitlines()
    return [tuple(line.split(" ")) for line in lines if line]


def build_lines() -> pd.DataFrame:
    rows = []
    for image_name, text_name in read_pairs():
        stem = image_name.removesuffix(".png")
        if text_name != f"{stem}_ann.txt":
            raise ValueError(f"files.txt : {image_name} associé à {text_name}")
        m = LINE_NAME.match(stem)
        if not m:
            raise ValueError(f"Nom de ligne inattendu : {stem}")
        year = YEAR.search(m["source"])
        image_path = AKIS_INTERIM / "images" / image_name
        text_path = AKIS_INTERIM / "annotations" / text_name
        raw = text_path.read_bytes()
        text = raw.decode("utf-8")  # strict : une erreur d'encodage arrête tout
        with Image.open(image_path) as im:
            width, height, mode = im.width, im.height, im.mode
        rows.append(
            {
                "line_id": stem,
                "source": m["source"],
                "year": int(year[1]) if year else None,
                "page": m["page"],
                "line_number": int(m["line"]),
                "text": text,
                "has_final_newline": text.endswith("\n"),
                "is_empty": not text.strip(),
                "image_width": width,
                "image_height": height,
                "image_mode": mode,
                "image_path": str(image_path.relative_to(ROOT)),
                "text_path": str(text_path.relative_to(ROOT)),
            }
        )
    lines = pd.DataFrame(rows).astype({"year": "Int64"})
    return lines.sort_values(["source", "page", "line_number"]).reset_index(drop=True)


def check_lines(lines: pd.DataFrame) -> None:
    """Chaque image a sa transcription et réciproquement, sans doublon."""
    images = {p.name for p in (AKIS_INTERIM / "images").iterdir()}
    texts = {p.name for p in (AKIS_INTERIM / "annotations").iterdir()}
    listed_images = {Path(p).name for p in lines["image_path"]}
    listed_texts = {Path(p).name for p in lines["text_path"]}
    if lines["line_id"].duplicated().any():
        raise ValueError("Lignes en double dans files.txt")
    if images != listed_images or texts != listed_texts:
        raise ValueError(
            f"files.txt ne couvre pas exactement les dossiers : images {len(images)} / {len(listed_images)}, "
            f"transcriptions {len(texts)} / {len(listed_texts)}"
        )


if __name__ == "__main__":
    print("Téléchargement")
    download()
    print("Extraction")
    extract()
    print("Table des lignes")
    lines = build_lines()
    check_lines(lines)
    lines.to_parquet(AKIS_LINES, index=False)
    print(f"  {len(lines)} lignes, {lines['source'].nunique()} sources -> {AKIS_LINES.relative_to(ROOT)}")
