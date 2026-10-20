"""F13, Q1 : la catégorie automatique d'une erreur est-elle juste ? Page de lecture (avant la lecture).

Mode exploratoire du test interne (complément du 2026-10-19 à la décision 39) : ne lit
que les deux `lignes.parquet` de F9 (baseline, F8 (lag 5)), après les contrôles
d'`error_analysis.check_exploratory` (SHA-256, entrées, sortie sous reports/f13/) ;
aucun modèle, aucune prédiction, aucune image (précision du plan du 2026-10-20).

- Erreurs : chaque prédiction alignée sur sa vérité terrain (`error_analysis.align`),
  chaque erreur classée comme dans `error_analysis` (`category`) ; les comptes par
  catégorie sont vérifiés contre ceux d'`error_analysis.tables`.
- Tirage : erreurs des deux modèles réunies par catégorie, N_PER_CATEGORY par
  catégorie (toutes s'il y en a moins), seed `splits.SEED` ; page groupée par
  catégorie dans l'ordre du plan, mélangée à l'intérieur. echantillon.csv : modèle,
  catégorie, ligne, position dans l'alignement, taille de la catégorie, poids.
- Page HTML autonome : modèle, catégorie, question ; segment de la vérité terrain et
  segment prédit (CONTEXT cases de chaque côté), paire d'erreur surlignée en fort,
  autres différences en clair ; grille alignée case par case. Ni image, ni manuscrit,
  ni identifiant de ligne. Réponses oui / non / incertain et un commentaire, gardées
  dans le navigateur (localStorage), téléchargées en CSV.
- jugements.csv : gabarit versionné, jamais écrasé.

Sorties : reports/f13/q1_conventions/lecture/.

Usage : uv run python -m htr_ottoman.analysis.category_check
"""
import html
import json
import re
import unicodedata

import numpy as np
import pandas as pd

from htr_ottoman.analysis.error_analysis import (CATEGORIES, EXPLORATORY_INPUTS, EXPLORATORY_SPLIT, MENTION, align,
                                                 category, check_exploratory, check_split, tables)
from htr_ottoman.config import REPORTS, ROOT
from htr_ottoman.splits import SEED

