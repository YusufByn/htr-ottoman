"""F13, Q3 : encre rouge en niveaux de gris, partie avant la lecture de l'utilisateur.

Dans Doc 2937 (validation), le séparateur d'hémistiche est un point rouge (•,
ramené à « . », décision 21). Le modèle reçoit la ligne en niveaux de gris : ce
module prépare une lecture à l'aveugle en deux temps, pour savoir si ce point
reste visible une fois converti.

- Échantillon : N_SAMPLE « . » tirés parmi ceux de Doc 2937 dans la validation
  compilée (seed `splits.SEED`), ordre mélangé ; une entrée par « . » (deux « . »
  d'une même ligne donnent deux entrées) -> echantillon.csv.
- Étape gris : l'image de la ligne prise dans val.arrow (même découpe que pour le
  modèle) passée par `ImageInputTransforms` de kraken avec les réglages de
  l'entraînement (1 canal, hauteur 120, marge de 16 px, sans normalisation de la
  ligne de base) ; seule l'inversion finale des valeurs est annulée pour l'affichage.
- Étape couleur : la même ligne dans l'image de la page d'origine, en couleur.
- Boîte large, à la même place dans les deux images. Les lignes de Doc 2937 sont
  des vers sur deux colonnes : une estimation proportionnelle à la largeur placerait
  mal le « . » de fin de premier hémistiche, juste avant le blanc entre les colonnes.
  L'emplacement est donc estimé d'après l'encre : profil des pixels sombres dans le
  polygone de la ligne, sur la page, cumulé de droite à gauche ; chaque lettre pèse 1,
  espaces, « . » et signes combinants 0 ; la boîte couvre la zone où l'encre cumulée
  est à BOX_LETTERS lettres au plus de la part du texte qui précède le « . » (un blanc
  y est donc couvert en entier), et au moins BOX_MIN_FRAC de la largeur de chaque
  côté. Elle est reportée sur l'image en gris en proportion de la largeur du
  polygone (la ligne compilée en couvre toute la largeur).
- Page HTML autonome : aucune prédiction, aucune transcription. Réponse en gris
  (visible / à peine visible / invisible / incertain), puis seulement alors un bouton
  « afficher la couleur » ; la réponse en gris est alors verrouillée ; réponse en
  couleur (oui / non / incertain) ; un commentaire. Réponses gardées dans le
  navigateur (localStorage), téléchargées en CSV.
- jugements.csv : gabarit versionné, remplacé par le CSV téléchargé.

Sorties : reports/f13/q3_encre_rouge/.

Usage : uv run python -m htr_ottoman.analysis.red_ink
"""
import html
import io
import json
import unicodedata

import numpy as np
import pandas as pd
import pyarrow as pa
from PIL import Image, ImageDraw

from htr_ottoman.analysis.period_ink import data_uri, line_geometry, relative_position
from htr_ottoman.config import MAKHZAN_PROCESSED, REPORTS, ROOT
from htr_ottoman.prepare import select_lines
from htr_ottoman.splits import SEED

PERIOD = "."
DOC = 2937
SPLIT = "val"
N_SAMPLE = 40
HEIGHT, CHANNELS, PAD = 120, 1, 16  # entrée du modèle de départ et --pad 16 de l'entraînement (décision 34)
BOX_LETTERS, BOX_MIN_FRAC = 2.0, 0.04  # boîte large : 2 lettres de part et d'autre, au moins 4 % de chaque côté
INK_THRESHOLD = 0.25  # pixel compté comme encre : plus sombre que le papier de 25 % de l'écart maximal
BOX_COLOR_RGB = (0, 90, 255)
MARGIN = (30, 20)
MAX_WIDTH = 1100
GRAY_ANSWERS = ("visible", "à peine visible", "invisible", "incertain")
COLOR_ANSWERS = ("oui", "non", "incertain")
GRAY_QUESTION = "Vois-tu un point de séparation dans la boîte ou à son bord ?"
COLOR_QUESTION = "Y a-t-il un point de séparation en couleur ?"
CRITERIA = ("Un point de séparation est isolé, entre deux mots, hors points des lettres.",
            "Point juste hors de la boîte : répondre incertain, avec le commentaire « boîte décalée ».")
HEADER = ("identifiant", "réponse gris", "réponse couleur", "commentaire")
OUTPUT = REPORTS / "f13" / "q3_encre_rouge"
PAGE = OUTPUT / "lecture_a_l_aveugle.html"
STORAGE_KEY = "htr_f13_q3_encre_rouge_v1"


