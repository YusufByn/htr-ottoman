"""Évaluation : CER (taux d'erreur par caractère) global et ventilé (F5).

- Les deux côtés passent par `normalize` (unique normalisation du projet) ;
  les prédictions sont en ordre logique (BiDi appliqué à la prédiction, décision 26).
- CER micro : erreurs totales / caractères totaux de la vérité terrain ;
  les espaces comptent comme des caractères (décision 28).
- Intervalle de confiance à 95 % par bootstrap sur les manuscrits (tirage avec
  remise de manuscrits entiers), seulement pour les groupes d'au moins 3
  manuscrits (décision 30).
- Ce calcul fait référence ; `ketos test` sert de contrôle (décision 29).
- Convention des erreurs : substitution ; suppression = caractère de la vérité
  terrain absent de la prédiction ; insertion = caractère en trop dans la
  prédiction.

Usage : uv run python -m htr_ottoman.evaluate PREDICTIONS.parquet --split val --output-dir DOSSIER
(PREDICTIONS : colonnes part_id, line_id, pred ; voir htr_ottoman.predict)
"""
import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from htr_ottoman.normalize import normalize
from htr_ottoman.splits import SEED, load_split

N_BOOTSTRAP = 1000
CI_LEVEL = 0.95
MIN_DOCS_FOR_CI = 3


@dataclass(frozen=True)
class EditCounts:
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions


def edit_counts(reference: str, hypothesis: str) -> EditCounts:
    """Distance de Levenshtein de `hypothesis` à `reference`, détaillée par type.

    Programmation dynamique : la case (i, j) contient le coût minimal pour
    aligner les i premiers caractères de la référence et les j premiers de
    l'hypothèse. À coût égal, on préfère substitution, puis suppression, puis
    insertion (le total ne dépend pas de ce choix).
    """
    prev = [(j, 0, 0, j) for j in range(len(hypothesis) + 1)]  # (coût, S, D, I)
    for i, r in enumerate(reference, 1):
        cur = [(i, 0, i, 0)]
        for j, h in enumerate(hypothesis, 1):
            c, s, d, n = prev[j - 1]
            diag = (c, s, d, n) if r == h else (c + 1, s + 1, d, n)
            c, s, d, n = prev[j]
            deletion = (c + 1, s, d + 1, n)
            c, s, d, n = cur[j - 1]
            insertion = (c + 1, s, d, n + 1)
            cur.append(min(diag, deletion, insertion, key=lambda t: t[0]))
        prev = cur
    _, s, d, n = prev[-1]
    return EditCounts(s, d, n)


def score_lines(lines: pd.DataFrame, ref_col: str = "text", hyp_col: str = "pred") -> pd.DataFrame:
    """Ajoute à chaque ligne : textes normalisés, caractères de référence et erreurs."""
    out = lines.copy()
    out["ref_norm"] = out[ref_col].map(normalize)
    out["hyp_norm"] = out[hyp_col].fillna("").map(normalize)
    counts = [edit_counts(r, h) for r, h in zip(out["ref_norm"], out["hyp_norm"])]
    out["ref_chars"] = out["ref_norm"].str.len()
    out["substitutions"] = [c.substitutions for c in counts]
    out["deletions"] = [c.deletions for c in counts]
    out["insertions"] = [c.insertions for c in counts]
    out["errors"] = [c.errors for c in counts]
    return out


def bootstrap_ci(scored: pd.DataFrame) -> tuple[float, float]:
    """Intervalle à 95 % du CER micro, en tirant des manuscrits entiers avec remise."""
    per_doc = scored.groupby("doc_id")[["errors", "ref_chars"]].sum()
    if len(per_doc) < MIN_DOCS_FOR_CI:
        return float("nan"), float("nan")
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(per_doc), size=(N_BOOTSTRAP, len(per_doc)))
    errors, chars = per_doc["errors"].to_numpy()[idx].sum(axis=1), per_doc["ref_chars"].to_numpy()[idx].sum(axis=1)
    cers = errors / chars
    alpha = (1 - CI_LEVEL) / 2
    return float(np.quantile(cers, alpha)), float(np.quantile(cers, 1 - alpha))


def _summary_row(g: pd.DataFrame) -> dict:
    chars, errors = int(g["ref_chars"].sum()), int(g["errors"].sum())
    low, high = bootstrap_ci(g)
    return {
        "manuscrits": g["doc_id"].nunique(),
        "lignes": len(g),
        "caracteres": chars,
        "erreurs": errors,
        "substitutions": int(g["substitutions"].sum()),
        "suppressions": int(g["deletions"].sum()),
        "insertions": int(g["insertions"].sum()),
        "cer": errors / chars if chars else float("nan"),
        "ic95_bas": low,
        "ic95_haut": high,
    }


def summarize(scored: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """CER micro par groupe (ou global si `by` est None), avec effectifs et intervalle."""
    if by is None:
        return pd.DataFrame([_summary_row(scored)], index=pd.Index(["tout"], name="groupe"))
    rows = {key: _summary_row(g) for key, g in scored.groupby(by, sort=True)}
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis(by)


def attach_metadata(predictions: pd.DataFrame, split: str) -> pd.DataFrame:
    """Joint aux prédictions la vérité terrain et les métadonnées des lignes du jeu.
    Toutes les lignes compilées du jeu doivent avoir une prédiction, et réciproquement."""
    from htr_ottoman.prepare import select_lines

    lines = select_lines()
    expected = lines[(lines["split"] == split) & lines["exclusion"].isna()]
    multi = load_split(split).set_index("part_id")["is_multilingual"]
    merged = expected.merge(predictions[["part_id", "line_id", "pred"]], on=["part_id", "line_id"],
                            how="outer", indicator=True, validate="one_to_one")
    if (merged["_merge"] != "both").any():
        counts = merged["_merge"].value_counts().to_dict()
        raise ValueError(f"Prédictions et lignes du jeu {split} ne correspondent pas : {counts}")
    merged = merged.drop(columns="_merge")
    merged["is_multilingual"] = merged["part_id"].map(multi)
    return merged


def report(scored: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tables = {
        "global": summarize(scored),
        "par_ecriture": summarize(scored, "script"),
        "par_relecture": summarize(scored, "category"),
        "par_couche_modele": summarize(scored, "is_model_layer"),
        "par_manuscrit": summarize(scored, "doc_id"),
    }
    if scored["is_multilingual"].any():
        tables["sans_multilingue"] = summarize(scored[~scored["is_multilingual"]])
        tables["par_multilinguisme"] = summarize(scored, "is_multilingual")
    works = scored.groupby("doc_id")["work"].first()
    tables["par_manuscrit"].insert(0, "oeuvre", tables["par_manuscrit"].index.map(works))
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--split", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    scored = score_lines(attach_metadata(pd.read_parquet(args.predictions), args.split))
    tables = report(scored)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scored.to_parquet(args.output_dir / "lignes.parquet", index=False)
    for name, table in tables.items():
        table.to_csv(args.output_dir / f"{name}.csv", lineterminator="\n", float_format="%.6f")
    pd.set_option("display.width", 200)
    for name in ["global", "sans_multilingue", "par_ecriture", "par_relecture", "par_couche_modele"]:
        if name in tables:
            print(f"== {name}\n{tables[name].to_string(float_format=lambda x: f'{x:.4f}')}\n")
    print(f"-> {args.output_dir}")


if __name__ == "__main__":
    main()
