"""Prédiction ligne par ligne avec un modèle kraken, sur les ALTO normalisés d'un jeu.

Passe par l'API Python de kraken (la sortie texte de `kraken ocr` 7.1.1 est
inversée, skill kraken section 8), avec le réglage BiDi du projet (décision 26) :
les prédictions sont en ordre logique. La découpe des lignes est imposée par le
projet (`prepare.LEGACY_POLYGONS`, décision 25), pas lue dans le modèle : kraken
7.1.1 perd ce drapeau en convertissant un checkpoint en .safetensors (décision 36).
Le test interne est clos depuis F9 : toute prédiction dessus est refusée (décision 39).

Usage : uv run python -m htr_ottoman.predict --model CHEMIN --split val --output FICHIER.parquet
"""
import argparse
import warnings
from pathlib import Path

import pandas as pd

from htr_ottoman.prepare import ALTO_DIR, KRAKEN_TEXT_OPTIONS, LEGACY_POLYGONS
from htr_ottoman.splits import load_split

CLOSED_SPLIT = "test_interne"  # clos depuis F9 (décision 39)


def load_model(path: Path):
    with warnings.catch_warnings():  # avertissements bénins de coremltools (voir base_model.load)
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.filterwarnings("ignore", message="You will not be able to run predict", category=RuntimeWarning)
        from kraken.tasks import RecognitionTaskModel

        model = RecognitionTaskModel.load_model(path)
    if model.net.use_legacy_polygons != LEGACY_POLYGONS:
        print(f"  découpe imposée : anciens polygones = {LEGACY_POLYGONS} "
              f"(drapeau du modèle : {model.net.use_legacy_polygons}, décision 36)", flush=True)
        model.net.use_legacy_polygons = LEGACY_POLYGONS
    return model


def predict_split(model_path: Path, split: str) -> pd.DataFrame:
    if split == CLOSED_SPLIT:
        raise ValueError(f"Le jeu {CLOSED_SPLIT} est clos depuis F9 (décision 39) : plus aucune prédiction dessus. "
                         "Prédictions sauvegardées : reports/baseline/test_interne/, reports/f8_finetune/test_interne/.")
    from kraken.configs import RecognitionInferenceConfig
    from kraken.lib.xml import XMLPage
    from PIL import Image

    model = load_model(model_path)
    config = RecognitionInferenceConfig(bidi_reordering=KRAKEN_TEXT_OPTIONS["bidi_reordering"])
    rows = []
    pages = load_split(split)
    for doc_id, part_id in zip(pages["doc_id"], pages["part_id"]):
        seg = XMLPage(ALTO_DIR / str(doc_id) / f"{doc_id}_{part_id}.xml").to_container()
        if not seg.lines:
            continue
        with Image.open(seg.imagename) as im:
            for rec in model.predict(im=im, segmentation=seg, config=config):
                rows.append({"part_id": part_id, "line_id": rec.id, "pred": rec.prediction})
        print(f"  {part_id} : {len(seg.lines)} lignes", flush=True)
    return pd.DataFrame(rows)


def predict_line_images(model, segmentation, images: list) -> list:
    """Reconnaissance d'images de lignes déjà découpées (F15 : expérience témoin, RiqaTestset).

    Option (b) du plan de l'expérience témoin : tout le traitement de kraken après la découpe est
    gardé (transformations de l'entraînement, sans redressement puisque la segmentation est de type
    « baselines », lots de 1, BiDi du projet) ; seule la découpe de la ligne dans la page
    (`kraken.models.ctc._extract_line`, kraken 7.1.1) est remplacée par l'image fournie.
    `images[i]` est l'image de `segmentation.lines[i]`. Le modèle doit être utilisé sans processus
    de découpe (`num_line_workers=0`) : on refuse un modèle déjà préparé avec des processus.
    """
    import kraken.models.ctc as ctc
    from kraken.configs import RecognitionInferenceConfig
    from PIL import Image

    if segmentation.type != "baselines" or len(images) != len(segmentation.lines):
        raise ValueError("Une image par ligne d'une segmentation de type « baselines » est exigée")
    pool = getattr(model.net, "_line_extraction_pool", None)
    if pool is not None and type(pool).__name__ != "_InProcessPool":
        raise ValueError("Modèle déjà préparé avec des processus de découpe : en charger un nouveau")
    config = RecognitionInferenceConfig(bidi_reordering=KRAKEN_TEXT_OPTIONS["bidi_reordering"], num_line_workers=0)
    original = ctc._extract_line
    ctc._extract_line = lambda im, seg, line_idx, legacy=False: (images[line_idx], line_idx)
    try:
        return list(model.predict(im=Image.new("L", (1, 1)), segmentation=segmentation, config=config))
    finally:
        ctc._extract_line = original


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    preds = predict_split(args.model, args.split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(args.output, index=False)
    print(f"{len(preds)} prédictions -> {args.output}")


if __name__ == "__main__":
    main()
