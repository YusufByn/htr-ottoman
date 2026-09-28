"""Évaluation pré-enregistrée d'un modèle sur un jeu réservé, avec contrôles bloquants (F9).

Pilotée par un fichier de configs/ qui fixe avant toute prédiction le modèle et
son empreinte, la référence (baseline) et l'empreinte de ses prédictions, les
effectifs attendus du jeu et les dossiers de sortie (décisions 37 et 38).

Contrôles bloquants, tous avant la prédiction du modèle. Au premier échec : arrêt,
aucune prédiction du modèle, rapport (décision 38).
1. Tout le travail est committé : le commit enregistré décrit le code lancé.
2. Aucune prédiction du modèle sur ce jeu n'existe déjà : une seule prédiction (décision 37).
3. Empreintes SHA-256 des deux modèles et des prédictions de la référence.
4. Découpe imposée par `predict` aux deux modèles : anciens polygones (décisions 25 et 36).
5. Effectifs du jeu (manuscrits, lignes, caractères de référence après `normalize`) et
   vérité terrain normalisée identique, ligne à ligne, à celle de l'évaluation de la référence.
6. Prédiction de la référence refaite avec le pipeline actuel : identique octet pour octet
   à ses prédictions enregistrées. Écrite dans un dossier temporaire, effacé ensuite.

Puis, sauf avec `--controls-only` : prédiction du modèle (`predict`), CER (`evaluate`),
comparaison appariée avec la référence (`compare`), contrôle `ketos test` du modèle
(décision 38, descriptif), et run.json (commit, empreintes, durées) dans le dossier du modèle.

Usage :
  uv run python -m htr_ottoman.final_eval configs/f9_test_interne.yml --controls-only   # contrôles seulement
  uv run python -m htr_ottoman.final_eval configs/f9_test_interne.yml                   # contrôles puis évaluation
"""
import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from htr_ottoman import compare, evaluate
from htr_ottoman.config import MAKHZAN_PROCESSED, ROOT
from htr_ottoman.prepare import KRAKEN_TEXT_OPTIONS, LEGACY_POLYGONS

SECTIONS = {"split", "model", "reference", "expected", "comparison"}
LINE_KEYS = ["part_id", "line_id"]


class ControlFailed(RuntimeError):
    """Contrôle bloquant en échec : arrêt, aucune prédiction du modèle (décision 38)."""


def load_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict) or set(config) != SECTIONS:
        raise ValueError(f"{path} : sections attendues {sorted(SECTIONS)}")
    return config


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_hash(path: Path, expected: str, label: str) -> None:
    found = sha256(path)
    if found != expected:
        raise ControlFailed(f"{label} : SHA-256 {found}, attendu {expected} ({path})")
    print(f"  ok  {label} : SHA-256 conforme", flush=True)


def check_cut(model_path: Path, label: str) -> None:
    from htr_ottoman.predict import load_model

    model = load_model(model_path)
    if not (LEGACY_POLYGONS and model.net.use_legacy_polygons):
        raise ControlFailed(f"{label} : découpe « anciens polygones » non imposée (décision 36)")
    print(f"  ok  {label} : découpe anciens polygones", flush=True)


def check_split(split: str, expected: dict, reference_lines: pd.DataFrame) -> None:
    from htr_ottoman.prepare import select_lines

    lines = select_lines()
    rows = lines[(lines["split"] == split) & lines["exclusion"].isna()]
    found = {"manuscripts": rows["doc_id"].nunique(), "lines": len(rows),
             "reference_chars": int(rows["norm"].str.len().sum())}
    if found != expected:
        raise ControlFailed(f"Effectifs du jeu {split} : {found}, attendus {expected}")
    print(f"  ok  effectifs : {found}", flush=True)
    merged = rows[LINE_KEYS + ["norm"]].merge(reference_lines[LINE_KEYS + ["ref_norm"]], on=LINE_KEYS,
                                              how="outer", indicator=True, validate="one_to_one")
    differing = int(((merged["_merge"] != "both") | (merged["norm"] != merged["ref_norm"])).sum())
    if differing:
        raise ControlFailed(f"Vérité terrain normalisée : {differing} lignes diffèrent de l'évaluation de la référence")
    print("  ok  vérité terrain normalisée identique à celle de la référence", flush=True)


def check_reference_reproduced(reference: dict, split: str) -> str:
    """Refait la prédiction de la référence et compare le fichier, à l'octet près, à celui enregistré."""
    from htr_ottoman.predict import predict_split

    preds = predict_split(ROOT / reference["path"], split)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "predictions.parquet"
        preds.to_parquet(path, index=False)  # même écriture que predict
        found = sha256(path)
    if found != reference["predictions_sha256"]:
        saved = pd.read_parquet(ROOT / reference["reports"] / "predictions.parquet")
        merged = saved.merge(preds, on=LINE_KEYS, how="outer", suffixes=("_f7", "_refaite"), indicator=True)
        differing = int(((merged["_merge"] != "both") | (merged["pred_f7"] != merged["pred_refaite"])).sum())
        raise ControlFailed(f"Prédiction de la référence refaite : SHA-256 {found}, attendu "
                            f"{reference['predictions_sha256']} ; lignes différentes : {differing} sur {len(merged)}")
    print("  ok  prédiction de la référence refaite, identique octet pour octet", flush=True)
    return found


