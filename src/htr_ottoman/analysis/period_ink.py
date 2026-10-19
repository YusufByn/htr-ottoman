"""F13, Q5 : « . » sans encre dans le train, partie avant la lecture de l'utilisateur.

Le « . » (fin d'hémistiche, décision 21) est parfois transcrit sans trace d'encre
visible. Ce module prépare la lecture à l'aveugle d'un échantillon :

- Comptage : nombre de « . » par manuscrit du train compilé (`prepare.select_lines`,
  lignes gardées, texte normalisé) -> points_par_manuscrit.csv.
- Échantillon de N_SAMPLE « . » (seed `splits.SEED`) : les manuscrits qui en ont
  SMALL_DOC au plus sont pris en entier ; le reste est réparti entre les autres en
  proportion de leurs « . » (plus forts restes), tiré au hasard dans chaque manuscrit ;
  ordre des éléments mélangé -> echantillon.csv.
- Emplacement : les ALTO n'ont qu'un String par ligne, sans position des mots. La
  zone du « . » est estimée d'après sa place dans le texte (caractères de base,
  signes combinants exclus), reportée de droite à gauche le long de la ligne de
  base ; la boîte est volontairement large. La transcription est affichée avec le
  « . » visé surligné pour retrouver l'endroit exact.
- Page HTML autonome (images de la page d'origine, en couleur, intégrées) : une
  question par élément, réponses oui / non / incertain et commentaire, gardées dans
  le navigateur (localStorage), téléchargées en CSV (identifiant, réponse,
  commentaire). Aucune prédiction n'est lue ni affichée (lecture à l'aveugle).
- jugements.csv : gabarit versionné (identifiants, réponses vides), remplacé par le
  CSV téléchargé une fois la lecture faite.

Sorties : reports/f13/q5_points/.

Usage : uv run python -m htr_ottoman.analysis.period_ink
"""
import base64
import html
import io
import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from htr_ottoman.config import REPORTS, ROOT
from htr_ottoman.data.alto import read_alto
from htr_ottoman.prepare import select_lines
from htr_ottoman.splits import SEED

PERIOD = "."
N_SAMPLE = 40
SMALL_DOC = 5  # manuscrits pris en entier dans l'échantillon
QUESTION = "Y a-t-il de l'encre à cet endroit ?"
ANSWERS = ("oui", "non", "incertain")
OUTPUT = REPORTS / "f13" / "q5_points"
PAGE = OUTPUT / "lecture_a_l_aveugle.html"
STORAGE_KEY = "htr_f13_q5_points_v1"
BOX_COLOR = (0, 90, 255)
MARGIN = (30, 20)  # marge du découpage autour de la ligne (x, y), en pixels de la page
MAX_WIDTH = 1100


def train_lines() -> pd.DataFrame:
    lines = select_lines()
    return lines[(lines["split"] == "train") & lines["exclusion"].isna()].copy()


def count_table(lines: pd.DataFrame) -> pd.DataFrame:
    lines = lines.assign(points=lines["norm"].str.count(rf"\{PERIOD}"))
    table = lines.groupby(["doc_id", "work", "script"]).agg(
        lignes=("line_id", "size"), points=("points", "sum"),
        lignes_avec_point=("points", lambda p: int((p > 0).sum()))).reset_index()
    table["part_des_points"] = (table["points"] / table["points"].sum()).round(4)
    return table.rename(columns={"work": "oeuvre", "script": "ecriture"})


