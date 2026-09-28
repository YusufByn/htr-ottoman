"""Comparaison appariée de deux modèles sur les mêmes lignes (F9, décisions 37 et 38).

- Entrées : les dossiers de `evaluate` des deux modèles (lignes.parquet), sur le
  même jeu. Mêmes lignes et même vérité terrain normalisée exigées des deux côtés.
- Différence de CER = CER du modèle moins CER de la référence (négative : le
  modèle fait moins d'erreurs).
- IC à 95 % de la différence par bootstrap apparié sur les manuscrits : à chaque
  tirage, les mêmes manuscrits (avec remise) servent aux deux modèles. Mêmes
  tirages que `evaluate.bootstrap_ci`, groupes d'au moins 3 manuscrits (décision 30).
- Conclusion (décision 38), pour toutes les pages et pour naskh contre autres
  seulement : gain si l'IC est entièrement sous 0, régression s'il est
  entièrement au-dessus, pas de conclusion s'il contient 0. Par écriture et par
  manuscrit : descriptif, sans IC ni conclusion.
- Réduction relative = 1 - CER du modèle / CER de la référence (estimation seule).

Usage : uv run python -m htr_ottoman.compare --reference DOSSIER --model DOSSIER --output-dir DOSSIER
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from htr_ottoman.evaluate import CI_LEVEL, MIN_DOCS_FOR_CI, OTHER_SCRIPTS, bootstrap_draws

MODELS = ("reference", "modele")
COUNTS = ("errors", "substitutions", "deletions", "insertions")
KEYS = ["part_id", "line_id"]
# Colonnes de regroupement, identiques des deux côtés (vérifiées par `pair`)
GROUPING = ["doc_id", "work", "script", "script_group", "category", "is_multilingual"]


def pair(reference: pd.DataFrame, model: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par ligne de texte : métadonnées, caractères de référence et erreurs des deux modèles.
    Refuse deux évaluations qui ne portent pas sur les mêmes lignes ni la même vérité terrain."""
    ref = reference[KEYS + GROUPING + ["ref_norm", "ref_chars", *COUNTS]]
    mod = model[KEYS + GROUPING + ["ref_norm", "ref_chars", *COUNTS]]
    merged = ref.merge(mod, on=KEYS, how="outer", suffixes=("_reference", "_modele"),
                       indicator=True, validate="one_to_one")
    if (merged["_merge"] != "both").any():
        raise ValueError(f"Les deux évaluations ne portent pas sur les mêmes lignes : "
                         f"{merged['_merge'].value_counts().to_dict()}")
    for col in GROUPING + ["ref_norm", "ref_chars"]:
        if not merged[f"{col}_reference"].equals(merged[f"{col}_modele"]):
            raise ValueError(f"Colonne {col} différente entre les deux évaluations")
    out = merged[KEYS].copy()
    for col in GROUPING + ["ref_norm", "ref_chars"]:
        out[col] = merged[f"{col}_reference"]
    for m in MODELS:
        for c in COUNTS:
            out[f"{c}_{m}"] = merged[f"{c}_{m}"]
    return out


def paired_bootstrap_ci(per_doc: pd.DataFrame) -> tuple[float, float]:
    """IC à 95 % de la différence de CER micro (modèle moins référence), les deux modèles
    étant mesurés sur les mêmes manuscrits tirés avec remise."""
    if len(per_doc) < MIN_DOCS_FOR_CI:
        return float("nan"), float("nan")
    idx = bootstrap_draws(len(per_doc))
    chars = per_doc["ref_chars"].to_numpy()[idx].sum(axis=1)
    diffs = (per_doc["errors_modele"].to_numpy()[idx].sum(axis=1)
             - per_doc["errors_reference"].to_numpy()[idx].sum(axis=1)) / chars
    alpha = (1 - CI_LEVEL) / 2
    return float(np.quantile(diffs, alpha)), float(np.quantile(diffs, 1 - alpha))


def conclusion(low: float, high: float) -> str:
    """Règle de la décision 38. Sans intervalle (moins de 3 manuscrits) : pas de conclusion."""
    if high < 0:
        return "gain"
    if low > 0:
        return "régression"
    return "pas de conclusion"