def ketos_test_command(model_path: Path, split: str) -> list[str]:
    """Contrôle de `evaluate` par ketos (décision 29), comme en F5 : jeu compilé, CPU, lots de 1."""
    manifest = (MAKHZAN_PROCESSED / f"{split}.lst").relative_to(ROOT)
    return ["-d", "cpu", "test", "-m", str(model_path.relative_to(ROOT)), "-f", "binary", "-e", str(manifest),
            "-u", KRAKEN_TEXT_OPTIONS["normalization"],
            "-n" if KRAKEN_TEXT_OPTIONS["normalize_whitespace"] else "--no-normalize-whitespace",
            "--reorder" if KRAKEN_TEXT_OPTIONS["bidi_reordering"] else "--no-reorder", "-B", "1"]


def parse_ketos_report(text: str) -> dict:
    """Caractères et erreurs du rapport de `ketos test` (gabarit kraken/templates/report)."""
    found = {key: re.search(rf"^\s*(\d+)\s+{label}\s*$", text, re.MULTILINE)
             for key, label in {"caracteres": "Characters", "erreurs": "Errors"}.items()}
    if not all(found.values()):
        return {}
    counts = {key: int(m.group(1)) for key, m in found.items()}
    return {**counts, "cer": counts["erreurs"] / counts["caracteres"]}


def ketos_test(model_path: Path, split: str, output: Path) -> dict:
    args = ketos_test_command(model_path, split)
    proc = subprocess.run([str(Path(sys.executable).with_name("ketos")), *args], cwd=ROOT,
                          capture_output=True, text=True)
    output.write_text(proc.stdout + proc.stderr)
    return {"commande": shlex.join(["uv", "run", "ketos", *args]), "code_retour": proc.returncode,
            **parse_ketos_report(proc.stdout + proc.stderr)}


def run(config_path: Path, controls_only: bool) -> None:
    from htr_ottoman.train import git_commit

    config = load_config(config_path)
    split, model, reference = config["split"], config["model"], config["reference"]
    model_path, model_dir = ROOT / model["path"], ROOT / model["reports"]
    started, t0 = datetime.now(), time.time()

    print(f"Contrôles bloquants (décision 38), jeu {split}", flush=True)
    try:
        commit = git_commit()
    except RuntimeError as err:
        raise ControlFailed(str(err)) from err
    print(f"  ok  travail committé : {commit}", flush=True)
    if (model_dir / "predictions.parquet").exists():
        raise ControlFailed(f"{model_dir / 'predictions.parquet'} existe déjà : une seule prédiction (décision 37)")
    check_hash(model_path, model["sha256"], "modèle")
    check_hash(ROOT / reference["path"], reference["sha256"], "référence")
    check_hash(ROOT / reference["reports"] / "predictions.parquet", reference["predictions_sha256"],
               "prédictions de la référence")
    check_cut(model_path, "modèle")
    check_cut(ROOT / reference["path"], "référence")
    check_split(split, config["expected"], pd.read_parquet(ROOT / reference["reports"] / "lignes.parquet"))
    check_reference_reproduced(reference, split)
    t_controls = time.time()
    print(f"Tous les contrôles sont passés ({(t_controls - t0) / 60:.1f} min).", flush=True)
    if controls_only:
        print("--controls-only : arrêt avant la prédiction du modèle.")
        return

    from htr_ottoman.predict import predict_split

    model_dir.mkdir(parents=True, exist_ok=True)
    predict_split(model_path, split).to_parquet(model_dir / "predictions.parquet", index=False)
    t_predict = time.time()
    evaluate.evaluate(pd.read_parquet(model_dir / "predictions.parquet"), split, model_dir)
    compare.run(ROOT / reference["reports"], model_dir, ROOT / config["comparison"])
    t_eval = time.time()
    print("Contrôle ketos test (CPU)...", flush=True)
    ketos = ketos_test(model_path, split, model_dir / "ketos_test.txt")
    t_end = time.time()
    print(f"ketos test : {ketos}")

    info = {
        "config": str(config_path.relative_to(ROOT)), "commit": commit,
        "debut": started.isoformat(timespec="seconds"), "fin": datetime.now().isoformat(timespec="seconds"),
        "sha256": {"modele": model["sha256"], "reference": reference["sha256"],
                   "predictions_reference": reference["predictions_sha256"],
                   "predictions_modele": sha256(model_dir / "predictions.parquet")},
        "controles": "tous passés, prédiction de la référence identique octet pour octet",
        "ketos_test": ketos,
        "durees_min": {k: round(v / 60, 2) for k, v in {
            "controles": t_controls - t0, "prediction": t_predict - t_controls,
            "evaluation_comparaison": t_eval - t_predict, "ketos_test": t_end - t_eval, "total": t_end - t0}.items()},
    }
    (model_dir / "run.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    print(f"-> {model_dir.relative_to(ROOT)}/run.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--controls-only", action="store_true",
                        help="contrôles bloquants seulement (prédiction de la référence comprise), sans prédire le modèle")
    args = parser.parse_args()
    try:
        run(args.config.resolve(), args.controls_only)
    except ControlFailed as err:
        raise SystemExit(f"CONTRÔLE BLOQUANT EN ÉCHEC : {err}\nArrêt : aucune prédiction du modèle (décision 38).")


if __name__ == "__main__":
    main()
