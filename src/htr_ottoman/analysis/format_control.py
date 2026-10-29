"""Expérience témoin de F15 sur la validation : effet du format d'image de RiqaTestset.

But : séparer l'effet du format d'image (lignes en rectangles, binarisées, petites) de celui de
l'écriture rik'a, avant toute prédiction sur RiqaTestset (décision 46). Validation seulement
(412 lignes, 2 manuscrits) ; test interne clos (décision 39). Modèles : baseline et F8 (lag 5).

Choix fixés par l'utilisateur le 2026-10-29, avant tout calcul :
- passage au modèle : option (b), l'image de la ligne passe par les transformations de
  l'entraînement, sans redressement (`predict.predict_line_images`) ; fixée d'avance comme la plus
  proche de l'entraînement, sans sélection au score. Option (a), mode `bbox` de kraken (redressement
  `CenterNormalizer`), en variante descriptive seulement ;
- rectangle : rectangle englobant le polygone de la ligne de l'ALTO, découpé dans la page ;
- binarisation : seuil d'Otsu par ligne (principal) ; `nlbin` de kraken (variante) ;
- hauteur : un facteur unique, pour que la hauteur médiane des rectangles de la validation passe à
  84 px (hauteur médiane de RiqaTestset, reports/riqa/resume.json) ; redimensionner, puis binariser.

Contrôle bloquant : la découpe actuelle (`kraken.models.ctc._extract_line`, anciens polygones)
passée par `predict_line_images` doit redonner `predictions.parquet` identique à l'octet à la
référence de chaque modèle. Sinon : arrêt, aucune autre condition.

Limite : la méthode de découpe et de binarisation d'Osmanlica.com est inconnue ; l'expérience donne
un ordre de grandeur de l'effet du format, jamais une correction du CER de RiqaTestset.

Sorties : reports/f15_temoin_format/<condition>/<modèle>/ (predictions.parquet et sorties
d'`evaluate`), resume.csv (CER, différence avec C0, IC 95 % par bootstrap apparié sur les pages),
run.json (environnement, facteur d'échelle, contrôle).

Usage : uv run python -m htr_ottoman.analysis.format_control
"""
import hashlib
import json
import platform
import time
from dataclasses import dataclass
from importlib.metadata import version

import numpy as np
import pandas as pd
from PIL import Image

from htr_ottoman.compare import pair
from htr_ottoman.compare_variant import cer, page_ci
from htr_ottoman.config import BASE_MODEL, MODELS, REPORTS, ROOT
from htr_ottoman.evaluate import evaluate
from htr_ottoman.predict import load_model, predict_line_images
from htr_ottoman.prepare import ALTO_DIR, KRAKEN_TEXT_OPTIONS, LEGACY_POLYGONS
from htr_ottoman.splits import load_split

SPLIT = "val"
RIQA_MEDIAN_HEIGHT = 84  # px, reports/riqa/resume.json (images.hauteur, 50 %)
OUTPUT = REPORTS / "f15_temoin_format"
TESTED = {"baseline": BASE_MODEL, "f8_lag5": MODELS / "f8_finetune" / "best_0.8365.safetensors"}
REFERENCES = {"baseline": REPORTS / "baseline" / SPLIT, "f8_lag5": REPORTS / "f8_finetune" / SPLIT}


@dataclass(frozen=True)
class Condition:
    crop: str  # "decoupe" (découpe actuelle) ou "rectangle"
    binarize: str | None  # None, "otsu" ou "nlbin"
    rescale: bool  # hauteur médiane ramenée à RIQA_MEDIAN_HEIGHT
    mode: str  # "b" (transformations de l'entraînement) ou "a" (mode bbox de kraken)
    role: str


CONDITIONS = {
    "c0_controle": Condition("decoupe", None, False, "b", "contrôle bloquant"),
    "c1_rectangle": Condition("rectangle", None, False, "b", "principal"),
    "c2_rectangle_otsu": Condition("rectangle", "otsu", False, "b", "principal"),
    "c3_rectangle_hauteur": Condition("rectangle", None, True, "b", "principal"),
    "c4_format_riqa": Condition("rectangle", "otsu", True, "b", "principal"),
    "v2_rectangle_nlbin": Condition("rectangle", "nlbin", False, "b", "variante nlbin"),
    "v4_format_riqa_nlbin": Condition("rectangle", "nlbin", True, "b", "variante nlbin"),
    "v1_rectangle_bbox": Condition("rectangle", None, False, "a", "variante mode bbox, descriptive"),
    "v4_format_riqa_bbox": Condition("rectangle", "otsu", True, "a", "variante mode bbox, descriptive"),
}


def pages():
    """(part_id, segmentation, image de la page) des pages de la validation, dans l'ordre de `predict`."""
    from kraken.lib.xml import XMLPage

    for p in load_split(SPLIT).itertuples():
        seg = XMLPage(ALTO_DIR / str(p.doc_id) / f"{p.doc_id}_{p.part_id}.xml").to_container()
        if seg.lines:
            with Image.open(seg.imagename) as im:
                im.load()
                yield p.part_id, seg, im


def rectangle(page: Image.Image, boundary) -> Image.Image:
    """Rectangle englobant le polygone de la ligne, limité à la page."""
    xs, ys = [x for x, _ in boundary], [y for _, y in boundary]
    box = (max(0, min(xs)), max(0, min(ys)), min(page.width, max(xs) + 1), min(page.height, max(ys) + 1))
    return page.crop(box)


def scale_factor(heights: list[int]) -> float:
    return RIQA_MEDIAN_HEIGHT / float(np.median(heights))


