"""Préparation des données pour kraken (F4).

Pour chaque jeu de splits/ :
1. sélection des lignes utilisables : transcrites (règle de CLAUDE.md) et sans
   annotation de transcripteur (décision 15) ;
2. un ALTO normalisé par page dans data/processed/makhzan/alto/<DocID>/ : lignes
   exclues retirées, texte passé par `normalize` (unique normalisation du
   projet), image désignée par un chemin relatif vers data/interim/ ;
3. compilation en <jeu>.arrow avec l'ancien extracteur de polygones, celui du
   modèle de départ (décision 25), et manifeste <jeu>.lst ;
4. vérification : nombre de lignes, texte en NFD et identique au texte
   normalisé attendu, statut « anciens polygones » enregistré ;
5. rapport reports/processed_datasets.csv (effectifs, exclusions, alphabet).

La compilation se fait dans un seul processus : avec plusieurs, kraken écrit
les lignes dans un ordre variable et deux compilations différeraient.

Usage : uv run python -m htr_ottoman.prepare
"""
import copy
import json
import os
import unicodedata
import xml.etree.ElementTree as ET

import pandas as pd
import pyarrow as pa

from htr_ottoman.config import MAKHZAN_LINES, MAKHZAN_PROCESSED, REPORTS, ROOT
from htr_ottoman.data.annotations import has_annotation
from htr_ottoman.normalize import normalize
from htr_ottoman.splits import SPLIT_NAMES, load_split

# Découpe des lignes : ancien extracteur, comme le modèle de départ (décision 25).
LEGACY_POLYGONS = True
# Réglages de texte de kraken, identiques à ceux du modèle de départ (décision 26).
# Sans effet sur un texte déjà passé par `normalize` (vérifié), mais explicites :
# `ketos train` et `ketos test` ne les reprennent pas du modèle chargé.
KRAKEN_TEXT_OPTIONS = {"normalization": "NFD", "normalize_whitespace": True, "bidi_reordering": True}

ALTO_DIR = MAKHZAN_PROCESSED / "alto"
REPORT = REPORTS / "processed_datasets.csv"


def select_lines() -> pd.DataFrame:
    """Table des lignes avec jeu, texte normalisé et motif d'exclusion éventuel."""
    lines = pd.read_parquet(MAKHZAN_LINES)
    split_of = {pid: name for name in SPLIT_NAMES for pid in load_split(name)["part_id"]}
    lines["split"] = lines["part_id"].map(split_of)
    if lines["split"].isna().any():
        raise ValueError("Des pages de la table des lignes n'ont pas de jeu dans splits/")
    lines["exclusion"] = None
    lines.loc[lines["text"].map(has_annotation), "exclusion"] = "annotation"
    lines.loc[lines["is_empty"], "exclusion"] = "vide"
    lines["norm"] = lines["text"].map(normalize)
    lines.loc[lines["exclusion"].isna() & (lines["norm"] == ""), "exclusion"] = "vide après normalisation"
    return lines


def write_page_alto(page_lines: pd.DataFrame) -> str:
    """Écrit l'ALTO normalisé d'une page et renvoie son chemin (relatif à ROOT)."""
    first = page_lines.iloc[0]
    src = ROOT / first["alto_path"]
    tree = ET.parse(src)
    root = tree.getroot()
    ns_uri = root.tag.split("}")[0].strip("{")
    ET.register_namespace("", ns_uri)
    q = lambda tag: f"{{{ns_uri}}}{tag}"  # noqa: E731

    kept = dict(zip(page_lines.loc[page_lines["exclusion"].isna(), "line_id"],
                    page_lines.loc[page_lines["exclusion"].isna(), "norm"]))
    parents = {child: parent for parent in root.iter() for child in parent}
    for tl in list(root.iter(q("TextLine"))):
        line_id = tl.get("ID")
        if line_id not in kept:
            parents[tl].remove(tl)
            continue
        strings = [el for el in tl if el.tag in (q("String"), q("SP"))]
        template = next((el for el in strings if el.tag == q("String")), None)
        for el in strings:
            tl.remove(el)
        string = copy.deepcopy(template) if template is not None else ET.Element(q("String"))
        string.attrib.pop("WC", None)
        string.set("CONTENT", kept[line_id])
        tl.append(string)

    dest = ALTO_DIR / str(first["doc_id"]) / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    image = ROOT / first["image_path"]
    file_name = root.find(f".//{q('sourceImageInformation')}/{q('fileName')}")
    file_name.text = os.path.relpath(image, dest.parent)
    tree.write(dest, encoding="utf-8", xml_declaration=True)
    return str(dest.relative_to(ROOT))