def _row(g: pd.DataFrame, with_ci: bool, with_conclusion: bool) -> dict:
    per_doc = g.groupby("doc_id")[["ref_chars", "errors_reference", "errors_modele"]].sum()
    chars = int(g["ref_chars"].sum())
    row = {"manuscrits": len(per_doc), "lignes": len(g), "caracteres": chars}
    cer = {}
    for m in MODELS:
        errors = int(g[f"errors_{m}"].sum())
        cer[m] = errors / chars if chars else float("nan")
        row.update({f"erreurs_{m}": errors,
                    f"substitutions_{m}": int(g[f"substitutions_{m}"].sum()),
                    f"suppressions_{m}": int(g[f"deletions_{m}"].sum()),
                    f"insertions_{m}": int(g[f"insertions_{m}"].sum()),
                    f"cer_{m}": cer[m]})
    low, high = paired_bootstrap_ci(per_doc) if with_ci else (float("nan"), float("nan"))
    row.update({
        "difference": cer["modele"] - cer["reference"],
        "ic95_bas": low,
        "ic95_haut": high,
        "reduction_relative": 1 - cer["modele"] / cer["reference"] if cer["reference"] else float("nan"),
        "manuscrits_ameliores": int((per_doc["errors_modele"] < per_doc["errors_reference"]).sum()),
    })
    if with_conclusion:
        row["conclusion"] = conclusion(low, high)
    return row


def compare(paired: pd.DataFrame, by: str | None = None, with_ci: bool = True,
            with_conclusion: bool = False) -> pd.DataFrame:
    """Comparaison globale (`by` None) ou par groupe, avec effectifs."""
    if by is None:
        return pd.DataFrame([_row(paired, with_ci, with_conclusion)], index=pd.Index(["tout"], name="groupe"))
    rows = {key: _row(g, with_ci, with_conclusion) for key, g in paired.groupby(by, sort=True)}
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis(by)


def report(paired: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Tableaux de la décision 37, ajustés par la décision 38."""
    tables = {
        "global": compare(paired, with_conclusion=True),  # critère principal : toutes les pages
        "par_ecriture": compare(paired, "script", with_ci=False),
        "par_relecture": compare(paired, "category"),
        "par_manuscrit": compare(paired, "doc_id", with_ci=False),
    }
    if paired["is_multilingual"].any():
        tables["sans_multilingue"] = compare(paired[~paired["is_multilingual"]])
        tables["par_multilinguisme"] = compare(paired, "is_multilingual")
    if (paired["script_group"] == OTHER_SCRIPTS).any():
        tables["par_groupe_ecriture"] = compare(paired, "script_group", with_conclusion=True)
    works = paired.groupby("doc_id")["work"].first()
    tables["par_manuscrit"].insert(0, "oeuvre", tables["par_manuscrit"].index.map(works))
    return tables


def run(reference_dir: Path, model_dir: Path, output_dir: Path) -> dict[str, pd.DataFrame]:
    paired = pair(pd.read_parquet(reference_dir / "lignes.parquet"), pd.read_parquet(model_dir / "lignes.parquet"))
    tables = report(paired)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(output_dir / f"{name}.csv", lineterminator="\n", float_format="%.6f")
    pd.set_option("display.width", 250)
    shown = ["manuscrits", "lignes", "caracteres", "cer_reference", "cer_modele", "difference",
             "ic95_bas", "ic95_haut", "manuscrits_ameliores", "conclusion"]
    for name in ["global", "sans_multilingue", "par_groupe_ecriture", "par_ecriture", "par_relecture"]:
        if name in tables:
            table = tables[name]
            print(f"== {name}\n{table[[c for c in shown if c in table]].to_string(float_format=lambda x: f'{x:.4f}')}\n")
    print(f"-> {output_dir}")
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference", type=Path, required=True, help="dossier de evaluate de la référence (baseline)")
    parser.add_argument("--model", type=Path, required=True, help="dossier de evaluate du modèle comparé")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.model, args.output_dir)


if __name__ == "__main__":
    main()