def rescale(im: Image.Image, factor: float) -> Image.Image:
    size = (max(1, round(im.width * factor)), max(1, round(im.height * factor)))
    return im.resize(size, Image.Resampling.LANCZOS)


def otsu(im: Image.Image) -> Image.Image:
    """Seuil d'Otsu sur la ligne en gris : 0 (encre) ou 255 (fond), mode L comme RiqaTestset."""
    from skimage.filters import threshold_otsu

    grey = np.asarray(im.convert("L"))
    if grey.min() == grey.max():
        return Image.fromarray(grey)
    return Image.fromarray(np.where(grey > threshold_otsu(grey), 255, 0).astype(np.uint8))


def nlbin(im: Image.Image) -> Image.Image:
    from kraken.binarization import nlbin as kraken_nlbin

    return kraken_nlbin(im).convert("L")


def line_images(condition: Condition, page: Image.Image, seg, factor: float) -> list[Image.Image]:
    import kraken.models.ctc as ctc

    images = []
    for idx, line in enumerate(seg.lines):
        if condition.crop == "decoupe":
            images.append(ctc._extract_line(page, seg, idx, legacy=LEGACY_POLYGONS)[0])
            continue
        im = rectangle(page, line.boundary)
        if condition.rescale:
            im = rescale(im, factor)
        if condition.binarize == "otsu":
            im = otsu(im)
        elif condition.binarize == "nlbin":
            im = nlbin(im)
        images.append(im)
    return images


def predict_bbox(model, seg, images: list[Image.Image]) -> list:
    """Option (a), descriptive : chaque image en mode bbox de kraken (redressement CenterNormalizer)."""
    from kraken.configs import RecognitionInferenceConfig
    from kraken.containers import BBoxLine, Segmentation

    config = RecognitionInferenceConfig(bidi_reordering=KRAKEN_TEXT_OPTIONS["bidi_reordering"], num_line_workers=0)
    records = []
    for line, im in zip(seg.lines, images):
        box = Segmentation(type="bbox", imagename="", text_direction=seg.text_direction, script_detection=False,
                           lines=[BBoxLine(id=line.id, bbox=(0, 0, im.width, im.height))])
        records += list(model.predict(im=im, segmentation=box, config=config))
    return records


def run_condition(name: str, model, model_name: str, factor: float) -> pd.DataFrame:
    condition = CONDITIONS[name]
    rows = []
    for part_id, seg, page in pages():
        images = line_images(condition, page, seg, factor)
        records = predict_line_images(model, seg, images) if condition.mode == "b" else predict_bbox(model, seg, images)
        if [r.id for r in records] != [line.id for line in seg.lines]:
            raise RuntimeError(f"{part_id} : ordre des lignes modifié")
        rows += [{"part_id": part_id, "line_id": r.id, "pred": r.prediction} for r in records]
    preds = pd.DataFrame(rows)
    out = OUTPUT / name / model_name
    out.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(out / "predictions.parquet", index=False)
    evaluate(preds, SPLIT, out)
    return pd.read_parquet(out / "lignes.parquet")


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment() -> dict:
    return {"macos": platform.mac_ver()[0], "python": platform.python_version(),
            **{p: version(p) for p in ("kraken", "torch", "scipy", "numpy", "scikit-image", "pillow")}}


def rectangle_heights() -> list[int]:
    return [rectangle(page, line.boundary).height for _, seg, page in pages() for line in seg.lines]


def main() -> None:
    start = time.time()
    factor = scale_factor(rectangle_heights())
    print(f"Facteur d'échelle : {factor:.4f} (hauteur médiane des rectangles -> {RIQA_MEDIAN_HEIGHT} px)", flush=True)
    models = {name: load_model(path) for name, path in TESTED.items()}
    run = {"environnement": environment(), "facteur_echelle": factor, "controle": {}, "conditions": list(CONDITIONS)}

    # 1. Contrôle bloquant : C0 identique à l'octet à la référence, pour chaque modèle
    lines = {}
    for model_name, model in models.items():
        lines[("c0_controle", model_name)] = run_condition("c0_controle", model, model_name, factor)
        new, ref = OUTPUT / "c0_controle" / model_name / "predictions.parquet", REFERENCES[model_name] / "predictions.parquet"
        identical = sha256(new) == sha256(ref)
        run["controle"][model_name] = {"sha256": sha256(new), "reference": sha256(ref), "identique": identical}
        print(f"Contrôle {model_name} : {'identique' if identical else 'DIFFÉRENT'} à {ref.relative_to(ROOT)}", flush=True)
    if not all(c["identique"] for c in run["controle"].values()):
        (OUTPUT / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        raise SystemExit("Contrôle bloquant échoué : aucune autre condition n'est lancée")

    # 2. Conditions principales, puis variantes
    for name in list(CONDITIONS)[1:]:
        for model_name, model in models.items():
            print(f"== {name} / {model_name}", flush=True)
            lines[(name, model_name)] = run_condition(name, model, model_name, factor)

    rows = []
    for (name, model_name), scored in lines.items():
        reference = lines[("c0_controle", model_name)]
        paired = pair(reference, scored)
        low, high = page_ci(paired)
        rows.append({"condition": name, "role": CONDITIONS[name].role, "modele": model_name,
                     "cer": round(cer(scored), 6), "difference_c0_points": round(100 * (cer(scored) - cer(reference)), 2),
                     "ic95_bas_points": round(100 * low, 2), "ic95_haut_points": round(100 * high, 2)})
    summary = pd.DataFrame(rows)
    summary.to_csv(OUTPUT / "resume.csv", index=False, lineterminator="\n")
    run["duree_min"] = round((time.time() - start) / 60, 2)
    (OUTPUT / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