def doc_lines() -> pd.DataFrame:
    lines = select_lines()
    return lines[(lines["split"] == SPLIT) & lines["exclusion"].isna() & (lines["doc_id"] == DOC)].copy()


def sample(lines: pd.DataFrame) -> pd.DataFrame:
    occ = [{"doc_id": l.doc_id, "part_id": l.part_id, "line_id": l.line_id, "rang_point": k + 1, "index_caractere": i}
           for l in lines.itertuples() for k, i in enumerate(i for i, c in enumerate(l.norm) if c == PERIOD)]
    occ = pd.DataFrame(occ)
    rng = np.random.default_rng(SEED)
    chosen = occ.iloc[np.sort(rng.choice(len(occ), size=N_SAMPLE, replace=False))]
    chosen = chosen.iloc[rng.permutation(len(chosen))].reset_index(drop=True)
    chosen.insert(0, "identifiant", [f"q3_{i + 1:02d}" for i in range(len(chosen))])
    return chosen


def compiled_images() -> dict[str, Image.Image]:
    """Images de val.arrow par texte normalisé (chaque texte doit être unique)."""
    with pa.memory_map(str(MAKHZAN_PROCESSED / f"{SPLIT}.arrow")) as source:
        records = pa.ipc.open_file(source).read_all().column("lines").to_pylist()
    texts = [r["text"] for r in records]
    if len(set(texts)) != len(texts):
        raise ValueError(f"{SPLIT}.arrow : textes en double, images non attribuables")
    return {r["text"]: Image.open(io.BytesIO(r["im"])) for r in records}


def model_view(image: Image.Image) -> Image.Image:
    """Ligne telle que le modèle la reçoit (transformations de kraken), inversion annulée pour l'affichage."""
    from kraken.lib.dataset import ImageInputTransforms

    tensor = ImageInputTransforms(1, HEIGHT, 0, CHANNELS, (PAD, 0), valid_norm=False)(image)
    array = ((1 - tensor[0].numpy()) * 255).round().astype(np.uint8)
    return Image.fromarray(array, mode="L")


def letter_weight(c: str) -> int:
    return 0 if c in " " + PERIOD or unicodedata.combining(c) else 1


def ink_span(page: Image.Image, polygon: list, text: str, index: int) -> tuple[int, int]:
    """Bornes horizontales (pixels de la page) de la boîte autour du « . » d'index `index`, d'après l'encre."""
    mask = Image.new("L", page.size, 0)
    ImageDraw.Draw(mask).polygon(polygon, fill=255)
    xs = [x for x, _ in polygon]
    left, right = min(xs), max(xs)
    gray = np.asarray(page.convert("L"), dtype=float)[:, left:right + 1]
    inside = np.asarray(mask)[:, left:right + 1] > 0
    paper = np.median(gray[inside])
    dark = np.clip(paper - gray, 0, None) * inside
    dark[dark < INK_THRESHOLD * dark.max()] = 0
    cumulative = np.cumsum(dark.sum(axis=0)[::-1])  # de droite à gauche
    cumulative /= cumulative[-1]
    weights = [letter_weight(c) for c in text]
    share = sum(weights[:index]) / sum(weights)
    near = np.nonzero(np.abs(cumulative - share) <= BOX_LETTERS / sum(weights))[0]
    lo, hi = (near.min(), near.max()) if len(near) else (int(np.searchsorted(cumulative, share)),) * 2
    xa, xb = right - hi, right - lo
    center, half = (xa + xb) / 2, BOX_MIN_FRAC * (right - left)
    return int(min(xa, center - half)), int(max(xb, center + half))


def gray_with_box(image: Image.Image, polygon: list, page_span: tuple[int, int]) -> tuple[Image.Image, tuple]:
    view = model_view(image)
    xs = [x for x, _ in polygon]
    left, right = min(xs), max(xs)
    scale = (view.width - 2 * PAD) / (right - left)
    x0, x1 = (PAD + (x - left) * scale for x in page_span)
    box = (max(0, int(x0)), 0, min(view.width - 1, int(x1)), view.height - 1)
    framed = view.convert("RGB")
    ImageDraw.Draw(framed).rectangle(box, outline=BOX_COLOR_RGB, width=3)
    return framed, box


