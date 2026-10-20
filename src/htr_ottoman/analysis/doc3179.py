"""F13, Q6 : Doc 3179 (test interne), page de lecture à l'aveugle, avant la lecture.

Complément du 2026-10-20 à la décision 39 (98f8e89, précisé en d4b3280) : pour Q6
seulement, images des lignes gardées de Doc 3179 ; aucune prédiction nouvelle, aucun modèle chargé, `predict`
jamais appelé ; ni prédiction, ni erreur, ni CER affichés. Ce module ne lit aucune
prédiction : la table des lignes (vérité terrain et géométrie), le jeu compilé et les
images de MAKHZAN seulement ; `select_lines(with_codec=False)` évite de charger le modèle
de départ pour lire son codec (la règle « hors codec » ne vise que le train).

- Échantillon : Doc 3179 n'a que 13 lignes gardées (une page, aucune exclusion) ; le
  tirage de 30 prévu est impossible : toutes les lignes gardées sont prises (règle
  « toutes s'il y en a moins »), ordre mélangé avec la seed `splits.SEED`
  -> echantillon.csv (identifiants et position seulement).
- Image 1, comme en Q3 : la ligne du jeu compilé du test interne (anciens polygones,
  décision 36) passée par les transformations d'entrée de kraken (gris, hauteur 120,
  marge `pad` de configs/f8_finetune.yml) ; seule l'inversion est annulée pour
  l'affichage (`red_ink.model_view`).
- Image 2 : le même endroit dans l'image de la page, en couleur, avec une marge
  (horizontale MARGIN_X, verticale VERTICAL_MARGIN × hauteur du polygone) ; deux petits
  triangles dans la marge, à gauche et à droite, désignent la ligne, sans rien tracer
  sur l'écriture.
- Page HTML autonome : six questions (A à F) oui / non / incertain par ligne, un
  commentaire ; réponses gardées dans le navigateur (localStorage), CSV téléchargeable
  à tout moment. Aucun texte, aucune prédiction, aucun CER.
- jugements.csv : gabarit versionné, jamais écrasé.

Sorties : reports/f13/q6_doc3179/.

Usage : uv run python -m htr_ottoman.analysis.doc3179
"""
import html
import io
import json

import numpy as np
import pandas as pd
import pyarrow as pa
import yaml
from PIL import Image, ImageDraw

from htr_ottoman.analysis import red_ink
from htr_ottoman.analysis.period_ink import data_uri, line_geometry
from htr_ottoman.analysis.red_ink import model_view, png_uri
from htr_ottoman.config import MAKHZAN_PROCESSED, REPORTS, ROOT
from htr_ottoman.data.alto import read_alto
from htr_ottoman.prepare import processed_alto_path, select_lines
from htr_ottoman.splits import SEED

DOC = 3179
SPLIT = "test_interne"
N_SAMPLE = 30  # prévu par le plan ; toutes les lignes s'il y en a moins (13 dans Doc 3179, d4b3280)
CONFIG = ROOT / "configs" / "f8_finetune.yml"
MARGIN_X, VERTICAL_MARGIN, MIN_MARGIN_Y = 40, 0.6, 20
MAX_WIDTH = 1100
MARKER_COLOR = (0, 90, 255)
ANSWERS = ("oui", "non", "incertain")
QUESTIONS = {
    "A": "Image 1 : des lettres sont-elles coupées par le bord ou par une zone noire ?",
    "B": "Image 1 : voit-on des morceaux d'une autre ligne (au-dessus ou au-dessous) ?",
    "C": "Image 2 : y a-t-il de l'écriture au-dessus ou au-dessous de la ligne, plus petite ou entre les mots ?",
    "D": "Image 2 : une partie de l'écriture est-elle pâle, effacée, tachée, ou le verso transparaît-il ?",
    "E": "Image 2 : y a-t-il de l'encre rouge ou d'une autre couleur que noir ou brun ?",
    "F": "Image 2 : la ligne est-elle inclinée ou courbe, ou les mots montent-ils en escalier en fin de mot ?",
}
RULES = (
    "Réponses : oui / non / incertain ; « incertain » si hésitation. Un commentaire libre par ligne.",
    "Image 1 : la ligne telle que le modèle la voit (niveaux de gris, hauteur 120 px, marge de 16 px).",
    "Image 2 : le même endroit sur la page, en couleur, avec une marge ; la ligne est désignée par deux petits "
    "triangles bleus, à gauche et à droite, dans la marge.",
)
HEADER = ("identifiant", *QUESTIONS, "commentaire")
OUTPUT = REPORTS / "f13" / "q6_doc3179"
PAGE = OUTPUT / "lecture_a_l_aveugle.html"
STORAGE_KEY = "htr_f13_q6_doc3179_v1"


def check_settings() -> None:
    """Réglages de l'image 1 tirés de la config de l'entraînement (aucun modèle chargé)."""
    pad = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["train"]["pad"]
    if pad != red_ink.PAD:
        raise ValueError(f"{CONFIG.name} : pad {pad}, attendu {red_ink.PAD} (image 1 comme en Q3)")


