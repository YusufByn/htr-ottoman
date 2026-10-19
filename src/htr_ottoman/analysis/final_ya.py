"""F13, Q4 : ي et ى de fin de mot dans Doc 2937, partie avant la lecture de l'utilisateur.

Doc 2937 (validation) emploie ي (deux points dessous) et ى (sans points) en fin de
mot. Ce module prépare une lecture à l'aveugle : les points sont-ils visibles sur
l'image, pour séparer convention de transcription et erreur de lecture.

- Population : fins de mot ي ou ى de Doc 2937 dans la validation (fin de mot comme la
  règle 5 de `normalize` ; ي suivi d'une hamza, soit ئ, exclu), classées d'après la
  prédiction sauvegardée de F8 (lag 5) (`reports/f8_finetune/val/lignes.parquet`),
  alignée comme dans `evaluate` (`error_analysis.align`, vérifié contre S, D, I) :
  correct (même lettre), confondu (l'autre lettre) ; les autres issues (supprimée,
  autre lettre) sont exclues.
- Tirage stratifié (seed `splits.SEED`, ordre mélangé) : ALLOCATION entrées par case
  (lettre de la vérité terrain × issue) ; poids = taille de la case / nombre tiré.
  Cases et poids -> echantillon.csv, jamais affichés sur la page.
- Image en couleur seule : la ligne dans l'image de la page, boîte autour du mot
  estimée d'après l'encre (profil des pixels sombres dans le polygone, cumulé de
  droite à gauche, comme Q3 ; lettres poids 1, espaces, « . » et signes combinants 0),
  puis un agrandissement ×ZOOM de la boîte avec une marge de MARGIN_LETTERS lettres
  de chaque côté.
- Page HTML autonome : ni vérité terrain, ni transcription, ni prédiction, ni lettre
  attendue. Réponses oui / non / incertain et un commentaire, gardées dans le
  navigateur (localStorage), téléchargées en CSV.
- jugements.csv : gabarit versionné, jamais écrasé, remplacé par le CSV téléchargé.

Sorties : reports/f13/q4_ya_final/.

Usage : uv run python -m htr_ottoman.analysis.final_ya
"""
import html
import json
import unicodedata

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from htr_ottoman.analysis.error_analysis import align
from htr_ottoman.analysis.period_ink import data_uri, line_geometry
from htr_ottoman.analysis.rare_chars import check_alignment
from htr_ottoman.analysis.red_ink import INK_THRESHOLD, letter_weight
from htr_ottoman.config import REPORTS, ROOT
from htr_ottoman.normalize import ALEF_MAKSURA, YEH
from htr_ottoman.prepare import select_lines
from htr_ottoman.splits import SEED

DOC = 2937
SPLIT = "val"
HAMZA_ABOVE = "ٔ"
PREDICTIONS = REPORTS / "f8_finetune" / SPLIT  # F8 (lag 5)
ALLOCATION = {(YEH, "confondu"): 18, (YEH, "correct"): 10, (ALEF_MAKSURA, "correct"): 10,
              (ALEF_MAKSURA, "confondu"): 2}
MARGIN_LETTERS = 2.0
ZOOM = 3  # ×2 testé sur q4_01 : deux points difficiles à distinguer (page de 1 000 px de large)
BOX_COLOR = (0, 90, 255)
MARGIN = (30, 20)  # marge du découpage de la ligne (x, y), en pixels de la page
MAX_WIDTH = 1100
QUESTION = "Sous la fin du mot encadré, vois-tu deux points (ou un petit trait, deux points liés) ?"
READING = "Le mot se lit de droite à gauche : sa fin est sa partie la plus à gauche."
CRITERIA = (
    "Oui : deux points, ou un trait court, sous la partie gauche du mot, y compris dans la courbe qui descend "
    "sous la ligne, même si les points y sont un peu décalés vers la droite.",
    "Non : aucune marque sous la fin du mot.",
    "Points nettement sous une lettre plus à droite : ils ne comptent pas. En cas de doute sur la lettre qui les "
    "porte : incertain, commentaire « autre lettre ? ».",
    "Un seul point net : non, commentaire « un point ».",
    "Tache, trou, encre qui traverse le papier : incertain, commentaire « tache ».",
    "Bord gauche de la boîte au milieu d'un mot, deux mots dans la boîte, ou fin du mot introuvable : incertain, "
    "commentaire « boîte décalée ».",
)
ANSWERS = ("oui", "non", "incertain")
HEADER = ("identifiant", "réponse", "commentaire")
OUTPUT = REPORTS / "f13" / "q4_ya_final"
PAGE = OUTPUT / "lecture_a_l_aveugle.html"
STORAGE_KEY = "htr_f13_q4_ya_final_v1"


