"""Comparaison d'une variante de F12 au modèle F8 sur la validation (décision 42).

- Entrées : dossiers de `evaluate` sur la validation (`lignes.parquet`) : la
  référence (F8, seed 42), la variante, et les répétitions de la référence
  (seeds 42, 43 et 44, référence comprise) pour mesurer le bruit.
- Différence = CER de la variante moins CER de la référence (CER d'`evaluate`,
  décision 29) ; négative : la variante fait moins d'erreurs.
- Bruit : écart = CER maximal moins CER minimal des répétitions ;
  seuil S = max(0,5 point ; 2 × écart).
- IC à 95 % de la différence par bootstrap apparié sur les pages : à chaque
  tirage, les mêmes pages (tirées avec remise parmi les 19 de la validation,
  sans tenir compte du manuscrit) servent aux deux modèles ; 1 000 tirages,
  seed 42 (`evaluate.bootstrap_draws`), au moins 3 pages. Les pages d'un même
  manuscrit se ressemblent : cet IC est un peu trop étroit, d'où le seuil S.
- Règle (décision 42) :
  meilleure si (a) différence < −S, (b) IC entièrement sous 0 et (c) CER en
  baisse dans chaque manuscrit ; régression si les trois conditions sont
  vraies dans l'autre sens ; sinon pas de différence établie (on garde F8).
- Validation seulement (test interne clos, décision 39).
- Même règle d'arrêt partout (décision 43) : la variante et chaque répétition
  doivent avoir la règle d'arrêt (quit, lag, plafond, min-epochs) de la
  référence, lue dans configs/<modèle>.yml (et identique à la copie
  models/<modèle>/config.yml faite au lancement, si elle existe). Un essai
  technique (`essai_technique_*`) est toujours refusé. La commande du lancement
  (models/<modèle>/commande.txt, obligatoire) doit commencer par le lanceur que
  `train` choisit pour cette config : `ketos_capped` pour la règle de F12.
- Sans --model : bruit seul (bruit.csv, CER de chaque répétition, et seuil.csv,
  écart et seuil S), sans comparer aucune variante.

Usage : uv run python -m htr_ottoman.compare_variant --reference reports/f8_finetune/val --model reports/<variante>/val --noise reports/f8_finetune/val reports/f8_finetune_seed43/val reports/f8_finetune_seed44/val --output-dir reports/comparaisons/<variante>_f8_finetune/val
Bruit seul : uv run python -m htr_ottoman.compare_variant --reference reports/f8_finetune/val --noise reports/f8_finetune/val reports/f8_finetune_seed43/val reports/f8_finetune_seed44/val --output-dir reports/bruit/f8_finetune
"""
import argparse
import shlex
from pathlib import Path

import pandas as pd

from htr_ottoman.analysis.error_analysis import check_split
from htr_ottoman.compare import compare, pair, paired_bootstrap_ci
from htr_ottoman.config import CONFIGS, MODELS
from htr_ottoman.train import TECHNICAL_PREFIX, launcher, load_config, stop_rule

MIN_THRESHOLD = 0.005  # 0,5 point de CER
NOISE_FACTOR = 2
MIN_NOISE_RUNS = 3  # seeds 42, 43 et 44
BETTER, WORSE, NO_DIFFERENCE = "meilleure", "régression", "pas de différence établie"


def load(directory: Path) -> pd.DataFrame:
    lines = pd.read_parquet(directory / "lignes.parquet")
    check_split(lines, str(directory))
    return lines


def training_stop_rule(name: str, configs_dir: Path = CONFIGS, models_dir: Path = MODELS) -> dict:
    """Règle d'arrêt de l'entraînement du modèle `name` (configs/<name>.yml). Si la copie faite au
    lancement (models/<name>/config.yml) existe, elle doit être identique à la config versionnée."""
    if name.startswith(TECHNICAL_PREFIX):
        raise ValueError(f"{name} : essai technique, jamais utilisé dans F12")
    path = configs_dir / f"{name}.yml"
    if not path.exists():
        raise FileNotFoundError(f"Config d'entraînement de {name} introuvable : {path}")
    config = load_config(path)
    launched = models_dir / name / "config.yml"
    if launched.exists() and load_config(launched) != config:
        raise ValueError(f"{name} : {path.name} diffère de la config copiée au lancement ({launched})")
    return stop_rule(config)