N_PER_CATEGORY = 10
CONTEXT = 4
MODEL_LABELS = {"baseline": "baseline", "f8_finetune": "F8 (lag 5)"}
OUTPUT = REPORTS / "f13" / "q1_conventions" / "lecture"
PAGE = OUTPUT / "lecture.html"
STORAGE_KEY = "htr_f13_q1_categories_v1"
ANSWERS = ("oui", "non", "incertain")
HEADER = ("identifiant", "réponse", "commentaire")
QUESTIONS = {
    "espace": "La case surlignée met-elle un blanc (␣) face à rien ou à autre chose, avec les voisines identiques ?",
    "séparateur .": "La case surlignée a-t-elle un point « . » d'un côté, face à rien ou à une autre forme, avec les "
                    "voisines identiques ?",
    "chiffre": "Un chiffre du tableau est-il dans la case surlignée, d'un côté au moins, avec les voisines identiques ?",
    "ponctuation": "Un signe du tableau de ponctuation est-il dans la case surlignée, d'un côté au moins, avec les "
                   "voisines identiques ?",
    "ئ": "La seule différence est-elle la petite marque de hamza (◌ٔ) sur ي ou ى, avec les voisines identiques ?",
    "ي / ى": "Les deux formes sont-elles identiques, sauf les deux points dessous, avec les voisines identiques ?",
    "même squelette (points)": "Les deux formes sont-elles identiques, sauf les points (ou le petit trait de گ) ?",
    "autre substitution": "Les deux formes sont-elles nettement différentes, au-delà des points ?",
    "autre suppression": "Côté vérité terrain, la case surlignée est-elle une lettre entière, sans rien en face et sans "
                         "la même forme juste à côté en face ?",
    "autre insertion": "Côté prédiction, la case surlignée est-elle une lettre entière, sans rien en face et sans la "
                       "même forme juste à côté en face ?",
}
LIMITS = {
    "espace": "Un autre blanc différent dans une case voisine est ignoré.",
    "séparateur .": "« . » face à ه ou ة : oui.",
    "chiffre": "Chiffre face à une lettre de forme proche : oui, commentaire « forme proche ». Un autre chiffre "
               "différent du même nombre dans une case voisine est ignoré.",
    "ئ": "Autre marque (par exemple ◌ٓ) : non, commentaire « autre marque ».",
    "même squelette (points)": "Formes finales de tracé différent (par exemple ن et ب en fin de mot) : non, "
                               "commentaire « forme finale ».",
    "autre substitution": "Non, avec le commentaire « points seulement », « petite marque » ou « décalage ».",
    "autre suppression": "Non, avec le commentaire « petite marque » ou « décalage ».",
    "autre insertion": "Non, avec le commentaire « petite marque » ou « décalage ».",
}
RULES = (
    "« Juste » : la paire surlignée en fort montre bien le type de différence que nomme la catégorie.",
    "« Voisines identiques » : la case juste avant et la case juste après la paire surlignée sont identiques "
    "des deux côtés (vérité terrain et prédiction). Les autres cases du contexte n'entrent pas dans la règle.",
    "Commentaires types : « décalage » (la même forme est juste à côté, de l'autre côté), « zone brouillée » "
    "(case juste avant ou juste après différente), « petite marque » (signe posé sur une lettre, montré sur ◌).",
)
REFERENCE = (  # (rubrique, [(formes, légende)])
    ("Chiffres", [("٠ ١ ٢ ٣ ٤ ٥ ٦ ٧ ٨ ٩", "arabes orientaux"), ("۰ ۱ ۲ ۳ ۴ ۵ ۶ ۷ ۸ ۹", "persans")]),
    ("Ponctuation", [("، ؛ ؟ ! : ( ) « » - /", "")]),
    ("Marques posées sur une lettre", [("◌ٔ", "hamza"), ("◌ٕ", "hamza dessous"), ("◌ٓ", "madda"),
                                       ("◌َ ◌ُ ◌ِ ◌ً ◌ٌ ◌ٍ", "voyelles"), ("◌ّ", "shadda"), ("◌ْ", "sukun")]),
    ("ي et ى", [("ي", "deux points dessous"), ("ى", "sans points")]),
    ("Grille", [("␣", "espace"), ("∅", "rien en face"), ("◌", "signe posé sur une lettre"),
                ("", "lecture de droite à gauche")]),
)
MARK = re.compile("◌[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]?")


def with_marks(escaped: str) -> str:
    """Entoure chaque ◌ (avec son signe) d'une police qui sait l'afficher (Geeza Pro n'a pas ◌)."""
    return MARK.sub(lambda m: f"<span class=\"mk\">{m.group(0)}</span>", escaped)


def model_errors(lines: pd.DataFrame, model: str) -> pd.DataFrame:
    """Une ligne par erreur, avec sa position dans l'alignement de la ligne (même classement qu'`error_analysis`)."""
    rows = []
    for line in lines.itertuples():
        ref_before = hyp_before = ""
        for k, (r, h) in enumerate(align(line.ref_norm, line.hyp_norm)):
            if r != h:
                rows.append({"modele": model, "doc_id": line.doc_id, "line_id": line.line_id, "position": k,
                             "categorie": category(r, h, ref_before, hyp_before)})
            ref_before, hyp_before = r or ref_before, h or hyp_before
    return pd.DataFrame(rows)


