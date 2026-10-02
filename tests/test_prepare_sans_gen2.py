"""Tests du jeu d'entraînement de la variante C (htr_ottoman.prepare_sans_gen2), sautés s'il n'est pas compilé."""
import unicodedata

import pandas as pd
import pytest

from htr_ottoman.config import MAKHZAN_PROCESSED
from htr_ottoman.prepare import LEGACY_POLYGONS, read_arrow
from htr_ottoman.prepare_sans_gen2 import GEN2_LAYER, NAME, REPORT, check_subset, select, sha256

pytestmark = pytest.mark.skipif(
    not all((MAKHZAN_PROCESSED / f"{n}.arrow").exists() for n in (NAME, "train", "val")),
    reason="jeu de C absent : uv run python -m htr_ottoman.prepare_sans_gen2",
)


@pytest.fixture(scope="module")
def selected():
    return select()


@pytest.fixture(scope="module")
def report():
    return pd.read_csv(REPORT, keep_default_na=False).iloc[0]


def test_removed_pages_are_the_gen2_pages(selected):
    kept, removed = selected
    pages = removed.groupby("doc_id")["part_id"].nunique().to_dict()
    assert pages == {83: 9, 6398: 9}  # décision 4 : 18 pages
    assert len(removed) == 254 and len(kept) == 2503 and len(kept) + len(removed) == 2757  # décision 42
    assert (removed["layer"] == GEN2_LAYER).all() and (kept["layer"] != GEN2_LAYER).all()


def test_report(report):
    assert (report["manuscrits"], report["pages"], report["lignes"]) == (9, 181, 2503)
    assert (report["pages_retirees"], report["lignes_retirees"]) == (18, 254)
    assert report["sha256"] == sha256(MAKHZAN_PROCESSED / f"{NAME}.arrow")
    assert report["sha256_val_arrow"] == sha256(MAKHZAN_PROCESSED / "val.arrow")
    assert report["sha256_train_arrow"] == sha256(MAKHZAN_PROCESSED / "train.arrow")


def test_lines_are_f8_train_lines_without_gen2(selected):
    check_subset(*selected)  # mêmes textes et mêmes images que train.arrow, pages gen2 en moins


def test_compiled_text_inside_base_codec():
    from htr_ottoman.base_model import codec_chars

    texts, meta = read_arrow(NAME)
    assert len(texts) == 2503
    assert meta["legacy_polygons"] is LEGACY_POLYGONS is True
    assert all(unicodedata.is_normalized("NFD", t) for t in texts)
    assert set("".join(texts)) <= codec_chars()  # --resize fail : codec du modèle de départ inchangé


def test_characters_absent_after_removal(report):
    # présents dans le train de F8 seulement sur les pages gen2, absents de la validation
    assert report["absents_apres_retrait"] == "U+0655 U+06AF"
    val, _ = read_arrow("val")
    assert not {"ٕ", "گ"} & set("".join(val))
