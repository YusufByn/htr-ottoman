"""Analyse des erreurs d'un modèle et de sa référence sur la validation (F12).

Relit les lignes déjà évaluées par `evaluate` (`lignes.parquet`) des deux
modèles : aucune prédiction n'est refaite, aucun modèle n'est chargé. Chaque
prédiction normalisée est alignée sur sa vérité terrain normalisée, puis
chaque erreur (substitution, suppression, insertion) est classée.

- Alignement : même calcul et même préférence à coût égal que
  `evaluate.edit_counts` ; les S, D et I de chaque ligne sont vérifiés contre
  ceux de `evaluate`. Quand plusieurs alignements ont le même coût, un seul
  est retenu : le détail par caractère en dépend un peu, pas le total.
- Catégories, testées dans cet ordre (une erreur n'en a qu'une, la première
  qui s'applique) :
  espace ; séparateur "." (fin d'hémistiche, décision 21) ; chiffre ;
  ponctuation (et symboles) ; ئ (hamza au-dessus d'un yā', U+0654 après ي ou ى :
  en NFD, ئ = ي + hamza) ; ي / ى (substitution de l'un par l'autre) ; puis les
  autres erreurs : substitution à même squelette (lettres qui ne diffèrent
  que par les points, SKELETONS), autre substitution, autre suppression,
  autre insertion.
- Validation seulement : F12 règle sur la validation, jamais sur le test
  interne, clos (décision 39). Toute autre entrée est refusée.

Sorties (dossier --output-dir) : categories.csv, categories_par_operation.csv,
categories_par_manuscrit.csv, operations.csv, par_longueur.csv,
par_manuscrit.csv, pires_lignes.csv et pires_lignes.html (page autonome : images
des lignes intégrées, découpées comme pour le modèle, lues dans le jeu compilé).

Usage : uv run python -m htr_ottoman.analysis.error_analysis --reference reports/baseline/val --model reports/f8_finetune/val --output-dir reports/erreurs/f8_finetune_baseline/val
"""
import argparse
import base64
import html
import io
import itertools
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd
import pyarrow as pa
from PIL import Image

from htr_ottoman.compare import pair
from htr_ottoman.config import MAKHZAN_PROCESSED, ROOT
from htr_ottoman.normalize import ALEF_MAKSURA, YEH

SPLIT = "val"
SUBSTITUTION, DELETION, INSERTION = "substitution", "suppression", "insertion"
SPACE, VERSE_SEPARATOR, HAMZA_ABOVE = " ", ".", "ٔ"
# Lettres de même squelette : seuls les points (ou le trait de گ) les distinguent,
# au moins dans une position du mot. Approximation : les formes finales de ن, ي, ق
# ont leur propre tracé. ى n'y figure pas : sa confusion avec ي a sa catégorie.
SKELETONS = ["بتثنيپٮ", "جحخچ", "دذ", "رزژ", "سش", "صض", "طظ", "عغ", "فقڡ", "هة", "كگڭ"]
SKELETON_OF = {c: i for i, group in enumerate(SKELETONS) for c in group}
CATEGORIES = [
    "espace", "séparateur .", "chiffre", "ponctuation", "ئ", "ي / ى",
    "même squelette (points)", "autre substitution", "autre suppression", "autre insertion",
]
LENGTH_BINS = [0, 40, 50, 60, float("inf")]
LENGTH_LABELS = ["< 40", "40-49", "50-59", ">= 60"]
MIN_CHARS_WORST = 20  # les pires lignes sont choisies parmi celles d'au moins 20 caractères
N_WORST = 8


def align(reference: str, hypothesis: str) -> list[tuple[str, str]]:
    """Alignement de coût minimal : paires (caractère de référence, caractère prédit),
    "" du côté où il manque un caractère. À coût égal : substitution, puis suppression,
    puis insertion, comme `evaluate.edit_counts` (donc mêmes S, D et I)."""
    n, m = len(reference), len(hypothesis)
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    move = [[""] * (m + 1) for _ in range(n + 1)]
    for j in range(1, m + 1):
        cost[0][j], move[0][j] = j, INSERTION
    for i in range(1, n + 1):
        cost[i][0], move[i][0] = i, DELETION
        for j in range(1, m + 1):
            cost[i][j], move[i][j] = min(
                (cost[i - 1][j - 1] + (reference[i - 1] != hypothesis[j - 1]), SUBSTITUTION),
                (cost[i - 1][j] + 1, DELETION),
                (cost[i][j - 1] + 1, INSERTION),
                key=lambda t: t[0],
            )
    pairs, i, j = [], n, m
    while i or j:
        step = move[i][j]
        if step == SUBSTITUTION:
            pairs.append((reference[i - 1], hypothesis[j - 1]))
            i, j = i - 1, j - 1
        elif step == DELETION:
            pairs.append((reference[i - 1], ""))
            i -= 1
        else:
            pairs.append(("", hypothesis[j - 1]))
            j -= 1
    return pairs[::-1]