def doc_lines() -> pd.DataFrame:
    lines = select_lines(with_codec=False)  # sans charger le modèle de départ
    return lines[(lines["split"] == SPLIT) & lines["exclusion"].isna() & (lines["doc_id"] == DOC)].copy()


def sample(lines: pd.DataFrame) -> pd.DataFrame:
    lines = lines.sort_values(["part_id", "line_index"]).reset_index(drop=True)
    rng = np.random.default_rng(SEED)
    n = min(N_SAMPLE, len(lines))
    chosen = lines.iloc[np.sort(rng.choice(len(lines), size=n, replace=False))]
    chosen = chosen.iloc[rng.permutation(n)].reset_index(drop=True)
    chosen = chosen[["doc_id", "part_id", "line_index", "line_id"]].copy()
    chosen.insert(0, "identifiant", [f"q6_{i + 1:02d}" for i in range(n)])
    return chosen


def compiled_images(line_ids: set[str]) -> dict[str, Image.Image]:
    """Images du jeu compilé du test interne, par identifiant de ligne.

    Le jeu compilé n'a pas d'identifiant de ligne, et deux lignes peuvent avoir la même
    vérité terrain (une ligne de Doc 3179 et une de Doc 3184). L'ordre de compilation est
    fixe (`prepare.main` : pages triées par part_id, lignes dans l'ordre des ALTO
    normalisés, num_workers=0) : il est reconstruit, puis vérifié texte par texte sur
    tout le jeu avant d'attribuer les images par position."""
    lines = select_lines(with_codec=False)  # sans charger le modèle de départ
    kept = lines[(lines["split"] == SPLIT) & lines["exclusion"].isna()]
    order = []
    for _, g in kept.groupby("part_id", sort=True):
        first = g.iloc[0]
        order += [l.line_id for l in read_alto(processed_alto_path(first["doc_id"], first["alto_path"]).read_bytes()).lines]
    with pa.memory_map(str(MAKHZAN_PROCESSED / f"{SPLIT}.arrow")) as source:
        records = pa.ipc.open_file(source).read_all().column("lines").to_pylist()
    if [r["text"] for r in records] != kept.set_index("line_id").loc[order, "norm"].tolist():
        raise ValueError(f"{SPLIT}.arrow : ordre des lignes différent de celui de la compilation")
    return {i: Image.open(io.BytesIO(r["im"])) for i, r in zip(order, records) if i in line_ids}


def color_view(page: Image.Image, polygon: list) -> Image.Image:
    """Le même endroit en couleur, avec une marge ; la ligne désignée par deux triangles dans la marge."""
    xs, ys = [x for x, _ in polygon], [y for _, y in polygon]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    my = max(MIN_MARGIN_Y, round(VERTICAL_MARGIN * (y1 - y0)))
    cx0, cy0 = max(0, x0 - MARGIN_X), max(0, y0 - my)
    cx1, cy1 = min(page.width, x1 + MARGIN_X), min(page.height, y1 + my)
    crop = page.convert("RGB").crop((cx0, cy0, cx1, cy1))
    draw, mid, size = ImageDraw.Draw(crop), (y0 + y1) / 2 - cy0, 10
    left, right = x0 - cx0, x1 - cx0
    draw.polygon([(left - 4, mid), (left - 4 - size, mid - size / 2), (left - 4 - size, mid + size / 2)],
                 fill=MARKER_COLOR)
    draw.polygon([(right + 4, mid), (right + 4 + size, mid - size / 2), (right + 4 + size, mid + size / 2)],
                 fill=MARKER_COLOR)
    if crop.width > MAX_WIDTH:
        crop = crop.resize((MAX_WIDTH, round(crop.height * MAX_WIDTH / crop.width)))
    return crop


