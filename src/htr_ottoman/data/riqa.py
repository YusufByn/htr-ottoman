"""RiqaTestset : extraction et table des lignes, sans aucune prédiction.

Source : osmanlica.com/test, « Ottoman Handwritten (Rika) OCR-Transliteration
Dataset » (DATASETS.md, section 3.3). Usage académique autorisé par écrit le
2026-10-23, citation des publications d'Osmanlica.com demandée. Test externe de
F15 (décision 46) : jamais d'entraînement ni de réglage ; ni image ni
transcription redistribuée, y compris dans reports/.

Le zip a été déposé par l'utilisateur dans data/raw/riqa/ (lecture seule) ; son
SHA-256 est vérifié avant toute lecture.

Étapes, chacune idempotente :
1. extract : contenu du dossier riqa/ du zip vers data/interim/riqa/ ;
2. build_lines : data/interim/riqa/riqa_lines.parquet, une ligne par image de
   ligne (lignes déjà découpées), texte ottoman brut non normalisé.

Usage : uv run python -m htr_ottoman.data.riqa
"""
import hashlib
import os
import re
import shutil
import zipfile

import pandas as pd
from PIL import Image

from htr_ottoman.config import RIQA_INTERIM, RIQA_LINES, RIQA_RAW, RIQA_ZIP, ROOT

ZIP_SHA256 = "7368010513b50c46459b0c3ef4afd826e4d75ab78c967808ef3a60abb3d39305"  # relevé le 2026-10-29
ZIP_SIZE = 9_789_642
TOP = "riqa/"  # dossier racine du zip
GT_SUFFIX = ".gt.txt"

# Nom d'une ligne : <uuid>-<numéro>, ex. 5d14e816-6f00-45f2-b951-030098f07e26-020
LINE_NAME = re.compile(r"^(?P<unit>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})-(?P<line>\d+)$")


def sha256sum(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_zip() -> None:
    """SHA-256 et taille du zip, puis data/raw/riqa/ en lecture seule (zip et dossier, comme data/raw/akis/)."""
    if RIQA_ZIP.stat().st_size != ZIP_SIZE or sha256sum(RIQA_ZIP) != ZIP_SHA256:
        raise RuntimeError(f"{RIQA_ZIP} : taille ou SHA-256 inattendus (attendu {ZIP_SHA256}, {ZIP_SIZE} octets)")
    RIQA_ZIP.chmod(0o444)
    RIQA_RAW.chmod(0o555)


def extract() -> None:
    """Extrait riqa/ vers RIQA_INTERIM (dossier temporaire puis renommage)."""
    if RIQA_INTERIM.is_dir():
        print(f"  extraction : {RIQA_INTERIM.relative_to(ROOT)} déjà présent")
        return
    tmp = RIQA_INTERIM.with_name(RIQA_INTERIM.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)  # reste d'une extraction interrompue (data/interim/ seulement)
    with zipfile.ZipFile(RIQA_ZIP) as z:
        for name in z.namelist():
            if not name.startswith(TOP) or ".." in name.split("/"):
                raise ValueError(f"{RIQA_ZIP.name} : nom de fichier inattendu {name!r}")
        z.extractall(tmp)
    os.replace(tmp / TOP.rstrip("/"), RIQA_INTERIM)
    tmp.rmdir()
    print(f"  extraction : {RIQA_INTERIM.relative_to(ROOT)}")


def build_lines() -> pd.DataFrame:
    rows = []
    for image_path in sorted((RIQA_INTERIM / "images").glob("*.png")):
        m = LINE_NAME.match(image_path.stem)
        if not m:
            raise ValueError(f"Nom de ligne inattendu : {image_path.name}")
        text_path = RIQA_INTERIM / "ottoman" / f"{image_path.stem}{GT_SUFFIX}"
        raw = text_path.read_bytes()
        text = raw.decode("utf-8")  # strict : une erreur d'encodage arrête tout
        with Image.open(image_path) as im:
            width, height, mode = im.width, im.height, im.mode
        rows.append(
            {
                "line_id": image_path.stem,
                "unit": m["unit"],
                "line_number": int(m["line"]),
                "text": text,
                "has_bom": raw.startswith(b"\xef\xbb\xbf"),
                "has_cr": "\r" in text,
                "has_final_newline": text.endswith("\n"),
                "is_empty": not text.strip(),
                "image_width": width,
                "image_height": height,
                "image_mode": mode,
                "image_path": str(image_path.relative_to(ROOT)),
                "text_path": str(text_path.relative_to(ROOT)),
            }
        )
    return pd.DataFrame(rows).sort_values(["unit", "line_number"]).reset_index(drop=True)


def check_lines(lines: pd.DataFrame) -> None:
    """Chaque image a sa transcription ottomane et turque et réciproquement, sans doublon."""
    stems = set(lines["line_id"])
    for folder in ("ottoman", "turkish"):
        names = {p.name.removesuffix(GT_SUFFIX) for p in (RIQA_INTERIM / folder).iterdir()}
        if names != stems:
            raise ValueError(f"{folder}/ ne correspond pas aux images : {len(names)} fichiers, {len(stems)} images")
    if lines["line_id"].duplicated().any() or lines.duplicated(["unit", "line_number"]).any():
        raise ValueError("Lignes en double")


if __name__ == "__main__":
    print("Vérification du zip")
    check_zip()
    print(f"  SHA-256 et taille conformes ({ZIP_SIZE} octets), data/raw/riqa/ en lecture seule")
    print("Extraction")
    extract()
    print("Table des lignes")
    lines = build_lines()
    check_lines(lines)
    lines.to_parquet(RIQA_LINES, index=False)
    print(f"  {len(lines)} lignes, {lines['unit'].nunique()} unités -> {RIQA_LINES.relative_to(ROOT)}")