def category(ref: str, hyp: str, ref_before: str = "", hyp_before: str = "") -> str:
    """Catégorie d'une erreur (voir l'en-tête du module). `ref_before` et `hyp_before` :
    caractère qui précède de chaque côté, pour reconnaître la hamza de ئ."""
    chars = {c for c in (ref, hyp) if c}
    if SPACE in chars:
        return "espace"
    if VERSE_SEPARATOR in chars:
        return "séparateur ."
    if any(unicodedata.category(c) == "Nd" for c in chars):
        return "chiffre"
    if any(unicodedata.category(c)[0] in "PS" for c in chars):
        return "ponctuation"
    if HAMZA_ABOVE in chars and (ref_before if ref == HAMZA_ABOVE else hyp_before) in (YEH, ALEF_MAKSURA):
        return "ئ"
    if chars == {YEH, ALEF_MAKSURA}:
        return "ي / ى"
    if ref and hyp:
        same = ref in SKELETON_OF and SKELETON_OF[ref] == SKELETON_OF.get(hyp)
        return "même squelette (points)" if same else "autre substitution"
    return "autre suppression" if ref else "autre insertion"


def line_errors(reference: str, hypothesis: str) -> list[dict]:
    """Erreurs d'une ligne : opération, caractère de référence, caractère prédit, catégorie."""
    errors, ref_before, hyp_before = [], "", ""
    for r, h in align(reference, hypothesis):
        if r != h:
            op = SUBSTITUTION if r and h else (DELETION if r else INSERTION)
            errors.append({"operation": op, "ref": r, "hyp": h,
                           "categorie": category(r, h, ref_before, hyp_before)})
        ref_before, hyp_before = r or ref_before, h or hyp_before
    return errors


def check_split(lines: pd.DataFrame, source: str) -> None:
    """Refuse tout autre jeu que la validation (F12, décision 39)."""
    splits = set(lines["split"])
    if splits != {SPLIT}:
        raise ValueError(f"{source} : jeu {sorted(splits)}. L'analyse d'erreurs de F12 ne porte que sur "
                         f"la validation ; le test interne est clos (décision 39).")


