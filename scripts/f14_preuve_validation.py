"""F14 : preuve que le modèle publié prédit exactement comme le modèle évalué (validation seulement).

Script ponctuel, versionné. Charge la copie corrigée (`htr_ottoman.publish`, décision 45)
par le chemin normal de kraken (`RecognitionTaskModel.load_model`), sans imposer la découpe :
contrairement à `predict` (décision 36, inchangée), le drapeau « anciens polygones » est
celui lu dans le modèle. Prédit la validation avec la même boucle et le même réglage BiDi
que `predict`, puis compare au fichier de F8 (lag 5) et recalcule le CER avec `evaluate`.

Attendu : drapeau lu à vrai ; predictions.parquet identique à l'octet à
reports/f8_finetune/val/predictions.parquet (SHA-256 b6b4517e…) ; CER 0,163184.
Validation seulement : rien sur le test interne (décision 39).

Le code est sous `if __name__ == "__main__":` : kraken extrait les lignes dans des
processus fils lancés par « spawn » (macOS), qui réimportent ce fichier ; sans ce garde,
chaque fils rechargeait le modèle et relançait la prédiction (incident du 2026-10-20,
EXPERIMENTS.md).

Usage : uv run python scripts/f14_preuve_validation.py
"""
import hashlib
import sys
import warnings

import pandas as pd

from htr_ottoman.config import PUBLICATION_DIR, PUBLISHED_MODEL, REPORTS
from htr_ottoman.evaluate import evaluate
from htr_ottoman.prepare import ALTO_DIR, KRAKEN_TEXT_OPTIONS
from htr_ottoman.splits import load_split

SPLIT = "val"
EXPECTED_SHA256 = "b6b4517ec0e81b51837a6b0efddeb84ab2bfa8e1a045321a4426a09658f453ee"
EXPECTED_CER = 0.163184
REFERENCE = REPORTS / "f8_finetune" / SPLIT / "predictions.parquet"
OUT_DIR = PUBLICATION_DIR / "preuve_validation"


def sha256sum(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with warnings.catch_warnings():  # avertissements bénins de coremltools (voir base_model.load)
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.filterwarnings("ignore", message="You will not be able to run predict", category=RuntimeWarning)
        from kraken.configs import RecognitionInferenceConfig
        from kraken.lib.xml import XMLPage
        from kraken.tasks import RecognitionTaskModel
        from PIL import Image

        model = RecognitionTaskModel.load_model(PUBLISHED_MODEL)  # aucun forçage du drapeau
    flag = model.net.use_legacy_polygons
    print(f"1. {PUBLISHED_MODEL.name} chargé par kraken : use_legacy_polygons = {flag}", flush=True)

    config = RecognitionInferenceConfig(bidi_reordering=KRAKEN_TEXT_OPTIONS["bidi_reordering"])
    rows = []
    pages = load_split(SPLIT)
    for n, (doc_id, part_id) in enumerate(zip(pages["doc_id"], pages["part_id"]), start=1):
        seg = XMLPage(ALTO_DIR / str(doc_id) / f"{doc_id}_{part_id}.xml").to_container()
        if not seg.lines:
            continue
        with Image.open(seg.imagename) as im:
            for rec in model.predict(im=im, segmentation=seg, config=config):
                rows.append({"part_id": part_id, "line_id": rec.id, "pred": rec.prediction})
        print(f"  page {n}/{len(pages)} ({part_id}) : {len(seg.lines)} lignes", flush=True)
    preds = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "predictions.parquet"
    preds.to_parquet(out, index=False)
    sha = sha256sum(out)
    print(f"2. {len(preds)} prédictions, SHA-256 {sha}")
    print(f"   identique à l'octet à {REFERENCE.name} de F8 (lag 5) : {out.read_bytes() == REFERENCE.read_bytes()}")

    cer = float(evaluate(preds, SPLIT, OUT_DIR / "evaluate")["global"]["cer"].iloc[0])
    print(f"3. CER de validation : {cer:.6f} (attendu {EXPECTED_CER})")

    ok = flag is True and sha == EXPECTED_SHA256 and round(cer, 6) == EXPECTED_CER
    print("OK" if ok else "ÉCART")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
