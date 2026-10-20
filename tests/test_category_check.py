"""Tests de htr_ottoman.analysis.category_check (F13, Q1, avant la lecture), sans modèle ni prédiction."""
import re
import subprocess
import sys

import pandas as pd
import pytest

from htr_ottoman.analysis.category_check import (HEADER, N_PER_CATEGORY, OUTPUT, PAGE, QUESTIONS, cell, grid, load,
                                                 sample, segment, window, with_marks)
from htr_ottoman.analysis.error_analysis import CATEGORIES, EXPLORATORY_INPUTS, MENTION

f9_available = pytest.mark.skipif(not all((d / "lignes.parquet").exists() for d in EXPLORATORY_INPUTS),
                                  reason="prédictions sauvegardées de F9 absentes")


def test_never_loads_a_model():
    code = ("import sys, htr_ottoman.analysis.category_check; "
            "print([m for m in ('htr_ottoman.predict', 'kraken', 'torch') if m in sys.modules])")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"


def test_cells_and_window():
    assert [cell(c) for c in ("ب", " ", "", "ِ")] == ["ب", "␣", "∅", "◌ِ"]
    pairs = [("ا", "ا"), ("ب", "ت"), (" ", ""), ("ج", "ج"), ("د", "د")]
    assert window(pairs, 2, context=1) == [("ب", "ت", "diff"), (" ", "", "err"), ("ج", "ج", "")]
    assert window(pairs, 0, context=1) == [("ا", "ا", "err"), ("ب", "ت", "diff")]  # coupé au bord de la ligne


def test_segment_keeps_mark_with_letter_and_grid_is_rtl():
    cells = [("ب", "ب", ""), ("ِ", "", "err"), ("ا", "ا", "")]
    assert segment(cells, 0) == "<mark class=\"err\">بِ</mark>ا"
    assert segment(cells, 1) == "با"
    table = grid(cells)
    assert 'dir="rtl"' in table and table.count("<tr>") == 2 and "∅" in table
    assert '<span class="mk">◌ِ</span>' in table  # ◌ affiché par une police qui l'a
    assert with_marks("x ◌ y") == 'x <span class="mk">◌</span> y'


@f9_available
def test_sample_and_page():
    lines, errors = load()
    assert len(errors) == sum(t["errors"].sum() for t in lines.values()) == 13440
    chosen = sample(errors)
    assert chosen.equals(sample(errors)) and len(chosen) == len(CATEGORIES) * N_PER_CATEGORY == 100
    assert chosen["categorie"].drop_duplicates().tolist() == CATEGORIES  # groupé dans l'ordre du plan
    assert (chosen.groupby("categorie")["identifiant"].size() == N_PER_CATEGORY).all()
    assert ((chosen["poids"] * chosen["n_categorie"]).round(9) == chosen["taille_categorie"]).all()
    assert (chosen["mention"] == MENTION).all()
    if PAGE.exists():
        page = PAGE.read_text(encoding="utf-8")
        assert len(re.findall(r'<section class="item"', page)) == 100
        assert "<img" not in page and "data:image" not in page  # aucune image du test interne
        assert not any(str(i) in page for i in chosen["line_id"].unique())  # ni identifiant de ligne
        assert "Doc " not in page and "doc_id" not in page  # ni manuscrit
        for cat, question in QUESTIONS.items():
            assert page.count(with_marks(question.replace("'", "&#x27;"))) == N_PER_CATEGORY + 1, cat
        saved = pd.read_csv(OUTPUT / "echantillon.csv")
        assert saved["identifiant"].tolist() == chosen["identifiant"].tolist()
        template = pd.read_csv(OUTPUT / "jugements.csv")
        assert template.columns.tolist() == list(HEADER)
        assert template["identifiant"].tolist() == chosen["identifiant"].tolist()
