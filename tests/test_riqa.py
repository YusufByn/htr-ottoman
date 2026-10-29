"""Tests de RiqaTestset (htr_ottoman.data.riqa, htr_ottoman.analysis.riqa_inventory).

Test externe de F15 (décision 46) : l'inventaire ne charge aucun modèle et
reports/riqa/ ne contient aucune transcription.
"""
import subprocess
import sys

import pandas as pd
import pytest

from htr_ottoman.config import RIQA_LINES, RIQA_REPORTS, ROOT
from htr_ottoman.data.riqa import LINE_NAME

needs_table = pytest.mark.skipif(
    not RIQA_LINES.exists(), reason="table des lignes absente : lancer uv run python -I -m htr_ottoman.data.riqa"
)


def test_line_name():
    m = LINE_NAME.match("5d14e816-6f00-45f2-b951-030098f07e26-020")
    assert (m["unit"], m["line"]) == ("5d14e816-6f00-45f2-b951-030098f07e26", "020")
    assert LINE_NAME.match("5d14e816-020") is None


def test_inventory_never_imports_kraken():
    code = "import sys, htr_ottoman.analysis.riqa_inventory; print(any(m.split('.')[0] in ('kraken', 'torch') for m in sys.modules))"
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


@needs_table
def test_line_table():
    lines = pd.read_parquet(RIQA_LINES)
    assert (len(lines), lines["unit"].nunique()) == (1575, 85)
    assert not lines["is_empty"].any()


@needs_table
def test_reports_contain_no_transcription():
    """Décision 46 : aucune ligne de transcription (ni un extrait de 20 caractères) ni image dans reports/riqa/."""
    texts = [t.strip() for t in pd.read_parquet(RIQA_LINES)["text"]]
    extracts = {t[i : i + 20] for t in texts for i in range(0, max(len(t) - 19, 1), 20)}
    for path in (p for p in RIQA_REPORTS.rglob("*") if p.is_file()):
        content = path.read_text(encoding="utf-8")
        assert not any(e in content for e in extracts), path.name
        assert "data:image" not in content and path.suffix in (".csv", ".json", ".md"), path.name


def test_reading_page_outside_reports():
    """Décision 46 : la page de lecture, qui contient les images, est hors de reports/ et hors git."""
    from htr_ottoman.analysis.riqa_reading import OUTPUT, PAGE

    assert not PAGE.is_relative_to(ROOT / "reports") and PAGE.is_relative_to(ROOT / "data")
    assert OUTPUT.is_relative_to(RIQA_REPORTS)


@needs_table
def test_reading_items():
    from htr_ottoman.analysis.riqa_reading import FAMILIES, items

    table = items(pd.read_parquet(RIQA_LINES))
    assert list(table["identifiant"]) == [f"riqa_{i:02d}" for i in range(1, len(table) + 1)]
    assert set(table["famille"]) <= set(FAMILIES) and (table["occurrences"] > 0).all()
    assert not table.duplicated(["line_id", "famille"]).any()