def word_finals(text: str) -> list[int]:
    """Index des ي et ى de fin de mot (règle 5 de `normalize`), hors ي + hamza (ئ)."""
    finals = []
    for i, c in enumerate(text):
        if c not in (YEH, ALEF_MAKSURA):
            continue
        j = i + 1
        while j < len(text) and unicodedata.category(text[j]).startswith("M"):
            j += 1
        final = j == len(text) or not unicodedata.category(text[j]).startswith("L")
        if final and HAMZA_ABOVE not in text[i + 1:j]:
            finals.append(i)
    return finals


def outcomes(reference: str, hypothesis: str) -> list[dict]:
    """Issue de chaque fin de mot ي / ى de la référence : correct, confondu ou autre."""
    finals, rows, index = set(word_finals(reference)), [], 0
    for r, h in align(reference, hypothesis):
        if r and index in finals:
            other = ALEF_MAKSURA if r == YEH else YEH
            issue = "correct" if h == r else "confondu" if h == other else "autre"
            rows.append({"index_caractere": index, "lettre": r, "issue": issue})
        if r:
            index += 1
    return rows


def doc_lines() -> pd.DataFrame:
    lines = select_lines()
    return lines[(lines["split"] == SPLIT) & lines["exclusion"].isna() & (lines["doc_id"] == DOC)].copy()


def population(lines: pd.DataFrame) -> pd.DataFrame:
    predicted = pd.read_parquet(PREDICTIONS / "lignes.parquet")
    if set(predicted["split"]) != {SPLIT}:
        raise ValueError("Prédictions de la validation seulement")
    predicted = predicted[predicted["doc_id"] == DOC].set_index("line_id")
    check_alignment(predicted.reset_index(), str(PREDICTIONS.relative_to(ROOT)))
    if set(predicted.index) != set(lines["line_id"]):
        raise ValueError("Lignes de la prédiction et de la vérité terrain différentes")
    rows = []
    for l in lines.itertuples():
        if predicted.loc[l.line_id, "ref_norm"] != l.norm:
            raise ValueError(f"{l.line_id} : vérité terrain différente de celle de la prédiction")
        rows += [{"doc_id": l.doc_id, "part_id": l.part_id, "line_id": l.line_id, **o}
                 for o in outcomes(l.norm, predicted.loc[l.line_id, "hyp_norm"])]
    return pd.DataFrame(rows)


def sample(pop: pd.DataFrame) -> pd.DataFrame:
    kept = pop[pop["issue"] != "autre"]
    rng = np.random.default_rng(SEED)
    parts = []
    for (letter, issue), n in ALLOCATION.items():
        case = kept[(kept["lettre"] == letter) & (kept["issue"] == issue)]
        chosen = case.iloc[np.sort(rng.choice(len(case), size=n, replace=False))].copy()
        chosen["case"] = f"{letter} × {issue}"
        chosen["taille_case"], chosen["n_case"], chosen["poids"] = len(case), n, len(case) / n
        parts.append(chosen)
    chosen = pd.concat(parts, ignore_index=True)
    chosen = chosen.iloc[rng.permutation(len(chosen))].reset_index(drop=True)
    chosen.insert(0, "identifiant", [f"q4_{i + 1:02d}" for i in range(len(chosen))])
    return chosen


