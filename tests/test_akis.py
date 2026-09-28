"""Tests d'Akis (htr_ottoman.data.akis, htr_ottoman.analysis.akis_inventory).

Akis est écarté comme jeu de test (décision 40) : ces tests gardent la trace
de la vérification (effectifs, texte en alphabet latin, inventaire versionné).
"""
import pandas as pd
import pytest

from htr_ottoman.analysis.akis_inventory import (
    CHARACTERS_OUTPUT,
    SOURCES_OUTPUT,
    characters_table,
    script_of,
    sources_table,
    unicode_form,
)
from htr_ottoman.config import AKIS_LINES, BASE_MODEL
from htr_ottoman.data.akis import LINE_NAME, check_lines

needs_table = pytest.mark.skipif(
    not AKIS_LINES.exists(), reason="table des lignes Akis absente : lancer uv run python -m htr_ottoman.data.akis"
)


@pytest.mark.parametrize(
    "stem, source, page, line",
    [
        ("HRG_01-032_04", "HRG_01", "032", "04"),
        ("T-MKA-01-N-1927-522_18", "T-MKA-01-N-1927", "522", "18"),
        ("R-AM-01-AS-1888-086-B_03", "R-AM-01-AS-1888", "086-B", "03"),
    ],
)
def test_line_name(stem, source, page, line):
    m = LINE_NAME.match(stem)
    assert (m["source"], m["page"], m["line"]) == (source, page, line)


def test_unicode_form_and_script():
    assert unicode_form("hâl") == "NFC"
    assert unicode_form("hâl") == "NFD"
    assert unicode_form("hâl hâl") == "mixte"
    assert unicode_form("bir") == "sans_composition"
    assert [script_of(c) for c in "aك1"] == ["latin", "arabe", "autre"]


@pytest.fixture(scope="module")
def lines():
    return pd.read_parquet(AKIS_LINES)


@needs_table
def test_table(lines):
    assert len(lines) == 8036 and lines["source"].nunique() == 13
    assert not lines["is_empty"].any()
    assert (lines["image_height"] == 64).all()
    check_lines(lines)  # files.txt couvre exactement images/ et annotations/


@needs_table
def test_no_arabic_letter(lines):
    """Décision 40 : les transcriptions d'Akis sont en alphabet latin."""
    assert not lines["text"].map(lambda t: any(script_of(c) == "arabe" for c in t)).any()


@needs_table
def test_sources_report_reproduced(lines):
    expected = pd.read_csv(SOURCES_OUTPUT, dtype={"annee": "Int64"})
    pd.testing.assert_frame_equal(sources_table(lines), expected)


@needs_table
@pytest.mark.skipif(not BASE_MODEL.exists(), reason="modèle de départ absent")
def test_characters_report_reproduced(lines):
    expected = pd.read_csv(CHARACTERS_OUTPUT, keep_default_na=False)
    pd.testing.assert_frame_equal(characters_table(lines), expected, check_dtype=False)
