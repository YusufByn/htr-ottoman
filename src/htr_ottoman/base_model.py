"""Modèle de départ : OpenITI ottoman imprimé (kraken, 2022).

- download : télécharge l'enregistrement Zenodo dans models/openiti_ottoman_print/,
  MD5 vérifiés, idempotent (même mécanisme que MAKHZAN, data.download) ;
- load : charge le modèle de reconnaissance avec kraken ;
- codec_labels : le codec du modèle, {suite de caractères: numéros de classe}.

Usage : uv run python -m htr_ottoman.base_model
"""
import functools
import json
import urllib.request
import warnings

from htr_ottoman.config import BASE_MODEL, BASE_MODEL_DIR, ROOT
from htr_ottoman.data.download import ensure_file

RECORD_ID = "7050342"
DOI = f"10.5281/zenodo.{RECORD_ID}"
API = f"https://zenodo.org/api/records/{RECORD_ID}"


def download() -> None:
    with urllib.request.urlopen(API) as r:
        record = json.load(r)
    if record.get("doi") != DOI:
        raise RuntimeError(f"DOI Zenodo {record.get('doi')}, attendu {DOI}")
    for f in record["files"]:
        algo, md5 = f["checksum"].split(":")
        assert algo == "md5", f["checksum"]
        status = ensure_file(f["links"]["self"], BASE_MODEL_DIR / f["key"], md5)
        print(f"  {status:10} {f['key']} (MD5 OK)")


def load():
    """Charge le modèle de reconnaissance (kraken 7 lit l'ancien format .mlmodel)."""
    # coremltools (lecteur du format .mlmodel) émet deux avertissements sans
    # conséquence : une faute dans sa documentation, et l'impossibilité d'exécuter
    # le modèle avec le moteur CoreML d'Apple, que kraken n'utilise pas.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        warnings.filterwarnings("ignore", message="You will not be able to run predict", category=RuntimeWarning)
        from kraken.models import load_models

        models = load_models(BASE_MODEL, tasks=["recognition"])
    if len(models) != 1:
        raise RuntimeError(f"{len(models)} modèles de reconnaissance dans {BASE_MODEL}, attendu 1")
    return models[0]


def codec_labels(model) -> dict[str, list[int]]:
    """Codec : chaque entrée (un caractère ou une suite) et ses numéros de classe."""
    return dict(model.codec.c2l)


@functools.cache
def codec_chars() -> frozenset[str]:
    """Caractères du codec du modèle de départ (modèle chargé une seule fois par processus)."""
    labels = codec_labels(load())
    if any(len(k) != 1 for k in labels):
        raise ValueError("Le codec contient des suites de plusieurs caractères")
    return frozenset(labels)


def main() -> None:
    print(f"1. Téléchargement ({BASE_MODEL_DIR.relative_to(ROOT)}/)")
    download()
    print("2. Chargement avec kraken")
    model = load()
    codec = codec_labels(model)
    multi = [k for k in codec if len(k) > 1]
    print(f"  {type(model).__name__} chargé, codec de {len(codec)} entrées ({len(multi)} suites de plusieurs caractères)")


if __name__ == "__main__":
    main()