def word_bounds(text: str, index: int) -> tuple[int, int]:
    """Index du début du mot qui finit par le caractère `index`, et index juste après ses signes combinants."""
    start = index
    while start > 0 and text[start - 1] != " ":
        start -= 1
    end = index + 1
    while end < len(text) and unicodedata.combining(text[end]):
        end += 1
    return start, end


def ink_profile(page: Image.Image, polygon: list) -> tuple[np.ndarray, int]:
    """Encre cumulée de droite à gauche dans le polygone (de 0 à 1), et bord droit du polygone."""
    mask = Image.new("L", page.size, 0)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)
    xs = [x for x, _ in polygon]
    left, right = min(xs), max(xs)
    gray = np.asarray(page.convert("L"), dtype=float)[:, left:right + 1]
    inside = np.asarray(mask)[:, left:right + 1] > 0
    dark = np.clip(np.median(gray[inside]) - gray, 0, None) * inside
    dark[dark < INK_THRESHOLD * dark.max()] = 0
    cumulative = np.cumsum(dark.sum(axis=0)[::-1])
    return cumulative / cumulative[-1], right


def word_span(page: Image.Image, polygon: list, text: str, index: int,
              margin: float = 0.0) -> tuple[int, int]:
    """Bornes horizontales (pixels de la page) du mot qui finit à `index`, élargies de `margin` lettres."""
    cumulative, right = ink_profile(page, polygon)
    weights = [letter_weight(c) for c in text]
    total = sum(weights)
    start, end = word_bounds(text, index)
    lo = max(0.0, (sum(weights[:start]) - margin) / total)
    hi = min(1.0, (sum(weights[:end]) + margin) / total)
    near = lambda share: int(np.searchsorted(cumulative, share))
    return right - near(hi), right - near(lo)


def framed_line(page: Image.Image, polygon: list, box_span: tuple[int, int]) -> Image.Image:
    xs, ys = [x for x, _ in polygon], [y for _, y in polygon]
    x0, x1 = box_span
    cx0, cy0 = max(0, min(xs) - MARGIN[0]), max(0, min(ys) - MARGIN[1])
    cx1, cy1 = min(page.width, max(xs) + MARGIN[0]), min(page.height, max(ys) + MARGIN[1])
    crop = page.convert("RGB").crop((cx0, cy0, cx1, cy1))
    ImageDraw.Draw(crop).rectangle((x0 - cx0, min(ys) - cy0, x1 - cx0, max(ys) - cy0), outline=BOX_COLOR, width=3)
    if crop.width > MAX_WIDTH:
        crop = crop.resize((MAX_WIDTH, round(crop.height * MAX_WIDTH / crop.width)))
    return crop


def zoomed(page: Image.Image, polygon: list, box_span: tuple[int, int], margin_span: tuple[int, int],
           zoom: int = ZOOM) -> Image.Image:
    """Boîte et marge (sans cadre), agrandies ×`zoom` ; la boîte est tracée après l'agrandissement."""
    ys = [y for _, y in polygon]
    cx0, cy0 = max(0, margin_span[0]), max(0, min(ys) - MARGIN[1])
    cx1, cy1 = min(page.width, margin_span[1]), min(page.height, max(ys) + MARGIN[1])
    crop = page.convert("RGB").crop((cx0, cy0, cx1, cy1))
    crop = crop.resize((crop.width * zoom, crop.height * zoom), Image.LANCZOS)
    box = ((box_span[0] - cx0) * zoom, (min(ys) - cy0) * zoom, (box_span[1] - cx0) * zoom, (max(ys) - cy0) * zoom)
    ImageDraw.Draw(crop).rectangle(box, outline=BOX_COLOR, width=3)
    return crop


