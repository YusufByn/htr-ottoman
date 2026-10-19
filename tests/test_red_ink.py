"""Tests de htr_ottoman.analysis.red_ink (F13, Q3, avant la lecture), sans modèle ni prédiction."""
import html
import inspect
import re
import subprocess
import sys

import pandas as pd
import pytest
from PIL import Image, ImageDraw

import htr_ottoman.analysis.red_ink as red_ink
from htr_ottoman.analysis.red_ink import (COLOR_QUESTION, GRAY_QUESTION, HEADER, HEIGHT, OUTPUT, PAD, PAGE,
                                          doc_lines, ink_span, letter_weight, model_view, sample)
from htr_ottoman.config import MAKHZAN_LINES

data_available = pytest.mark.skipif(not MAKHZAN_LINES.exists(), reason="table des lignes absente")


def test_never_reads_predictions():
    code = "import sys, htr_ottoman.analysis.red_ink; print('htr_ottoman.predict' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "False"
    source = inspect.getsource(red_ink)
    assert "lignes.parquet" not in source and "hyp_norm" not in source


def test_model_view_height_padding_and_gray():
    image = Image.new("RGB", (300, 60), "white")
    ImageDraw.Draw(image).rectangle((100, 20, 200, 40), fill="black")
    view = model_view(image)
    assert view.mode == "L" and view.height == HEIGHT and view.width == 600 + 2 * PAD  # 300 × 120 / 60
    assert view.getpixel((PAD // 2, 60)) == 255 and view.getpixel((PAD + 300, 60)) < 50  # marge blanche, encre noire


def test_letter_weights():
    assert [letter_weight(c) for c in "ب .\u0653"] == [1, 0, 0, 0]


def test_ink_span_covers_the_gap_between_columns():
    page = Image.new("L", (1000, 100), 255)
    draw = ImageDraw.Draw(page)
    draw.rectangle((550, 40, 950, 60), fill=0)  # premier hémistiche, à droite
    draw.rectangle((50, 40, 450, 60), fill=0)  # second hémistiche, à gauche
    polygon = [(0, 0), (1000, 0), (1000, 100), (0, 100)]
    text = "ببببب . ببببب"  # le « . » sépare deux moitiés d'encre égale
    x0, x1 = ink_span(page, polygon, text, text.index("."))
    assert x0 <= 450 and x1 >= 550  # le blanc entre les colonnes est couvert en entier


@data_available
def test_sample_and_page():
    lines = doc_lines()
    chosen = sample(lines)
    assert chosen.equals(sample(lines)) and len(chosen) == 40 and set(chosen["doc_id"]) == {2937}
    texts = lines.set_index("line_id")["norm"]
    assert sum(t.count(".") for t in texts) == 86
    assert all(texts[r.line_id][r.index_caractere] == "." for r in chosen.itertuples())
    if PAGE.exists():
        page = PAGE.read_text(encoding="utf-8")
        assert len(re.findall(r'<section class="item"', page)) == 40
        assert page.count(html.escape(GRAY_QUESTION)) == 40 and page.count(html.escape(COLOR_QUESTION)) == 40
        assert len(re.findall(r"<img ", page)) == 40  # images en couleur absentes du HTML avant le clic
        assert not any(t in page for t in texts[chosen["line_id"]])  # aucune transcription
        saved = pd.read_csv(OUTPUT / "echantillon.csv")
        assert saved["identifiant"].tolist() == chosen["identifiant"].tolist()
        template = pd.read_csv(OUTPUT / "jugements.csv")
        assert template.columns.tolist() == list(HEADER)
        assert template["identifiant"].tolist() == chosen["identifiant"].tolist()