def error_table(lines: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par erreur. Vérifie que les S, D, I de chaque ligne sont ceux d'`evaluate`."""
    rows = []
    for line in lines.itertuples():
        errors = line_errors(line.ref_norm, line.hyp_norm)
        n = Counter(e["operation"] for e in errors)
        if (n[SUBSTITUTION], n[DELETION], n[INSERTION]) != (line.substitutions, line.deletions, line.insertions):
            raise ValueError(f"Ligne {line.line_id} : alignement différent de celui d'evaluate")
        rows += [{"line_id": line.line_id, "doc_id": line.doc_id, **e} for e in errors]
    return pd.DataFrame(rows, columns=["line_id", "doc_id", "operation", "ref", "hyp", "categorie"])


def char_label(c: str) -> str:
    """Caractère lisible hors contexte : signe combinant posé sur ◌, nom Unicode."""
    if not c:
        return ""
    shown = f"◌{c}" if unicodedata.category(c).startswith("M") else ("␣" if c == SPACE else c)
    return f"{shown} U+{ord(c):04X} {unicodedata.name(c, '?')}"


def _counts(errors: dict[str, pd.DataFrame], index: pd.Index) -> pd.DataFrame:
    """Nombre d'erreurs de chaque modèle (une colonne par modèle) pour chaque clé de `index`,
    dans l'ordre de `index` ; les clés sans aucune erreur sont retirées."""
    keys = list(index.names)
    counts = pd.concat({m: e.groupby(keys).size() for m, e in errors.items()}, axis=1)
    counts = counts.reindex(index).fillna(0).astype(int)
    return counts[counts.sum(axis=1) > 0]


def _shares(counts: pd.DataFrame, errors_total, chars) -> pd.DataFrame:
    """Pour chaque modèle : erreurs, part de ses erreurs, contribution au CER en points."""
    out = pd.DataFrame(index=counts.index)
    for m in counts.columns:
        out[f"erreurs_{m}"] = counts[m]
        out[f"part_{m}"] = counts[m] / errors_total(m)
        out[f"points_cer_{m}"] = 100 * counts[m] / chars
    return out


def tables(reference: pd.DataFrame, model: pd.DataFrame, names: tuple[str, str]) -> dict[str, pd.DataFrame]:
    """Tous les tableaux de l'analyse, à partir des lignes évaluées des deux modèles."""
    check_split(reference, names[0])
    check_split(model, names[1])
    paired = pair(reference, model)  # mêmes lignes, même vérité terrain, sinon erreur
    lines = {names[0]: reference.set_index("line_id").loc[paired["line_id"]].reset_index(),
             names[1]: model.set_index("line_id").loc[paired["line_id"]].reset_index()}
    errors = {m: error_table(lines[m]) for m in names}
    chars = int(paired["ref_chars"].sum())
    for m in names:
        if len(errors[m]) != lines[m]["errors"].sum():
            raise ValueError(f"{m} : total des erreurs différent de celui d'evaluate")

    out = {}
    total = {m: len(e) for m, e in errors.items()}
    counts = _counts(errors, pd.Index(CATEGORIES, name="categorie")).reindex(CATEGORIES, fill_value=0)
    counts.loc["total"] = counts.sum()
    out["categories"] = _shares(counts, total.get, chars)

    counts = _counts(errors, pd.MultiIndex.from_product(
        [CATEGORIES, [SUBSTITUTION, DELETION, INSERTION]], names=["categorie", "operation"]))
    out["categories_par_operation"] = _shares(counts, total.get, chars)

    docs = sorted(paired["doc_id"].unique())
    counts = _counts(errors, pd.MultiIndex.from_product([docs, CATEGORIES], names=["doc_id", "categorie"]))
    doc = counts.index.get_level_values("doc_id")
    doc_chars = paired.groupby("doc_id")["ref_chars"].sum().reindex(doc).to_numpy()
    doc_errors = {m: e.groupby("doc_id").size().reindex(doc).to_numpy() for m, e in errors.items()}
    out["categories_par_manuscrit"] = _shares(counts, doc_errors.get, doc_chars)

    ops = pd.concat({m: e.groupby(["operation", "ref", "hyp", "categorie"]).size() for m, e in errors.items()},
                    axis=1).fillna(0).astype(int).add_prefix("erreurs_").reset_index()
    ops.insert(4, "ref_nom", ops["ref"].map(char_label))
    ops.insert(5, "hyp_nom", ops["hyp"].map(char_label))
    ops = ops.sort_values([f"erreurs_{names[1]}", f"erreurs_{names[0]}", "operation", "ref", "hyp"],
                          ascending=[False, False, True, True, True], kind="stable")
    out["operations"] = ops.reset_index(drop=True)

    paired["longueur"] = pd.cut(paired["ref_chars"], LENGTH_BINS, right=False, labels=LENGTH_LABELS)
    for m in names:
        paired[f"pred_chars_{m}"] = lines[m]["hyp_norm"].str.len().to_numpy()
        paired[f"deletions_{m}"] = lines[m]["deletions"].to_numpy()
    out["par_longueur"] = _length_table(paired, names)
    out["par_manuscrit"] = _doc_table(paired, lines, names)
    out["pires_lignes"] = _worst(paired, lines, names)
    return out


def _cer_columns(g: pd.DataFrame, names: tuple[str, str]) -> dict:
    chars = g["ref_chars"].sum()
    row = {"lignes": len(g), "caracteres": int(chars)}
    for m, suffix in zip(names, ("reference", "modele")):
        row[f"cer_{m}"] = g[f"errors_{suffix}"].sum() / chars
    return row


def _length_table(paired: pd.DataFrame, names: tuple[str, str]) -> pd.DataFrame:
    """CER par longueur de ligne (caractères de la vérité terrain), taux de suppression
    et longueur prédite rapportée à la longueur de la référence."""
    rows = {}
    for label, g in paired.groupby("longueur", observed=False):
        row = _cer_columns(g, names)
        for m in names:
            row[f"taux_suppression_{m}"] = g[f"deletions_{m}"].sum() / g["ref_chars"].sum()
            row[f"longueur_predite_{m}"] = g[f"pred_chars_{m}"].sum() / g["ref_chars"].sum()
        rows[label] = row
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("longueur")


def _doc_table(paired: pd.DataFrame, lines: dict, names: tuple[str, str]) -> pd.DataFrame:
    rows = {}
    for doc, g in paired.groupby("doc_id"):
        row = _cer_columns(g, names)
        for m in names:
            sub = lines[m][lines[m]["doc_id"] == doc]
            for col, label in [("substitutions", "S"), ("deletions", "D"), ("insertions", "I")]:
                row[f"{label}_{m}"] = int(sub[col].sum())
        rows[doc] = row
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("doc_id")


def _worst(paired: pd.DataFrame, lines: dict, names: tuple[str, str]) -> pd.DataFrame:
    """Les N_WORST lignes d'au moins MIN_CHARS_WORST caractères où le modèle a le CER le plus haut."""
    df = paired[["doc_id", "part_id", "line_id", "ref_chars", "ref_norm"]].copy()
    for m, suffix in zip(names, ("reference", "modele")):
        df[f"cer_{m}"] = paired[f"errors_{suffix}"] / paired["ref_chars"]
        df[f"pred_{m}"] = lines[m]["hyp_norm"].to_numpy()
    df = df[df["ref_chars"] >= MIN_CHARS_WORST]
    return df.sort_values([f"cer_{names[1]}", "line_id"], ascending=[False, True]).head(N_WORST).reset_index(drop=True)


def line_images() -> dict[str, Image.Image]:
    """Images des lignes de la validation découpées comme pour le modèle (jeu compilé,
    anciens polygones), en niveaux de gris, par texte normalisé ; chaque texte doit être unique."""
    with pa.memory_map(str(MAKHZAN_PROCESSED / f"{SPLIT}.arrow")) as source:
        records = pa.ipc.open_file(source).read_all().column("lines").to_pylist()
    texts = [r["text"] for r in records]
    if len(set(texts)) != len(texts):
        raise ValueError(f"{SPLIT}.arrow : textes en double, images non attribuables")
    return {r["text"]: Image.open(io.BytesIO(r["im"])).convert("L") for r in records}


def _marked(pairs: list[tuple[str, str]], side: int) -> str:
    """Un côté de l'alignement en HTML, erreurs dans <mark>. Un signe combinant reste
    avec sa lettre (sinon la forme arabe se casse)."""
    clusters = []
    for p in pairs:
        c = p[side]
        if not c:
            continue
        if clusters and unicodedata.category(c).startswith("M"):
            clusters[-1][0] += c
            clusters[-1][1] |= p[0] != p[1]
        else:
            clusters.append([c, p[0] != p[1]])
    parts = []
    for err, group in itertools.groupby(clusters, key=lambda x: x[1]):
        text = html.escape("".join(c for c, _ in group))
        parts.append(f"<mark>{text}</mark>" if err else text)
    return "".join(parts)


HTML_HEAD = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pires lignes, validation</title>
<style>
body { font-family: -apple-system, system-ui, sans-serif; max-width: 980px; margin: 24px auto; padding: 0 16px; color: #1d1d1f; background: #fff; }
h1 { font-size: 1.3rem; } p.note { color: #555; font-size: .9rem; }
section { border-top: 1px solid #ddd; padding: 14px 0; }
.meta { font-size: .85rem; color: #555; margin-bottom: 6px; }
img { max-width: 100%; border: 1px solid #ccc; display: block; margin: 6px 0 10px auto; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-weight: 500; font-size: .8rem; color: #555; width: 9em; vertical-align: top; padding: 4px 8px 4px 0; }
td.t { font-family: "Geeza Pro", "Noto Naskh Arabic", "Amiri", serif; font-size: 1.35rem; line-height: 1.9; padding: 2px 0; }
mark { background: #ffd6d6; color: #a00; border-radius: 3px; }
</style></head><body>
"""


def write_html(worst: pd.DataFrame, names: tuple[str, str], output_dir: Path) -> None:
    """Page des pires lignes : image, vérité terrain et prédictions, erreurs surlignées."""
    images = line_images()
    reference, model = names
    body = [HTML_HEAD, f"<h1>Pires lignes de la validation pour {model} (comparé à {reference})</h1>",
            f"<p class=\"note\">Les {N_WORST} lignes d'au moins {MIN_CHARS_WORST} caractères où {model} a le CER "
            "le plus élevé. Image : la ligne découpée comme pour le modèle (jeu compilé, anciens polygones), "
            "en niveaux de gris ; en noir, ce qui est hors du polygone de la ligne. "
            "Textes après <code>normalize</code>. Surligné : dans la vérité terrain, les caractères mal lus ou "
            "oubliés ; dans une prédiction, les caractères faux ou en trop.</p>"]
    for rank, row in enumerate(worst.itertuples(), 1):
        png = io.BytesIO()
        images[row.ref_norm].save(png, format="PNG")
        src = "data:image/png;base64," + base64.b64encode(png.getvalue()).decode("ascii")
        pairs = align(row.ref_norm, getattr(row, f"pred_{model}"))
        pairs_ref = align(row.ref_norm, getattr(row, f"pred_{reference}"))
        body.append(
            f"<section><div class=\"meta\">{rank}. Doc {row.doc_id}, page {row.part_id}, {row.line_id} : "
            f"{row.ref_chars} caractères, CER {model} {getattr(row, f'cer_{model}'):.0%}, "
            f"{reference} {getattr(row, f'cer_{reference}'):.0%}</div>"
            f"<img src=\"{src}\" alt=\"ligne {row.line_id}\">"
            "<table>"
            f"<tr><th>Vérité terrain</th><td class=\"t\" dir=\"rtl\" lang=\"ota\">{_marked(pairs, 0)}</td></tr>"
            f"<tr><th>{model}</th><td class=\"t\" dir=\"rtl\" lang=\"ota\">{_marked(pairs, 1)}</td></tr>"
            f"<tr><th>{reference}</th><td class=\"t\" dir=\"rtl\" lang=\"ota\">{_marked(pairs_ref, 1)}</td></tr>"
            "</table></section>")
    body.append("</body></html>\n")
    (output_dir / "pires_lignes.html").write_text("\n".join(body), encoding="utf-8")


def write_tables(out: dict[str, pd.DataFrame], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in out.items():
        index = name not in ("operations", "pires_lignes")
        table.to_csv(output_dir / f"{name}.csv", index=index, lineterminator="\n", float_format="%.6f")


def analyse(reference_dir: Path, model_dir: Path, output_dir: Path) -> dict[str, pd.DataFrame]:
    """Calcule et écrit les tableaux et la page des pires lignes dans `output_dir`."""
    names = (reference_dir.parent.name, model_dir.parent.name)
    out = tables(pd.read_parquet(reference_dir / "lignes.parquet"), pd.read_parquet(model_dir / "lignes.parquet"),
                 names)
    write_tables(out, output_dir)
    write_html(out["pires_lignes"], names, output_dir)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    fmt = lambda x: f"{x:.4f}"  # noqa: E731
    print(f"== categories\n{out['categories'].to_string(float_format=fmt)}\n")
    print(f"== categories_par_operation\n{out['categories_par_operation'].to_string(float_format=fmt)}\n")
    for op in (SUBSTITUTION, DELETION, INSERTION):
        top = out["operations"][out["operations"]["operation"] == op].head(12)
        cols = [c for c in top.columns if c.startswith(("ref_nom", "hyp_nom", "erreurs_"))]
        print(f"== {op}s les plus fréquentes ({names[1]})\n{top[cols].to_string(index=False)}\n")
    for name in ("par_longueur", "par_manuscrit"):
        print(f"== {name}\n{out[name].to_string(float_format=fmt)}\n")
    print(f"-> {output_dir.relative_to(ROOT) if output_dir.is_relative_to(ROOT) else output_dir}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference", type=Path, required=True, help="dossier d'evaluate de la référence")
    parser.add_argument("--model", type=Path, required=True, help="dossier d'evaluate du modèle")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    analyse(args.reference.resolve(), args.model.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
