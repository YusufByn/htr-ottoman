"""Tests de htr_ottoman.analysis.final_ya (F13, Q4, avant la lecture), sans modèle."""
import html
import re
import subprocess
import sys

import pandas as pd
import pytest
from PIL import Image, ImageDraw

from htr_ottoman.analysis.final_ya import (ALLOCATION, HEADER, OUTPUT, PAGE, PREDICTIONS, QUESTION, doc_lines,
                                           outcomes, population, sample, word_bounds, word_finals, word_span)
from htr_ottoman.config import MAKHZAN_LINES

data_available = pytest.mark.skipif(not MAKHZAN_LINES.exists() or not (PREDICTIONS / "lignes.parquet").exists(),
                                    reason="table des lignes ou prédictions sauvegardées absentes")


def test_never_loads_a_model():
    code = "import sys, htr_ottoman.analysis.final_ya; print('htr_ottoman.predict' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "False"


def test_word_finals():
    text = "بي بىِ بيت بئ ي."  # fin de mot, fin avec kasra, milieu, ئ exclu, avant « . »
    assert word_finals(text) == [1, 4, 15]


def test_outcomes():
    assert outcomes("بي بى بى", "بي بي ب") == [
        {"index_caractere": 1, "lettre": "ي", "issue": "correct"},
        {"index_caractere": 4, "lettre": "ى", "issue": "confondu"},
        {"index_caractere": 7, "lettre": "ى", "issue": "autre"},
    ]


def test_word_bounds():
    assert word_bounds("اب جديِ ه", 5) == (3, 7)


def test_word_span_follows_ink():
    page = Image.new("L", (1000, 100), 255)
    draw = ImageDraw.Draw(page)
    draw.rectangle((600, 40, 950, 60), fill=0)  # premier mot, à droite
    draw.rectangle((50, 40, 400, 60), fill=0)  # second mot, à gauche
    polygon = [(0, 0), (1000, 0), (1000, 100), (0, 100)]
    x0, x1 = word_span(page, polygon, "بببي بببي", 3)
    assert 590 <= x0 <= 610 and x1 >= 940  # le blanc entre les mots n'est pas compté


@data_available
def test_sample_and_page():
    pop = population(doc_lines())
    kept = pop[pop["issue"] != "autre"]
    assert len(pop) == 315 and len(kept) == 280
    chosen = sample(pop)
    assert chosen.equals(sample(pop)) and len(chosen) == sum(ALLOCATION.values()) == 40
    sizes = chosen.groupby("case")["taille_case"].first().to_dict()
    assert sorted(sizes.values()) == [2, 82, 84, 112]
    assert ((chosen["poids"] * chosen["n_case"]).round(9) == chosen["taille_case"]).all()
    assert not chosen.duplicated(["line_id", "index_caractere"]).any()
    if PAGE.exists():
        page = PAGE.read_text(encoding="utf-8")
        assert len(re.findall(r'<section class="item"', page)) == 40
        assert page.count(html.escape(QUESTION)) == 40
        assert not re.search(r"[؀-ۿ]", page)  # ni transcription ni lettre attendue
        assert "confondu" not in page and "poids" not in page and "correct" not in page
        saved = pd.read_csv(OUTPUT / "echantillon.csv")
        assert saved["identifiant"].tolist() == chosen["identifiant"].tolist()
        template = pd.read_csv(OUTPUT / "jugements.csv")
        assert template.columns.tolist() == list(HEADER)
        assert template["identifiant"].tolist() == chosen["identifiant"].tolist()