def training_launcher(name: str, configs_dir: Path = CONFIGS, models_dir: Path = MODELS) -> str:
    """Lanceur du modèle `name`, lu dans models/<name>/commande.txt : celui que `train` choisit pour
    configs/<name>.yml (ketos_capped pour la règle de F12, sans quoi le plafond serait ignoré)."""
    expected = shlex.join(launcher(load_config(configs_dir / f"{name}.yml"))[0])
    path = models_dir / name / "commande.txt"
    if not path.exists():
        raise FileNotFoundError(f"Commande du lancement de {name} introuvable : {path}")
    if not path.read_text().startswith(expected + " "):
        raise ValueError(f"{name} : {path} n'est pas lancée par « {expected} » (décision 43)")
    return expected


def check_stop_rules(reference: str, others: list[str], **dirs) -> dict:
    """Refuse tout modèle dont la règle d'arrêt diffère de celle de la référence (décision 43), ou
    dont la commande du lancement n'utilise pas le lanceur de cette règle."""
    expected = training_stop_rule(reference, **dirs)
    for name in others:
        rule = training_stop_rule(name, **dirs)
        if rule != expected:
            raise ValueError(f"{name} : règle d'arrêt {rule} différente de celle de la référence {reference} "
                             f"{expected} (décision 43)")
    for name in [reference, *others]:
        training_launcher(name, **dirs)
    return expected


def cer(lines: pd.DataFrame) -> float:
    return lines["errors"].sum() / lines["ref_chars"].sum()


def threshold(cers: list[float]) -> tuple[float, float]:
    """Écart entre répétitions (max moins min) et seuil S = max(0,5 point ; 2 × écart)."""
    spread = max(cers) - min(cers)
    return spread, max(MIN_THRESHOLD, NOISE_FACTOR * spread)


def page_ci(paired: pd.DataFrame) -> tuple[float, float]:
    """IC à 95 % de la différence de CER par bootstrap apparié sur les pages (même calcul
    que `compare.paired_bootstrap_ci`, où chaque page tient lieu de manuscrit)."""
    per_page = paired.groupby("part_id")[["ref_chars", "errors_reference", "errors_modele"]].sum()
    return paired_bootstrap_ci(per_page)


def conditions(difference: float, low: float, high: float, doc_differences: list[float],
               limit: float) -> dict[str, bool]:
    """Les trois conditions de la décision 42, dans le sens de la baisse et dans celui de la hausse.
    Un IC non calculé (moins de 3 pages) ne remplit ni (b) ni son inverse."""
    return {
        "a_baisse_sup_seuil": difference < -limit,
        "b_ic_sous_0": high < 0,
        "c_baisse_chaque_manuscrit": all(d < 0 for d in doc_differences),
        "a_hausse_sup_seuil": difference > limit,
        "b_ic_au_dessus_0": low > 0,
        "c_hausse_chaque_manuscrit": all(d > 0 for d in doc_differences),
    }


def verdict(checks: dict[str, bool]) -> str:
    if checks["a_baisse_sup_seuil"] and checks["b_ic_sous_0"] and checks["c_baisse_chaque_manuscrit"]:
        return BETTER
    if checks["a_hausse_sup_seuil"] and checks["b_ic_au_dessus_0"] and checks["c_hausse_chaque_manuscrit"]:
        return WORSE
    return NO_DIFFERENCE