PAGE_HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F13 Q6 : lecture à l'aveugle</title>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 0 auto; max-width: 1180px; padding: 16px;
         background: #fafafa; color: #1a1a1a; line-height: 1.45; }
  header { position: sticky; top: 0; background: #fafafa; padding: 8px 0; border-bottom: 1px solid #ccc; z-index: 1; }
  .item { background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 12px; margin: 16px 0; }
  .item.done { border-color: #7a7; }
  img { max-width: 100%; height: auto; display: block; margin: 8px 0; }
  .label { color: #555; font-size: 0.9em; margin-top: 10px; }
  .q { margin: 6px 0; } .q b { display: inline-block; min-width: 1.5em; }
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
const QUESTIONS = __QUESTIONS__;
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { state = {}; }
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
function get(id) { return state[id] || (state[id] = {}); }
function complete(id) { const s = state[id] || {}; return QUESTIONS.every(q => s[q]); }
function refresh() {
  let n = 0, a = 0;
  for (const id of IDS) {
    const s = state[id] || {};
    a += QUESTIONS.filter(q => s[q]).length;
    if (complete(id)) n++;
    document.getElementById(id).classList.toggle("done", complete(id));
  }
  document.getElementById("progress").textContent = n + " / " + IDS.length + " lignes complètes (" + a + " / " + (IDS.length * QUESTIONS.length) + " réponses)";
}
for (const id of IDS) {
  for (const q of QUESTIONS) {
    for (const input of document.querySelectorAll('input[name="' + id + '_' + q + '"]')) {
      input.checked = input.value === (state[id] || {})[q];
      input.addEventListener("change", () => { get(id)[q] = input.value; save(); refresh(); });
    }
  }
  const area = document.getElementById(id + "_commentaire");
  area.value = (state[id] || {}).commentaire || "";
  area.addEventListener("input", () => { get(id).commentaire = area.value; save(); });
}
function cell(v) { v = v || ""; return /[",\\n\\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
function csv() {
  const rows = [__HEADER__];
  for (const id of IDS) { const s = state[id] || {}; rows.push([id, ...QUESTIONS.map(q => s[q] || ""), s.commentaire || ""].map(cell).join(",")); }
  return rows.join("\\n") + "\\n";
}
document.getElementById("download").addEventListener("click", () => {
  const blob = new Blob([csv()], {type: "text/csv;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "jugements.csv"; a.click();
  URL.revokeObjectURL(a.href);
});
refresh();
</script>
"""


def write_page(items: list[dict]) -> None:
    parts = [PAGE_HEAD,
             "<header><h1>F13, Q6 : Doc 3179 (lecture à l'aveugle)</h1>",
             "<p><span id=\"progress\"></span> · <button id=\"download\">Télécharger mes réponses (CSV)</button> "
             "<span class=\"note\">(à tout moment : à mi-parcours et à la fin)</span></p></header>",
             "<ul>" + "".join(f"<li>{html.escape(r)}</li>" for r in RULES) + "</ul>",
             "<ol type=\"A\">" + "".join(f"<li>{html.escape(q.split(' : ', 1)[1])} "
                                         f"<span class=\"note\">({html.escape(q.split(' : ', 1)[0])})</span></li>"
                                         for q in QUESTIONS.values()) + "</ol>",
             "<p class=\"note\">Aucun texte, aucune prédiction, aucun CER n'est affiché. Les réponses sont gardées "
             "dans ce navigateur, même après un rechargement de la page.</p>"]
    for item in items:
        i = item["identifiant"]
        questions = "".join(
            f"<div class=\"q\"><b>{k}.</b> {html.escape(text)}<br>"
            + "".join(f"<label><input type=\"radio\" name=\"{i}_{k}\" value=\"{a}\"> {a}</label>" for a in ANSWERS)
            + "</div>" for k, text in QUESTIONS.items())
        parts.append(
            f"<section class=\"item\" id=\"{i}\"><h2>{i}</h2>"
            f"<p class=\"label\">Image 1 : la ligne telle que le modèle la voit</p>"
            f"<img src=\"{item['gray']}\" alt=\"ligne {i}, vue par le modèle\">"
            f"<p class=\"label\">Image 2 : le même endroit en couleur, avec une marge</p>"
            f"<img src=\"{item['color']}\" alt=\"ligne {i}, en couleur avec une marge\">"
            f"{questions}"
            f"<textarea id=\"{i}_commentaire\" placeholder=\"Commentaire (facultatif)\"></textarea></section>")
    ids = [item["identifiant"] for item in items]
    script = (PAGE_SCRIPT.replace("__KEY__", json.dumps(STORAGE_KEY)).replace("__IDS__", json.dumps(ids))
              .replace("__QUESTIONS__", json.dumps(list(QUESTIONS)))
              .replace("__HEADER__", json.dumps(",".join(HEADER), ensure_ascii=False)))
    parts += [script, "</body>\n</html>\n"]
    PAGE.write_text("".join(parts), encoding="utf-8")


def main() -> None:
    check_settings()
    lines = doc_lines()
    chosen = sample(lines)
    by_id = lines.set_index("line_id")
    images = compiled_images(set(chosen["line_id"]))
    items = []
    for row in chosen.itertuples():
        line = by_id.loc[row.line_id]
        _, polygon = line_geometry(line["alto_path"], row.line_id)
        page = Image.open(ROOT / line["image_path"])
        items.append({"identifiant": row.identifiant, "gray": png_uri(model_view(images[row.line_id])),
                      "color": data_uri(color_view(page, polygon))})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    chosen.to_csv(OUTPUT / "echantillon.csv", index=False, lineterminator="\n")
    template = OUTPUT / "jugements.csv"
    if not template.exists():  # ne jamais écraser des réponses déjà déposées
        pd.DataFrame({h: chosen["identifiant"] if h == HEADER[0] else "" for h in HEADER}).to_csv(
            template, index=False, lineterminator="\n")
    write_page(items)
    print(f"{len(chosen)} lignes prises parmi {len(lines)} lignes gardées de Doc {DOC}")
    print(f"-> {OUTPUT.relative_to(ROOT)} ; page : {PAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
