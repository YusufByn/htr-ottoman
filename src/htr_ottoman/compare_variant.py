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

Usage : uv run python -m htr_ottoman.compare_variant --reference reports/f8_finetune/val --model reports/<variante>/val --noise reports/f8_finetune/val reports/f8_finetune_seed43/val reports/f8_finetune_seed44/val --output-dir reports/comparaisons/<variante>_f8_finetune/val
"""
import argparse
from pathlib import Path

import pandas as pd

from htr_ottoman.analysis.error_analysis import check_split
from htr_ottoman.compare import compare, pair, paired_bootstrap_ci

MIN_THRESHOLD = 0.005  # 0,5 point de CER
NOISE_FACTOR = 2
MIN_NOISE_RUNS = 3  # seeds 42, 43 et 44
BETTER, WORSE, NO_DIFFERENCE = "meilleure", "régression", "pas de différence établie"


def load(directory: Path) -> pd.DataFrame:
    lines = pd.read_parquet(directory / "lignes.parquet")
    check_split(lines, str(directory))
    return lines


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


def tables(reference: pd.DataFrame, model: pd.DataFrame, noise: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Tableaux de la comparaison. `noise` : répétitions de la référence, par nom de dossier."""
    if len(noise) < MIN_NOISE_RUNS:
        raise ValueError(f"Bruit : {len(noise)} répétitions, il en faut au moins {MIN_NOISE_RUNS} (décision 42)")
    for name, lines in noise.items():
        pair(reference, lines)  # mêmes lignes et même vérité terrain que la référence, sinon erreur
    paired = pair(reference, model)
    noise_table = pd.DataFrame({"cer": {name: cer(lines) for name, lines in noise.items()}}).rename_axis("repetition")
    spread, limit = threshold(noise_table["cer"].tolist())

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
        "bruit": noise_table,
    }


def run(reference_dir: Path, model_dir: Path, noise_dirs: list[Path], output_dir: Path) -> dict[str, pd.DataFrame]:
    if reference_dir.resolve() not in {d.resolve() for d in noise_dirs}:
        raise ValueError("La référence (F8, seed 42) doit figurer parmi les répétitions du bruit (décision 42)")
    noise = {str(d): load(d) for d in noise_dirs}
    out = tables(load(reference_dir), load(model_dir), noise)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in out.items():
        table.to_csv(output_dir / f"{name}.csv", lineterminator="\n", float_format="%.6f")
    pd.set_option("display.width", 250)
    fmt = lambda x: f"{x:.4f}"  # noqa: E731
    print(f"== bruit\n{out['bruit'].to_string(float_format=fmt)}\n")
    print(f"== global\n{out['global'].T.to_string(float_format=fmt)}\n")
    shown = ["lignes", "caracteres", "cer_reference", "cer_modele", "difference"]
    print(f"== par_manuscrit\n{out['par_manuscrit'][shown].to_string(float_format=fmt)}\n")
    print(f"-> {output_dir}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference", type=Path, required=True, help="dossier d'evaluate de F8 (seed 42)")
    parser.add_argument("--model", type=Path, required=True, help="dossier d'evaluate de la variante")
    parser.add_argument("--noise", type=Path, nargs="+", required=True,
                        help="dossiers d'evaluate des répétitions de F8 (seeds 42, 43, 44)")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.model, args.noise, args.output_dir)


if __name__ == "__main__":
    main()