def color_with_box(page: Image.Image, polygon: list, page_span: tuple[int, int]) -> tuple[Image.Image, tuple]:
    page = page.convert("RGB")
    xs, ys = [x for x, _ in polygon], [y for _, y in polygon]
    x0, x1 = page_span
    box = (x0, min(ys), x1, max(ys))
    cx0, cy0 = max(0, min(xs + [x0]) - MARGIN[0]), max(0, min(ys) - MARGIN[1])
    cx1, cy1 = min(page.width, max(xs + [x1]) + MARGIN[0]), min(page.height, max(ys) + MARGIN[1])
    crop = page.crop((cx0, cy0, cx1, cy1))
    ImageDraw.Draw(crop).rectangle((x0 - cx0, box[1] - cy0, x1 - cx0, box[3] - cy0), outline=BOX_COLOR_RGB, width=3)
    if crop.width > MAX_WIDTH:
        crop = crop.resize((MAX_WIDTH, round(crop.height * MAX_WIDTH / crop.width)))
    return crop, box


def png_uri(image: Image.Image) -> str:
    import base64
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")  # sans perte : le gris est montré tel qu'il est
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


PAGE_HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F13 Q3 : lecture à l'aveugle</title>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 0 auto; max-width: 1180px; padding: 16px;
         background: #fafafa; color: #1a1a1a; line-height: 1.45; }
  header { position: sticky; top: 0; background: #fafafa; padding: 8px 0; border-bottom: 1px solid #ccc; z-index: 1; }
  .item { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 12px; margin: 16px 0; }
  .item.done { border-color: #7a7; }
  img { max-width: 100%; height: auto; display: block; margin: 8px 0; }
  img.gray { image-rendering: auto; }
  .question { font-weight: 600; margin-top: 8px; }
  label { margin-right: 18px; cursor: pointer; }
  textarea { width: 100%; min-height: 2.4em; margin-top: 6px; font: inherit; }
  button { font: inherit; padding: 6px 14px; cursor: pointer; }
  button:disabled { cursor: not-allowed; }
  .color { display: none; border-top: 1px dashed #bbb; margin-top: 10px; padding-top: 6px; }
  .note { color: #555; font-size: 0.92em; }
</style>
</head>
<body>
"""

PAGE_SCRIPT = """<script>
const KEY = __KEY__;
const IDS = __IDS__;
const COLOR = __COLOR__;
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { state = {}; }
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
function get(id) { return state[id] || (state[id] = {}); }
function show(id) {
  const s = get(id), item = document.getElementById(id);
  for (const input of item.querySelectorAll('input[data-step="gris"]')) { input.checked = input.value === s.gris; input.disabled = !!s.couleur_affichee; }
  for (const input of item.querySelectorAll('input[data-step="couleur"]')) input.checked = input.value === s.couleur;
  const button = document.getElementById(id + "_bouton");
  button.disabled = !s.gris || !!s.couleur_affichee;
  const box = document.getElementById(id + "_couleur");
  if (s.couleur_affichee) {
    if (!box.querySelector("img")) {
      const img = document.createElement("img");
      img.src = COLOR[id]; img.alt = "ligne " + id + " en couleur, emplacement estimé encadré";
      box.insertBefore(img, box.firstChild);
    }
    box.style.display = "block";
  }
  item.classList.toggle("done", !!(s.gris && s.couleur));
}
function refresh() {
  let g = 0, c = 0;
  for (const id of IDS) { const s = get(id); if (s.gris) g++; if (s.couleur) c++; }
  document.getElementById("progress").textContent = "gris : " + g + " / " + IDS.length + " · couleur : " + c + " / " + IDS.length;
}
for (const id of IDS) {
  const item = document.getElementById(id);
  for (const input of item.querySelectorAll('input[data-step="gris"]')) input.addEventListener("change", () => {
    if (get(id).couleur_affichee) return;
    get(id).gris = input.value; save(); show(id); refresh();
  });
  for (const input of item.querySelectorAll('input[data-step="couleur"]')) input.addEventListener("change", () => {
    get(id).couleur = input.value; save(); show(id); refresh();
  });
  document.getElementById(id + "_bouton").addEventListener("click", () => {
    if (!get(id).gris) return;
    get(id).couleur_affichee = true; save(); show(id); refresh();
  });
  const area = document.getElementById(id + "_commentaire");
  area.value = get(id).commentaire || "";
  area.addEventListener("input", () => { get(id).commentaire = area.value; save(); });
  show(id);
}
function cell(v) { v = v || ""; return /[",\\n\\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
document.getElementById("download").addEventListener("click", () => {
  const rows = [__HEADER__];
  for (const id of IDS) { const s = get(id); rows.push([id, s.gris || "", s.couleur || "", s.commentaire || ""].map(cell).join(",")); }
  const blob = new Blob([rows.join("\\n") + "\\n"], {type: "text/csv;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "jugements.csv"; a.click();
  URL.revokeObjectURL(a.href);
});
refresh();
</script>
"""


def radios(name: str, step: str, answers: tuple) -> str:
    return "".join(f"<label><input type=\"radio\" name=\"{name}_{step}\" data-step=\"{step}\" value=\"{html.escape(a)}\"> "
                   f"{html.escape(a)}</label>" for a in answers)


def write_page(items: list[dict]) -> None:
    parts = [PAGE_HEAD,
             "<header><h1>F13, Q3 : encre rouge en niveaux de gris (lecture à l'aveugle)</h1>",
             "<p><span id=\"progress\"></span> · <button id=\"download\">Télécharger mes réponses (CSV)</button></p></header>",
             "<ul class=\"consignes\">" + "".join(f"<li><b>{html.escape(c)}</b></li>" for c in CRITERIA) + "</ul>",
             "<p class=\"note\">Pour chaque entrée : d'abord la ligne telle que le modèle la reçoit (niveaux de gris, "
             "hauteur 120 px), avec une boîte large autour de l'emplacement <b>estimé</b> d'un point de séparation. "
             "Après ta réponse seulement, le bouton « afficher la couleur » montre la même ligne en couleur, même boîte ; "
             "ta réponse en gris est alors verrouillée. Aucune prédiction ni transcription n'est affichée. Les réponses "
             "sont gardées dans ce navigateur, même après un rechargement de la page.</p>"]
    for item in items:
        i = item["identifiant"]
        parts.append(
            f"<section class=\"item\" id=\"{i}\"><h2>{i}</h2>"
            f"<img class=\"gray\" src=\"{item['gray']}\" alt=\"ligne {i} en niveaux de gris, emplacement estimé encadré\">"
            f"<p class=\"question\">{html.escape(GRAY_QUESTION)}</p><p>{radios(i, 'gris', GRAY_ANSWERS)}</p>"
            f"<p><button id=\"{i}_bouton\" disabled>afficher la couleur</button></p>"
            f"<div class=\"color\" id=\"{i}_couleur\"><p class=\"question\">{html.escape(COLOR_QUESTION)}</p>"
            f"<p>{radios(i, 'couleur', COLOR_ANSWERS)}</p></div>"
            f"<textarea id=\"{i}_commentaire\" placeholder=\"Commentaire (facultatif)\"></textarea></section>")
    ids = [item["identifiant"] for item in items]
    script = (PAGE_SCRIPT.replace("__KEY__", json.dumps(STORAGE_KEY)).replace("__IDS__", json.dumps(ids))
              .replace("__COLOR__", json.dumps({item["identifiant"]: item["color"] for item in items}))
              .replace("__HEADER__", json.dumps(",".join(HEADER), ensure_ascii=False)))
    parts += [script, "</body>\n</html>\n"]
    PAGE.write_text("".join(parts), encoding="utf-8")


def main() -> None:
    lines = doc_lines()
    chosen = sample(lines)
    images = compiled_images()
    by_id = lines.set_index("line_id")
    items, gray_boxes, color_boxes, positions = [], [], [], []
    for row in chosen.itertuples():
        line = by_id.loc[row.line_id]
        text, index = line["norm"], row.index_caractere
        _, polygon = line_geometry(line["alto_path"], row.line_id)
        page = Image.open(ROOT / line["image_path"])
        page_span = ink_span(page, polygon, text, index)
        gray, gray_box = gray_with_box(images[text], polygon, page_span)
        color, color_box = color_with_box(page, polygon, page_span)
        items.append({"identifiant": row.identifiant, "gray": png_uri(gray), "color": data_uri(color)})
        gray_boxes.append(" ".join(map(str, gray_box)))
        color_boxes.append(" ".join(map(str, color_box)))
        positions.append(round(relative_position(text, index), 4))
    chosen["position_relative"] = positions
    chosen["boite_gris"] = gray_boxes
    chosen["boite_couleur"] = color_boxes
    chosen["image_path"] = [by_id.loc[i, "image_path"] for i in chosen["line_id"]]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    chosen.to_csv(OUTPUT / "echantillon.csv", index=False, lineterminator="\n")
    template = OUTPUT / "jugements.csv"
    if not template.exists():  # ne jamais écraser des réponses déjà déposées
        pd.DataFrame({h: chosen["identifiant"] if h == HEADER[0] else "" for h in HEADER}).to_csv(
            template, index=False, lineterminator="\n")
    write_page(items)
    print(f"{len(chosen)} « . » tirés parmi {sum(t.count(PERIOD) for t in lines['norm'])} de Doc {DOC} "
          f"({chosen['line_id'].nunique()} lignes)")
    print(f"-> {OUTPUT.relative_to(ROOT)} ; page : {PAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
