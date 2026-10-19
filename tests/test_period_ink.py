"""Tests de htr_ottoman.analysis.period_ink (F13, Q5, avant la lecture), sans modèle ni prédiction."""
import html
import inspect
import re
import subprocess
import sys
import unicodedata

import pandas as pd
import pytest

import htr_ottoman.analysis.period_ink as period_ink
from htr_ottoman.analysis.period_ink import (OUTPUT, PAGE, QUESTION, allocation, count_table, estimated_box,
                                             marked_text, relative_position, sample, train_lines)
from htr_ottoman.config import MAKHZAN_LINES

data_available = pytest.mark.skipif(not MAKHZAN_LINES.exists(), reason="table des lignes absente")


def test_never_reads_predictions():
    code = "import sys, htr_ottoman.analysis.period_ink; print('htr_ottoman.predict' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "False"
    source = inspect.getsource(period_ink)
    assert "lignes.parquet" not in source and "predictions" not in source.replace("Aucune prédiction", "")


def test_allocation_small_docs_whole_rest_proportional():
    counts = pd.Series({82: 1, 131: 4, 2891: 44, 3262: 236, 3263: 44})
    assert allocation(counts) == {82: 1, 131: 4, 2891: 5, 3262: 25, 3263: 5}
    assert sum(allocation(counts, n=30).values()) == 30


def test_position_right_to_left_ignores_combining_marks():
    text = unicodedata.normalize("NFD", "آب . دار")  # آ = ا + signe combinant
    # 8 caractères de base : le signe combinant de آ ne compte pas
    assert relative_position(text, text.index(".")) == pytest.approx((3 + 0.5) / 8)
    baseline, polygon = [(100, 50), (900, 50)], [(100, 10), (900, 10), (900, 80), (100, 80)]
    x0, y0, x1, y1 = estimated_box(baseline, polygon, text, 0)
    assert x1 > 850 and (y0, y1) == (10, 80)  # début logique : à droite
    x0, _, x1, _ = estimated_box(baseline, polygon, text, len(text) - 1)
    assert x0 < 150  # fin logique : à gauche


def test_marked_text_escapes():
    assert marked_text("a<b . c", 4) == "a&lt;b <mark>.</mark> c"


@data_available
def test_counts_sample_and_page():
    lines = train_lines()
    counts = count_table(lines).set_index("doc_id")
    assert counts["points"].sum() == 329
    assert counts.loc[[82, 131, 2891, 3262, 3263], "points"].tolist() == [1, 4, 44, 236, 44]
    chosen = sample(lines)
    assert chosen.equals(sample(lines))  # seed fixe
    assert len(chosen) == 40 and chosen["doc_id"].value_counts().to_dict() == {3262: 25, 2891: 5, 3263: 5, 131: 4, 82: 1}
    texts = lines.set_index("line_id")["norm"]
    assert all(texts[r.line_id][r.index_caractere] == "." for r in chosen.itertuples())
    if PAGE.exists():
        page = PAGE.read_text(encoding="utf-8")
        assert len(re.findall(r'<section class="item"', page)) == 40 and page.count(html.escape(QUESTION)) == 40
        saved = pd.read_csv(OUTPUT / "echantillon.csv")
        assert saved["identifiant"].tolist() == chosen["identifiant"].tolist()
        assert pd.read_csv(OUTPUT / "jugements.csv")["identifiant"].tolist() == chosen["identifiant"].tolist()