PAGE_HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F13 Q4 : lecture à l'aveugle</title>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 0 auto; max-width: 1180px; padding: 16px;
         background: #fafafa; color: #1a1a1a; line-height: 1.45; }
  header { position: sticky; top: 0; background: #fafafa; padding: 8px 0; border-bottom: 1px solid #ccc; z-index: 1; }
  .item { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 12px; margin: 16px 0; }
  .item.done { border-color: #7a7; }
  img { max-width: 100%; height: auto; display: block; margin: 8px 0; }
  .question { font-weight: 600; margin-top: 8px; }
  label { margin-right: 18px; cursor: pointer; }
  textarea { width: 100%; min-height: 2.4em; margin-top: 6px; font: inherit; }
  button { font: inherit; padding: 6px 14px; cursor: pointer; }
  .note { color: #555; font-size: 0.92em; }
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
    parts = [PAGE_HEAD,
             "<header><h1>F13, Q4 : fin de mot (lecture à l'aveugle)</h1>",
             "<p><span id=\"progress\"></span> · <button id=\"download\">Télécharger mes réponses (CSV)</button></p></header>",
             f"<p><b>{html.escape(READING)}</b></p>",
             "<ul class=\"consignes\">" + "".join(f"<li>{html.escape(c)}</li>" for c in CRITERIA) + "</ul>",
             "<p class=\"note\">Pour chaque entrée : la ligne en couleur, avec une boîte autour de l'emplacement "
             f"<b>estimé</b> d'un mot, puis un agrandissement ×{ZOOM} de la boîte avec une marge de chaque côté. "
             "Aucune prédiction ni transcription n'est affichée. Les réponses sont gardées dans ce navigateur, même "
             "après un rechargement de la page.</p>"]
    for item in items:
        i = item["identifiant"]
        choices = "".join(f"<label><input type=\"radio\" name=\"{i}\" value=\"{html.escape(a)}\"> {html.escape(a)}</label>"
                          for a in ANSWERS)
        parts.append(
            f"<section class=\"item\" id=\"{i}\"><h2>{i}</h2>"
            f"<img src=\"{item['line']}\" alt=\"ligne {i}, mot estimé encadré\">"
            f"<img src=\"{item['zoom']}\" alt=\"agrandissement de la boîte {i}\">"
            f"<p class=\"question\">{html.escape(QUESTION)}</p><p>{choices}</p>"
            f"<textarea id=\"{i}_commentaire\" placeholder=\"Commentaire (facultatif)\"></textarea></section>")
    ids = [item["identifiant"] for item in items]
    script = (PAGE_SCRIPT.replace("__KEY__", json.dumps(STORAGE_KEY)).replace("__IDS__", json.dumps(ids))
              .replace("__HEADER__", json.dumps(",".join(HEADER), ensure_ascii=False)))
    parts += [script, "</body>\n</html>\n"]
    PAGE.write_text("".join(parts), encoding="utf-8")


def main() -> None:
    lines = doc_lines()
    pop = population(lines)
    chosen = sample(pop)
    by_id = lines.set_index("line_id")
    items, boxes = [], []
    for row in chosen.itertuples():
        line = by_id.loc[row.line_id]
        _, polygon = line_geometry(line["alto_path"], row.line_id)
        page = Image.open(ROOT / line["image_path"])
        box_span = word_span(page, polygon, line["norm"], row.index_caractere)
        margin_span = word_span(page, polygon, line["norm"], row.index_caractere, MARGIN_LETTERS)
        items.append({"identifiant": row.identifiant, "line": data_uri(framed_line(page, polygon, box_span)),
                      "zoom": data_uri(zoomed(page, polygon, box_span, margin_span))})
        boxes.append(f"{box_span[0]} {box_span[1]}")
    chosen["boite_x"] = boxes
    chosen["image_path"] = [by_id.loc[i, "image_path"] for i in chosen["line_id"]]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    chosen.to_csv(OUTPUT / "echantillon.csv", index=False, lineterminator="\n")
    template = OUTPUT / "jugements.csv"
    if not template.exists():  # ne jamais écraser des réponses déjà déposées
        pd.DataFrame({h: chosen["identifiant"] if h == HEADER[0] else "" for h in HEADER}).to_csv(
            template, index=False, lineterminator="\n")
    write_page(items)
    # Aucun aperçu de l'échantillon : la lecture est à l'aveugle.
    print(f"{len(chosen)} fins de mot tirées parmi {(pop['issue'] != 'autre').sum()} (Doc {DOC}, {len(ALLOCATION)} cases)")
    print(f"-> {OUTPUT.relative_to(ROOT)} ; page : {PAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
