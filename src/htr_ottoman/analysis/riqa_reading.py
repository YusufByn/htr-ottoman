"""RiqaTestset : page de lecture pour vérifier sur les images les crochets, parenthèses et `_`
de la vérité terrain (F15, point du pré-enregistrement, décision 46), sans aucune prédiction.

Une entrée par ligne et par famille de signes présente dans sa transcription : crochets ([ ou ]),
parenthèses (( ou )), trait bas (_). Question oui/non posée à l'utilisateur, critère écrit
ci-dessous avant tout affichage. La page montre l'image de la ligne seulement : ni transcription,
ni nombre d'occurrences, ni prédiction. Ordre des entrées mélangé (seed du projet).

Décision 46 : ni image ni transcription de RiqaTestset dans reports/ (dépôt public). La page,
qui contient les images, est donc écrite hors git (data/interim/riqa/lecture/) ; seuls des CSV
sans contenu sont versionnés dans reports/riqa/lecture/ : echantillon.csv (identifiant, ligne,
unité, famille, occurrences) et jugements.csv (modèle à remplir, jamais écrasé).

Usage : uv run python -I -m htr_ottoman.analysis.riqa_reading
"""
import html
import json

import pandas as pd
from PIL import Image

from htr_ottoman.analysis.final_ya import PAGE_HEAD, PAGE_SCRIPT
from htr_ottoman.analysis.period_ink import data_uri
from htr_ottoman.config import RIQA_INTERIM, RIQA_LINES, RIQA_REPORTS, ROOT
from htr_ottoman.splits import SEED

FAMILIES = {"crochets": "[]", "parentheses": "()", "trait_bas": "_"}
SHAPES = {"crochets": "[  ou  ]", "parentheses": "(  ou  )", "trait_bas": "_"}
NAMES = {"crochets": "crochet", "parentheses": "parenthèse", "trait_bas": "trait bas"}
QUESTION = "Voit-on un signe de cette forme dessiné sur l'image ?"
READING = "La ligne se lit de droite à gauche. Les images sont fournies binarisées (noir et blanc) par Osmanlica.com."
CRITERIA = (
    "Oui : au moins un signe de la forme indiquée est tracé à l'encre sur la ligne, à n'importe quel endroit et "
    "quelle que soit sa taille. Crochet : trait vertical avec deux retours horizontaux ; parenthèse : arc ouvert ; "
    "trait bas : trait horizontal isolé, posé sur ou sous la ligne d'écriture.",
    "Ne comptent pas : le trait d'allongement entre deux lettres, la barre d'une lettre (ك, ط...), un trait de "
    "rature, un trait collé au bord de l'image dû à la découpe.",
    "Non : aucun signe de cette forme sur l'image.",
    "En cas de doute : non, commentaire « doute ».",
    "Image vide, coupée ou illisible : non, commentaire « illisible ».",
)
ANSWERS = ("oui", "non")
HEADER = ("identifiant", "réponse", "commentaire")
OUTPUT = RIQA_REPORTS / "lecture"  # versionné : CSV sans contenu
PAGE = RIQA_INTERIM / "lecture" / "lecture.html"  # hors git : contient les images
STORAGE_KEY = "htr_f15_riqa_signes_v1"
EXTRA_STYLE = "<style>.scroll { overflow-x: auto; } .scroll img { max-width: none; } .forme { font-size: 1.6em; }</style>\n"


def items(lines: pd.DataFrame) -> pd.DataFrame:
    """Une entrée par (ligne, famille présente), ordre mélangé, identifiants riqa_01...."""
    rows = [
        {"line_id": r.line_id, "unite": r.unit, "famille": family,
         "occurrences": sum(r.text.count(c) for c in chars)}
        for r in lines.itertuples()
        for family, chars in FAMILIES.items()
        if any(c in r.text for c in chars)
    ]
    table = pd.DataFrame(rows).sample(frac=1, random_state=SEED).reset_index(drop=True)
    table.insert(0, "identifiant", [f"riqa_{i:02d}" for i in range(1, len(table) + 1)])
    return table


def write_page(table: pd.DataFrame, images: dict[str, str]) -> None:
    head = PAGE_HEAD.replace("<title>F13 Q4 : lecture à l'aveugle</title>",
                             "<title>RiqaTestset : signes sur l'image</title>")
    parts = [head.replace("</head>", EXTRA_STYLE + "</head>"),
             "<header><h1>RiqaTestset : crochets, parenthèses et trait bas sur l'image</h1>",
             "<p><span id=\"progress\"></span> · <button id=\"download\">Télécharger mes réponses (CSV)</button></p></header>",
             f"<p><b>{html.escape(READING)}</b></p>",
             "<ul class=\"consignes\">" + "".join(f"<li>{html.escape(c)}</li>" for c in CRITERIA) + "</ul>",
             "<p class=\"note\">Pour chaque entrée : l'image de la ligne à sa taille réelle (faire défiler si elle "
             "est large) et la forme cherchée. Aucune transcription ni prédiction n'est affichée. Les réponses sont "
             "gardées dans ce navigateur, même après un rechargement de la page. Page hors git (décision 46).</p>"]
    for row in table.itertuples():
        i = row.identifiant
        choices = "".join(f"<label><input type=\"radio\" name=\"{i}\" value=\"{a}\"> {a}</label>" for a in ANSWERS)
        parts.append(
            f"<section class=\"item\" id=\"{i}\"><h2>{i}</h2>"
            f"<div class=\"scroll\" dir=\"rtl\"><img src=\"{images[row.line_id]}\" alt=\"ligne {i}\"></div>"
            f"<p>Forme cherchée ({NAMES[row.famille]}) : <span class=\"forme\">{html.escape(SHAPES[row.famille])}</span></p>"
            f"<p class=\"question\">{html.escape(QUESTION)}</p><p>{choices}</p>"
            f"<textarea id=\"{i}_commentaire\" placeholder=\"Commentaire (facultatif)\"></textarea></section>")
    script = (PAGE_SCRIPT.replace("__KEY__", json.dumps(STORAGE_KEY))
              .replace("__IDS__", json.dumps(list(table["identifiant"])))
              .replace("__HEADER__", json.dumps(",".join(HEADER), ensure_ascii=False)))
    parts += [script, "</body>\n</html>\n"]
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text("".join(parts), encoding="utf-8")


def main() -> None:
    lines = pd.read_parquet(RIQA_LINES)
    table = items(lines)
    paths = lines.set_index("line_id")["image_path"]
    images = {}
    for line_id in table["line_id"].unique():
        with Image.open(ROOT / paths[line_id]) as im:
            images[line_id] = data_uri(im.convert("L"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT / "echantillon.csv", index=False, lineterminator="\n")
    template = OUTPUT / "jugements.csv"
    if not template.exists():  # ne jamais écraser des réponses déjà déposées
        pd.DataFrame({h: table["identifiant"] if h == HEADER[0] else "" for h in HEADER}).to_csv(
            template, index=False, lineterminator="\n")
    write_page(table, images)
    counts = table["famille"].value_counts().to_dict()
    print(f"{len(table)} entrées ({counts}), {table['line_id'].nunique()} lignes, {table['unite'].nunique()} unités")
    print(f"-> {OUTPUT.relative_to(ROOT)} (CSV) ; page hors git : {PAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