def load() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    reference_dir, model_dir = EXPLORATORY_INPUTS
    check_exploratory(reference_dir, model_dir, OUTPUT)  # avant toute lecture
    lines = {d.parent.name: pd.read_parquet(d / "lignes.parquet") for d in EXPLORATORY_INPUTS}
    for name, table in lines.items():
        check_split(table, name, EXPLORATORY_SPLIT)
    errors = pd.concat([model_errors(t, m) for m, t in lines.items()], ignore_index=True)
    expected = tables(lines["baseline"], lines["f8_finetune"], ("baseline", "f8_finetune"), EXPLORATORY_SPLIT)
    counts = errors.groupby(["categorie", "modele"]).size().unstack(fill_value=0)
    for model in lines:
        if not counts[model].reindex(CATEGORIES, fill_value=0).equals(
                expected["categories"][f"erreurs_{model}"].drop("total").astype(int).rename(model)):
            raise ValueError(f"{model} : comptes par catégorie différents de ceux d'error_analysis")
    return lines, errors


def sample(errors: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    parts = []
    for cat in CATEGORIES:
        pool = errors[errors["categorie"] == cat].reset_index(drop=True)
        n = min(N_PER_CATEGORY, len(pool))
        chosen = pool.iloc[np.sort(rng.choice(len(pool), size=n, replace=False))]
        chosen = chosen.iloc[rng.permutation(n)].copy()
        chosen["taille_categorie"], chosen["n_categorie"], chosen["poids"] = len(pool), n, len(pool) / n
        parts.append(chosen)
    chosen = pd.concat(parts, ignore_index=True)
    chosen.insert(0, "identifiant", [f"q1_{i + 1:03d}" for i in range(len(chosen))])
    return chosen.assign(mention=MENTION)


def cell(c: str) -> str:
    """Un caractère de la grille, lisible seul : signe combinant sur ◌, espace ␣, rien ∅."""
    if not c:
        return "∅"
    if c == " ":
        return "␣"
    return f"◌{c}" if unicodedata.combining(c) else c


def window(pairs: list[tuple[str, str]], k: int, context: int = CONTEXT) -> list[tuple[str, str, str]]:
    """Paires du contexte autour de la paire `k`, avec leur niveau : erreur, autre différence ou identique."""
    lo, hi = max(0, k - context), min(len(pairs), k + context + 1)
    return [(r, h, "err" if j == k else "diff" if r != h else "") for j, (r, h) in enumerate(pairs[lo:hi], lo)]


def segment(cells: list[tuple[str, str, str]], side: int) -> str:
    """Un côté du contexte en texte suivi, différences surlignées ; un signe combinant reste avec sa lettre."""
    clusters = []
    for item in cells:
        c, level = item[side], item[2]
        if not c:
            continue
        if clusters and unicodedata.combining(c):
            clusters[-1][0] += c
            clusters[-1][1] = max(clusters[-1][1], level, key=("", "diff", "err").index)
        else:
            clusters.append([c, level])
    out = []
    for text, level in clusters:
        shown = html.escape(text.replace(" ", " "))
        out.append(f"<mark class=\"{level}\">{shown}</mark>" if level else shown)
    return "".join(out)


def grid(cells: list[tuple[str, str, str]]) -> str:
    rows = []
    for side, label in ((0, "vérité terrain"), (1, "prédiction")):
        tds = "".join(f"<td class=\"{lvl}\">{with_marks(html.escape(cell((r, h)[side])))}</td>" for r, h, lvl in cells)
        rows.append(f"<tr><th>{label}</th>{tds}</tr>")
    return f"<table class=\"grid\" dir=\"rtl\">{''.join(rows)}</table>"


PAGE_HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F13 Q1 : catégories d'erreurs</title>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 0 auto; max-width: 1100px; padding: 16px;
         background: #fafafa; color: #1a1a1a; line-height: 1.45; }
  header { position: sticky; top: 0; background: #fafafa; padding: 8px 0; border-bottom: 1px solid #ccc; z-index: 1; }
  .item { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 12px; margin: 16px 0; }
  .item.done { border-color: #7a7; }
  .meta { color: #555; font-size: 0.92em; }
  .question { font-weight: 600; margin-top: 8px; }
  .limit { color: #555; font-size: 0.92em; }
  .seg { font-family: "Geeza Pro", "Noto Naskh Arabic", "Amiri", serif; font-size: 2em; line-height: 1.8; }
  .seg th { font-family: -apple-system, "Segoe UI", sans-serif; font-size: 0.4em; font-weight: 500; color: #555;
            text-align: left; padding-right: 12px; white-space: nowrap; }
  mark.err { background: #ffb3b3; } mark.diff { background: #fff0b3; }
  table.grid { border-collapse: collapse; margin: 8px 0; }
  table.grid td { border: 1px solid #ccc; min-width: 2.2em; text-align: center; padding: 4px;
                  font-family: "Geeza Pro", "Noto Naskh Arabic", "Amiri", serif; font-size: 1.6em; }
  table.grid td.err { background: #ffb3b3; } table.grid td.diff { background: #fff0b3; }
  table.grid th { font-weight: 500; font-size: 0.85em; color: #555; padding-left: 8px; text-align: right; }
  table.ref td { padding: 4px 10px; vertical-align: middle; }
  .refitem { display: inline-block; margin-right: 18px; }
  .glyph { font-family: "Geeza Pro", "Noto Naskh Arabic", "Amiri", serif; font-size: 1.5em; margin-right: 4px; }
  .mk { font-family: Arial, "Times New Roman", sans-serif; }
  label { margin-right: 18px; cursor: pointer; }
  textarea { width: 100%; min-height: 2.4em; margin-top: 6px; font: inherit; }
  button { font: inherit; padding: 6px 14px; cursor: pointer; }
  h2.cat { margin-top: 32px; }
</style>
</head>
<body>
"""

PAGE_SCRIPT = """<script>
const KEY = __KEY__;
const IDS = __IDS__;
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { state = {}; }
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
function refresh() {
  let n = 0;
  for (const id of IDS) {
    const done = state[id] && state[id].reponse;
    if (done) n++;
    document.getElementById(id).classList.toggle("done", !!done);
  }
  document.getElementById("progress").textContent = n + " / " + IDS.length + " réponses";
}
for (const id of IDS) {
  const s = state[id] || {};
  for (const input of document.querySelectorAll('input[name="' + id + '"]')) {
    input.checked = input.value === s.reponse;
    input.addEventListener("change", () => { state[id] = Object.assign(state[id] || {}, {reponse: input.value}); save(); refresh(); });
  }
  const area = document.getElementById(id + "_commentaire");
  area.value = s.commentaire || "";
  area.addEventListener("input", () => { state[id] = Object.assign(state[id] || {}, {commentaire: area.value}); save(); });
}
function cell(v) { v = v || ""; return /[",\\n\\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
document.getElementById("download").addEventListener("click", () => {
  const rows = [__HEADER__];
  for (const id of IDS) { const s = state[id] || {}; rows.push([id, s.reponse || "", s.commentaire || ""].map(cell).join(",")); }
  const blob = new Blob([rows.join("\\n") + "\\n"], {type: "text/csv;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "jugements.csv"; a.click();
  URL.revokeObjectURL(a.href);
});
refresh();
</script>
"""


def write_page(items: list[dict]) -> None:
    reference = "".join(
        f"<tr><td>{html.escape(name)}</td><td>"
        + "".join(f"<span class=\"refitem\"><bdi class=\"glyph\" dir=\"rtl\">{with_marks(html.escape(g))}</bdi>"
                  f"{html.escape(label)}</span>" for g, label in items)
        + "</td></tr>" for name, items in REFERENCE)
    parts = [PAGE_HEAD,
             "<header><h1>F13, Q1 : la catégorie automatique est-elle juste ?</h1>",
             "<p><span id=\"progress\"></span> · <button id=\"download\">Télécharger mes réponses (CSV)</button></p></header>",
             "<ul>" + "".join(f"<li>{with_marks(html.escape(r))}</li>" for r in RULES) + "</ul>",
             f"<table class=\"ref\">{reference}</table>",
             "<p class=\"meta\">Pour chaque entrée : le segment de la vérité terrain et le segment prédit (contexte de "
             f"{CONTEXT} cases de chaque côté), la paire d'erreur en rouge, les autres différences en jaune ; dessous, "
             "la grille alignée case par case. Mode exploratoire, décision 39 : prédictions déjà sauvegardées, aucune "
             "image. Les réponses sont gardées dans ce navigateur, même après un rechargement de la page.</p>"]
    current = None
    for item in items:
        i, cat = item["identifiant"], item["categorie"]
        if cat != current:
            limit = f"<p class=\"limit\">Cas limites : {with_marks(html.escape(LIMITS[cat]))}</p>" if cat in LIMITS else ""
            parts.append(f"<h2 class=\"cat\">Catégorie : {html.escape(cat)}</h2>"
                         f"<p class=\"question\">{with_marks(html.escape(QUESTIONS[cat]))}</p>{limit}")
            current = cat
        choices = "".join(f"<label><input type=\"radio\" name=\"{i}\" value=\"{html.escape(a)}\"> {html.escape(a)}</label>"
                          for a in ANSWERS)
        parts.append(
            f"<section class=\"item\" id=\"{i}\"><h3>{i}</h3>"
            f"<p class=\"meta\">Modèle : {html.escape(item['modele'])} · catégorie : <bdi>{html.escape(cat)}</bdi></p>"
            "<table class=\"seg\">"
            f"<tr><th>vérité terrain</th><td dir=\"rtl\">{item['ref']}</td></tr>"
            f"<tr><th>prédiction</th><td dir=\"rtl\">{item['hyp']}</td></tr></table>"
            f"{item['grid']}"
            f"<p class=\"question\">{with_marks(html.escape(QUESTIONS[cat]))}</p><p>{choices}</p>"
            f"<textarea id=\"{i}_commentaire\" placeholder=\"Commentaire (facultatif)\"></textarea></section>")
    ids = [item["identifiant"] for item in items]
    script = (PAGE_SCRIPT.replace("__KEY__", json.dumps(STORAGE_KEY)).replace("__IDS__", json.dumps(ids))
              .replace("__HEADER__", json.dumps(",".join(HEADER), ensure_ascii=False)))
    parts += [script, "</body>\n</html>\n"]
    PAGE.write_text("".join(parts), encoding="utf-8")


def main() -> None:
    lines, errors = load()
    chosen = sample(errors)
    by_line = {m: t.set_index("line_id") for m, t in lines.items()}
    items = []
    for row in chosen.itertuples():
        line = by_line[row.modele].loc[row.line_id]
        pairs = align(line["ref_norm"], line["hyp_norm"])
        if pairs[row.position][0] == pairs[row.position][1]:
            raise ValueError(f"{row.identifiant} : la position tirée n'est pas une erreur")
        cells = window(pairs, row.position)
        items.append({"identifiant": row.identifiant, "categorie": row.categorie,
                      "modele": MODEL_LABELS[row.modele], "ref": segment(cells, 0), "hyp": segment(cells, 1),
                      "grid": grid(cells)})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    chosen.to_csv(OUTPUT / "echantillon.csv", index=False, lineterminator="\n")
    template = OUTPUT / "jugements.csv"
    if not template.exists():  # ne jamais écraser des réponses déjà déposées
        pd.DataFrame({h: chosen["identifiant"] if h == HEADER[0] else "" for h in HEADER}).to_csv(
            template, index=False, lineterminator="\n")
    write_page(items)
    print(chosen.groupby("categorie", sort=False).agg(tires=("identifiant", "size"),
                                                       taille=("taille_categorie", "first")).to_string())
    print(f"-> {OUTPUT.relative_to(ROOT)} ; page : {PAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
