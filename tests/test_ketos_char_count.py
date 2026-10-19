"""Tests de htr_ottoman.analysis.ketos_char_count (F13, Q2), sans modèle ni prédiction."""
import json
import unicodedata

import pytest

from htr_ottoman.analysis.ketos_char_count import kraken_text, kraken_text_steps, responsible_step, split_table
from htr_ottoman.config import MAKHZAN_PROCESSED, REPORTS

ZWNJ = "\u200c"


def test_bidi_drops_zwnj():
    text = unicodedata.normalize("NFD", f"جزئي{ZWNJ}ي انكار")  # comme la ligne de Doc 3215, déjà en NFD
    steps = dict(kraken_text_steps())
    assert steps["NFD"](text) == text and steps["-n"](text) == text  # NFD et -n gardent le ZWNJ
    assert ZWNJ not in steps["BiDi"](text)  # BiDi le retire (classe BN, règle X9)
    assert len(kraken_text(text)) == len(text) - 1
    assert responsible_step(text) == "BiDi"
    assert responsible_step("باب اول") == ""


@pytest.mark.skipif(not (MAKHZAN_PROCESSED / "test_interne.arrow").exists(), reason="jeux compilés absents")
def test_gap_explained_by_two_zwnj():
    val, val_rows = split_table("val")
    assert val["ecart"] == 0 and val_rows.empty
    test, rows = split_table("test_interne")
    assert (test["caracteres_evaluate"], test["caracteres_ketos"], test["ecart"]) == (21211, 21209, 2)
    assert rows["doc_id"].tolist() == [3215, 3215]
    assert rows["perdus"].str.startswith("U+200C").all() and (rows["ajoutes"] == "").all()
    assert (rows["transformation"] == "BiDi").all()
    run = json.loads((REPORTS / "f8_finetune" / "test_interne" / "run.json").read_text())
    assert run["ketos_test"]["caracteres"] == test["caracteres_ketos"]  # 21 209 de F9