def noise_tables(reference: pd.DataFrame, noise: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """CER de chaque répétition de la référence (global et par manuscrit), écart et seuil S.
    `noise` : répétitions par nom ; au moins 3, sur les mêmes lignes que la référence."""
    if len(noise) < MIN_NOISE_RUNS:
        raise ValueError(f"Bruit : {len(noise)} répétitions, il en faut au moins {MIN_NOISE_RUNS} (décision 42)")
    rows = {}
    for name, lines in noise.items():
        pair(reference, lines)  # mêmes lignes et même vérité terrain que la référence, sinon erreur
        rows[name] = {"cer": cer(lines), **{f"cer_{doc}": cer(g) for doc, g in lines.groupby("doc_id")}}
    runs = pd.DataFrame.from_dict(rows, orient="index").rename_axis("repetition")
    spread, limit = threshold(runs["cer"].tolist())
    summary = pd.DataFrame([{"repetitions": len(runs), "cer_min": runs["cer"].min(), "cer_max": runs["cer"].max(),
                             "ecart": spread, "seuil": limit}], index=pd.Index(["tout"], name="groupe"))
    return {"bruit": runs, "seuil": summary}


def tables(reference: pd.DataFrame, model: pd.DataFrame, noise: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Tableaux de la comparaison. `noise` : répétitions de la référence, par nom."""
    noise_out = noise_tables(reference, noise)
    spread, limit = noise_out["seuil"].loc["tout", ["ecart", "seuil"]]
    paired = pair(reference, model)

    row = compare(paired, with_ci=False).loc["tout"].to_dict()
    per_doc = compare(paired, "doc_id", with_ci=False)
    low, high = page_ci(paired)
    checks = conditions(row["difference"], low, high, per_doc["difference"].tolist(), limit)
    summary = {
        "pages": paired["part_id"].nunique(),
        **{k: row[k] for k in ["manuscrits", "lignes", "caracteres", "cer_reference", "cer_modele", "difference"]},
        "ic95_pages_bas": low, "ic95_pages_haut": high,
        "ecart_bruit": spread, "seuil": limit,
        **checks,
        "conclusion": verdict(checks),
    }
    return {
        "global": pd.DataFrame([summary], index=pd.Index(["tout"], name="groupe")),
        "par_manuscrit": per_doc,
        "bruit": noise_out["bruit"],
    }


def run(reference_dir: Path, model_dir: Path | None, noise_dirs: list[Path], output_dir: Path,
        configs_dir: Path = CONFIGS, models_dir: Path = MODELS) -> dict[str, pd.DataFrame]:
    """Comparaison de la variante `model_dir` à la référence ; sans variante, bruit seul.
    Chaque modèle est nommé d'après son dossier (parent de <jeu>/ : f8_finetune_seed43...)."""
    if reference_dir.resolve() not in {d.resolve() for d in noise_dirs}:
        raise ValueError("La référence (F8, seed 42) doit figurer parmi les répétitions du bruit (décision 42)")
    noise = {d.resolve().parent.name: load(d) for d in noise_dirs}
    if len(noise) != len(noise_dirs):
        raise ValueError("Deux répétitions portent le même nom de modèle")
    reference = load(reference_dir)
    model = None if model_dir is None else load(model_dir)
    others = list(noise) + ([] if model_dir is None else [model_dir.resolve().parent.name])
    check_stop_rules(reference_dir.resolve().parent.name, others, configs_dir=configs_dir, models_dir=models_dir)
    out = noise_tables(reference, noise) if model is None else tables(reference, model, noise)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in out.items():
        table.to_csv(output_dir / f"{name}.csv", lineterminator="\n", float_format="%.6f")
    pd.set_option("display.width", 250)
    fmt = lambda x: f"{x:.4f}"  # noqa: E731
    print(f"== bruit\n{out['bruit'].to_string(float_format=fmt)}\n")
    if model_dir is None:
        print(f"== seuil\n{out['seuil'].T.to_string(float_format=fmt)}\n")
    else:
        print(f"== global\n{out['global'].T.to_string(float_format=fmt)}\n")
        shown = ["lignes", "caracteres", "cer_reference", "cer_modele", "difference"]
        print(f"== par_manuscrit\n{out['par_manuscrit'][shown].to_string(float_format=fmt)}\n")
    print(f"-> {output_dir}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference", type=Path, required=True, help="dossier d'evaluate de F8 (seed 42)")
    parser.add_argument("--model", type=Path, help="dossier d'evaluate de la variante ; absent : bruit seul")
    parser.add_argument("--noise", type=Path, nargs="+", required=True,
                        help="dossiers d'evaluate des répétitions de F8 (seeds 42, 43, 44)")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.model, args.noise, args.output_dir)


if __name__ == "__main__":
    main()
