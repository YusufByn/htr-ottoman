"""Modèle de départ : OpenITI ottoman imprimé (kraken, 2022).

- download : télécharge l'enregistrement Zenodo dans models/openiti_ottoman_print/,
  MD5 vérifiés, idempotent (même mécanisme que MAKHZAN, data.download) ;
- load : charge le modèle de reconnaissance avec kraken ;
- codec_labels : le codec du modèle, {suite de caractères: numéros de classe} ;
- write_codec : écrit ce codec dans reports/codec_modele_depart.json (versionné),
  avec le SHA-256 du .mlmodel ;
- codec_chars : les caractères du codec, lus dans ce fichier, sans charger le
  modèle (F14) : préparation, évaluation et analyses n'importent jamais kraken pour
  le codec, et aucun modèle n'est chargé sur le test interne (décision 39).

Usage : uv run python -m htr_ottoman.base_model
"""
import functools
import hashlib
import json
import urllib.request
import warnings

from htr_ottoman.config import BASE_MODEL, BASE_MODEL_CODEC, BASE_MODEL_DIR, ROOT
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


def sha256sum(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_codec(model) -> dict:
    """Écrit le codec du modèle chargé dans BASE_MODEL_CODEC (seul endroit où le codec vient du modèle)."""
    data = {
        "modele": BASE_MODEL.name,
        "doi": DOI,
        "sha256": sha256sum(BASE_MODEL),
        "codec": dict(sorted(codec_labels(model).items())),
    }
    BASE_MODEL_CODEC.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data


@functools.cache
def codec_chars() -> frozenset[str]:
    """Caractères du codec du modèle de départ, lus dans BASE_MODEL_CODEC, sans charger le modèle.
    Si le .mlmodel est présent, son SHA-256 doit être celui du fichier."""
    data = json.loads(BASE_MODEL_CODEC.read_text(encoding="utf-8"))
    if BASE_MODEL.exists() and sha256sum(BASE_MODEL) != data["sha256"]:
        raise ValueError(f"{BASE_MODEL.name} ne correspond pas à {BASE_MODEL_CODEC.name} (SHA-256 différent)")
    labels = data["codec"]
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
    print(f"3. Codec écrit dans {BASE_MODEL_CODEC.relative_to(ROOT)}")
    write_codec(model)


if __name__ == "__main__":
    main()
