"""Prédiction ligne par ligne avec un modèle kraken, sur les ALTO normalisés d'un jeu.

Passe par l'API Python de kraken (la sortie texte de `kraken ocr` 7.1.1 est
inversée, skill kraken section 8), avec le réglage BiDi du projet (décision 26) :
les prédictions sont en ordre logique. La découpe des lignes suit le drapeau du
modèle (anciens polygones pour le modèle de départ, décision 25).

Usage : uv run python -m htr_ottoman.predict --model CHEMIN --split val --output FICHIER.parquet
"""
import argparse
import warnings
from pathlib import Path

import pandas as pd

from htr_ottoman.prepare import ALTO_DIR, KRAKEN_TEXT_OPTIONS
from htr_ottoman.splits import load_split


def load_model(path: Path):
    with warnings.catch_warnings():  # avertissements bénins de coremltools (voir base_model.load)
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.filterwarnings("ignore", message="You will not be able to run predict", category=RuntimeWarning)
        from kraken.tasks import RecognitionTaskModel

        return RecognitionTaskModel.load_model(path)


def predict_split(model_path: Path, split: str) -> pd.DataFrame:
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