def compile_split(name: str, alto_paths: list[str]) -> None:
    from kraken.lib.arrow_dataset import build_binary_dataset

    output = MAKHZAN_PROCESSED / f"{name}.arrow"
    build_binary_dataset(
        files=[str(ROOT / p) for p in alto_paths],
        output_file=str(output),
        format_type="alto",
        num_workers=0,
        ignore_splits=True,
        skip_empty_lines=True,
        linetype="baselines",
        legacy_polygons=LEGACY_POLYGONS,
    )
    (MAKHZAN_PROCESSED / f"{name}.lst").write_text(str(output.relative_to(ROOT)) + "\n", encoding="utf-8")


def read_arrow(name: str) -> tuple[list[str], dict]:
    """Textes et métadonnées kraken d'un jeu compilé."""
    with pa.memory_map(str(MAKHZAN_PROCESSED / f"{name}.arrow")) as source:
        table = pa.ipc.open_file(source).read_all()
    meta = json.loads(table.schema.metadata[b"lines"])
    texts = [rec["text"] for rec in table.column("lines").to_pylist()]
    return texts, meta


def check_split(name: str, expected: list[str]) -> dict:
    texts, meta = read_arrow(name)
    if sorted(texts) != sorted(expected):
        raise ValueError(f"{name}.arrow : {len(texts)} lignes, textes différents des {len(expected)} attendus")
    if not all(unicodedata.is_normalized("NFD", t) for t in texts):
        raise ValueError(f"{name}.arrow : texte non NFD")
    if meta.get("legacy_polygons") is not LEGACY_POLYGONS:
        raise ValueError(f"{name}.arrow : legacy_polygons = {meta.get('legacy_polygons')}")
    return meta


def verify_with_kraken(name: str, limit: int | None = None) -> int:
    """Charge <jeu>.arrow avec la classe de jeu de données de l'entraînement kraken,
    les réglages de texte du projet et les transformations d'image du modèle de
    départ, puis lit les lignes. kraken remplace en silence une ligne illisible
    par une ligne au hasard (failed_samples) : on échoue dans ce cas.
    Renvoie le nombre de lignes lues."""
    from kraken.lib.dataset import ArrowIPCRecognitionDataset, ImageInputTransforms

    from htr_ottoman.base_model import load

    _, channels, height, width = load().input  # (lot, canaux, hauteur, largeur) = (1, 1, 120, 0)
    transforms = ImageInputTransforms(1, height, width, channels, (16, 0), valid_norm=False)
    ds = ArrowIPCRecognitionDataset(
        normalization=KRAKEN_TEXT_OPTIONS["normalization"],
        whitespace_normalization=KRAKEN_TEXT_OPTIONS["normalize_whitespace"],
        reorder=KRAKEN_TEXT_OPTIONS["bidi_reordering"],
        im_transforms=transforms,
    )
    ds.add(str(MAKHZAN_PROCESSED / f"{name}.arrow"))
    ds.no_encode()
    n = len(ds) if limit is None else min(limit, len(ds))
    for i in range(n):
        image = ds[i]["image"]
        if tuple(image.shape[:2]) != (channels, height):
            raise ValueError(f"{name}.arrow, ligne {i} : image de forme {tuple(image.shape)}")
    if ds.failed_samples:
        raise ValueError(f"{name}.arrow : lignes illisibles pour kraken {sorted(ds.failed_samples)}")
    return n


def main() -> None:
    lines = select_lines()
    rows = []
    for name in SPLIT_NAMES:
        split_lines = lines[lines["split"] == name]
        alto_paths = [write_page_alto(g) for _, g in split_lines.groupby("part_id", sort=True)]
        print(f"{name} : {len(alto_paths)} ALTO normalisés, compilation…", flush=True)
        compile_split(name, alto_paths)
        kept = split_lines[split_lines["exclusion"].isna()]
        meta = check_split(name, kept["norm"].tolist())
        charset = sorted(set("".join(kept["norm"])))
        excl = split_lines["exclusion"].value_counts()
        rows.append({
            "split": name,
            "manuscrits": split_lines["doc_id"].nunique(),
            "pages": len(alto_paths),
            "lignes_total": len(split_lines),
            "exclues_vides": int(excl.get("vide", 0)),
            "exclues_annotation": int(excl.get("annotation", 0)),
            "exclues_vides_apres_normalisation": int(excl.get("vide après normalisation", 0)),
            "lignes_compilees": len(kept),
            "caracteres": int(kept["norm"].str.len().sum()),
            "caracteres_distincts": len(charset),
            "legacy_polygons": meta["legacy_polygons"],
            "type": meta["type"],
            "alphabet": "".join(charset),
        })
    report = pd.DataFrame(rows)
    report.to_csv(REPORT, index=False, lineterminator="\n")
    print(report.drop(columns="alphabet").to_string(index=False))
    for name in SPLIT_NAMES:
        print(f"lecture kraken {name} : {verify_with_kraken(name)} lignes lues sans erreur", flush=True)
    print(f"-> data/processed/makhzan/{{{','.join(SPLIT_NAMES)}}}.arrow et .lst ; {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
