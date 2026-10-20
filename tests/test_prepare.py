"""Tests de la préparation pour kraken (htr_ottoman.prepare), sautés si les jeux ne sont pas compilés."""
import subprocess
import sys
import unicodedata

import pandas as pd
import pytest

from htr_ottoman.config import BASE_MODEL, MAKHZAN_PROCESSED, ROOT
from htr_ottoman.data.annotations import has_annotation
from htr_ottoman.normalize import normalize
from htr_ottoman.prepare import ALTO_DIR, KRAKEN_TEXT_OPTIONS, LEGACY_POLYGONS, REPORT, read_arrow, verify_with_kraken
from htr_ottoman.splits import SPLIT_NAMES

pytestmark = pytest.mark.skipif(
    not all((MAKHZAN_PROCESSED / f"{n}.arrow").exists() for n in SPLIT_NAMES),
    reason="jeux absents : uv run python -m htr_ottoman.prepare",
)

EXPECTED = {"train": 2757, "val": 412, "test_interne": 544}  # train : 6 lignes hors codec écartées (décision 33)


@pytest.fixture(scope="module")
def arrows():
    return {name: read_arrow(name) for name in SPLIT_NAMES}


@pytest.mark.parametrize("name", SPLIT_NAMES)
def test_compiled_line_counts(arrows, name):
    texts, meta = arrows[name]
    assert len(texts) == EXPECTED[name]
    report = pd.read_csv(REPORT, keep_default_na=False).set_index("split")
    assert report.loc[name, "lignes_compilees"] == EXPECTED[name]


def test_exclusions():
    report = pd.read_csv(REPORT, keep_default_na=False).set_index("split")
    assert report["exclues_annotation"].sum() == 43
    assert report.loc["train", "exclues_vides"] + report.loc["val", "exclues_vides"] == 106
    assert report["exclues_hors_codec"].to_dict() == {"train": 6, "val": 0, "test_interne": 0}


def test_train_inside_base_codec(arrows):
    from htr_ottoman.base_model import codec_chars

    texts, _ = arrows["train"]
    assert set("".join(texts)) <= codec_chars()  # permet --resize fail en F8


@pytest.mark.parametrize("name", SPLIT_NAMES)
def test_compiled_text(arrows, name):
    texts, meta = arrows[name]
    assert meta["legacy_polygons"] is LEGACY_POLYGONS is True
    assert meta["type"] == "kraken_recognition_baseline"
    for t in texts:
        assert t and t == t.strip()
        assert unicodedata.is_normalized("NFD", t)
        assert normalize(t) == t
        assert not has_annotation(t)


@pytest.mark.parametrize("name", SPLIT_NAMES)
def test_kraken_text_transforms_are_noop(arrows, name):
    from kraken.lib.functional_im_transforms import text_normalize, text_whitespace_normalize

    texts, _ = arrows[name]
    for t in texts:
        assert text_whitespace_normalize(text_normalize(t, KRAKEN_TEXT_OPTIONS["normalization"])) == t
        assert not any(unicodedata.mirrored(c) for c in t)  # BiDi ne remplace aucun caractère


def test_text_options_match_base_model():
    if not BASE_MODEL.exists():
        pytest.skip("modèle de départ absent")
    from htr_ottoman.base_model import load

    hp = load().hyper_params
    assert KRAKEN_TEXT_OPTIONS["normalization"] == hp["normalization"]
    assert KRAKEN_TEXT_OPTIONS["normalize_whitespace"] == hp["normalize_whitespace"]
    assert KRAKEN_TEXT_OPTIONS["bidi_reordering"] is True  # modèle en ordre d'affichage (vérifié en F4)


def test_processed_alto_read_by_kraken():
    from kraken.lib.xml import XMLPage

    files = sorted(ALTO_DIR.glob("*/*.xml"))
    assert len(files) == 248
    n_lines = 0
    for f in files:
        page = XMLPage(f)
        assert page.imagename.is_file()
        assert ROOT / "data" / "interim" in page.imagename.resolve().parents
        for line in page.lines.values():
            assert line.text and normalize(line.text) == line.text
            n_lines += 1
    assert n_lines == sum(EXPECTED.values())


@pytest.mark.parametrize("name", SPLIT_NAMES)
def test_kraken_reads_sample(name):
    if not BASE_MODEL.exists():
        pytest.skip("modèle de départ absent")
    assert verify_with_kraken(name, limit=20) == 20


def test_select_lines_never_imports_kraken():
    # F14 : codec lu dans reports/codec_modele_depart.json, aucun modèle chargé
    code = """
import sys
from htr_ottoman.prepare import select_lines
lines = select_lines()
print(sorted(lines[lines["exclusion"].isna()].groupby("split").size().items()), "kraken" in sys.modules)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.split()[-1] == "False"
    assert "('test_interne', 544), ('train', 2757), ('val', 412)" in result.stdout