def occurrences(lines: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par « . » du train : ligne, rang dans la ligne, index dans le texte normalisé."""
    rows = []
    for line in lines.itertuples():
        positions = [i for i, c in enumerate(line.norm) if c == PERIOD]
        rows += [{"doc_id": line.doc_id, "part_id": line.part_id, "line_id": line.line_id,
                  "rang_point": k + 1, "index_caractere": i} for k, i in enumerate(positions)]
    return pd.DataFrame(rows)


def allocation(counts: pd.Series, n: int = N_SAMPLE, small: int = SMALL_DOC) -> dict[int, int]:
    """Nombre de « . » tirés par manuscrit : petits manuscrits en entier, le reste au prorata."""
    counts = counts[counts > 0]
    alloc = {doc: int(c) for doc, c in counts.items() if c <= small}
    big = counts[counts > small]
    rest = n - sum(alloc.values())
    quotas = big / big.sum() * rest
    base = np.floor(quotas).astype(int)
    order = (quotas - base).sort_values(ascending=False).index
    extra = rest - int(base.sum())
    for doc in big.index:
        alloc[doc] = int(base[doc]) + (1 if doc in order[:extra] else 0)
    return dict(sorted(alloc.items()))


def sample(lines: pd.DataFrame) -> pd.DataFrame:
    occ = occurrences(lines)
    rng = np.random.default_rng(SEED)
    parts = []
    for doc, k in allocation(occ["doc_id"].value_counts()).items():
        candidates = occ[occ["doc_id"] == doc]
        parts.append(candidates.iloc[np.sort(rng.choice(len(candidates), size=k, replace=False))])
    chosen = pd.concat(parts, ignore_index=True)
    chosen = chosen.iloc[rng.permutation(len(chosen))].reset_index(drop=True)
    chosen.insert(0, "identifiant", [f"q5_{i + 1:02d}" for i in range(len(chosen))])
    return chosen


def relative_position(text: str, index: int) -> float:
    """Place du caractère `index` dans la ligne, de 0 (début logique) à 1, en caractères de base."""
    base = [not unicodedata.combining(c) for c in text]
    return (sum(base[:index]) + 0.5) / sum(base)


def estimated_box(baseline: list, polygon: list, text: str, index: int) -> tuple[int, int, int, int]:
    """Boîte (x0, y0, x1, y1) autour de l'emplacement estimé, de droite à gauche le long de la ligne de base."""
    xs = [x for x, _ in baseline] or [x for x, _ in polygon]
    left, right = min(xs), max(xs)
    width = right - left
    n_base = sum(not unicodedata.combining(c) for c in text)
    half = max(0.05 * width, 1.5 * width / n_base)
    center = right - relative_position(text, index) * width
    ys = [y for _, y in polygon] or [y for _, y in baseline]
    return int(center - half), min(ys), int(center + half), max(ys)


def line_geometry(alto_path: str, line_id: str):
    page = read_alto((ROOT / alto_path).read_bytes())
    line = next(l for l in page.lines if l.line_id == line_id)
    return line.baseline, line.polygon


def crop_with_box(image_path: str, polygon: list, box: tuple[int, int, int, int]) -> Image.Image:
    image = Image.open(ROOT / image_path).convert("RGB")
    xs, ys = [x for x, _ in polygon], [y for _, y in polygon]
    x0, y0 = max(0, min(xs + [box[0]]) - MARGIN[0]), max(0, min(ys) - MARGIN[1])
    x1, y1 = min(image.width, max(xs + [box[2]]) + MARGIN[0]), min(image.height, max(ys) + MARGIN[1])
    crop = image.crop((x0, y0, x1, y1))
    ImageDraw.Draw(crop).rectangle((box[0] - x0, box[1] - y0, box[2] - x0, box[3] - y0), outline=BOX_COLOR, width=3)
    if crop.width > MAX_WIDTH:
        crop = crop.resize((MAX_WIDTH, round(crop.height * MAX_WIDTH / crop.width)))
    return crop


def marked_text(text: str, index: int) -> str:
    return f"{html.escape(text[:index])}<mark>{html.escape(text[index])}</mark>{html.escape(text[index + 1:])}"


def data_uri(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


PAGE_HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F13 Q5 : lecture à l'aveugle</title>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 0 auto; max-width: 1180px; padding: 16px;
         background: #fafafa; color: #1a1a1a; line-height: 1.45; }
  header { position: sticky; top: 0; background: #fafafa; padding: 8px 0; border-bottom: 1px solid #ccc; z-index: 1; }
  .item { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 12px; margin: 16px 0; }
  .item.done { border-color: #7a7; }
  img { max-width: 100%; height: auto; display: block; margin: 8px 0; }
  .text { font-size: 1.5em; font-family: "Geeza Pro", "Noto Naskh Arabic", "Amiri", serif; }
  mark { background: #ffd54a; padding: 0 0.15em; }
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
  const rows = ["identifiant,réponse,commentaire"];
  for (const id of IDS) { const s = state[id] || {}; rows.push([id, s.reponse || "", s.commentaire || ""].map(cell).join(",")); }
  const blob = new Blob([rows.join("\\n") + "\\n"], {type: "text/csv;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "jugements.csv"; a.click();
  URL.revokeObjectURL(a.href);
});
refresh();
</script>
"""


def write_page(items: list[dict], path: Path) -> None:
    parts = [PAGE_HEAD,
             "<header><h1>F13, Q5 : « . » sans encre (lecture à l'aveugle)</h1>",
             f"<p><span id=\"progress\"></span> · <button id=\"download\">Télécharger mes réponses (CSV)</button></p></header>",
             "<p class=\"note\">Pour chaque ligne du train, la boîte bleue entoure l'emplacement <b>estimé</b> du « . » "
             "surligné dans la transcription (estimé d'après sa place dans le texte : la boîte peut être décalée ; "
             "repérez l'endroit exact grâce aux mots qui l'entourent). Aucune prédiction de modèle n'est affichée. "
             "Les réponses sont gardées dans ce navigateur, même après un rechargement de la page.</p>"]
    for item in items:
        i = item["identifiant"]
        radios = "".join(f"<label><input type=\"radio\" name=\"{i}\" value=\"{a}\"> {a}</label>" for a in ANSWERS)
        parts.append(
            f"<section class=\"item\" id=\"{i}\"><h2>{i}</h2>"
            f"<img src=\"{item['image']}\" alt=\"ligne {i}, emplacement estimé du point encadré\">"
            f"<p class=\"text\" dir=\"rtl\" lang=\"ota\">{item['text']}</p>"
            f"<p class=\"question\">{html.escape(QUESTION)}</p><p>{radios}</p>"
            f"<textarea id=\"{i}_commentaire\" placeholder=\"Commentaire (facultatif)\"></textarea></section>")
    ids = [item["identifiant"] for item in items]
    parts.append(PAGE_SCRIPT.replace("__KEY__", json.dumps(STORAGE_KEY)).replace("__IDS__", json.dumps(ids)))
    parts.append("</body>\n</html>\n")
    path.write_text("".join(parts), encoding="utf-8")


def main() -> None:
    lines = train_lines()
    counts = count_table(lines)
    chosen = sample(lines)
    by_id = lines.set_index("line_id")
    items, boxes, positions = [], [], []
    for row in chosen.itertuples():
        line = by_id.loc[row.line_id]
        baseline, polygon = line_geometry(line["alto_path"], row.line_id)
        box = estimated_box(baseline, polygon, line["norm"], row.index_caractere)
        boxes.append(" ".join(map(str, box)))
        positions.append(round(relative_position(line["norm"], row.index_caractere), 4))
        items.append({"identifiant": row.identifiant,
                      "image": data_uri(crop_with_box(line["image_path"], polygon, box)),
                      "text": marked_text(line["norm"], row.index_caractere)})
    chosen["position_relative"] = positions
    chosen["boite_estimee"] = boxes
    chosen["image_path"] = [by_id.loc[i, "image_path"] for i in chosen["line_id"]]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    counts.to_csv(OUTPUT / "points_par_manuscrit.csv", index=False, lineterminator="\n")
    chosen.to_csv(OUTPUT / "echantillon.csv", index=False, lineterminator="\n")
    template = OUTPUT / "jugements.csv"
    if not template.exists():  # ne jamais écraser des réponses déjà déposées
        pd.DataFrame({"identifiant": chosen["identifiant"], "réponse": "", "commentaire": ""}).to_csv(
            template, index=False, lineterminator="\n")
    write_page(items, PAGE)
    print(counts.to_string(index=False))
    print(chosen.groupby("doc_id").size().to_string())
    print(f"-> {OUTPUT.relative_to(ROOT)} ; page : {PAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
