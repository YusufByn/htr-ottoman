"""Tests de htr_ottoman.analysis.rare_chars (F13, Q7), sans modèle ni prédiction."""
import subprocess
import sys

import pandas as pd
import pytest

from htr_ottoman.analysis.rare_chars import TEST_MODELS, TEST_ONLY, TRAIN_ONLY, check_alignment, occurrences, reading
from htr_ottoman.config import MAKHZAN_PROCESSED

data_available = pytest.mark.skipif(
    not ((MAKHZAN_PROCESSED / "train.arrow").exists() and all(p.exists() for p in TEST_MODELS.values())),
    reason="jeu compilé ou prédictions sauvegardées absents",
)


def test_never_imports_predict():
    code = "import sys, htr_ottoman.analysis.rare_chars; print('htr_ottoman.predict' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "False"


def test_alignment_checked_against_evaluate():
    ok = pd.DataFrame([{"line_id": "l1", "ref_norm": "باب", "hyp_norm": "بات",
                        "substitutions": 1, "deletions": 0, "insertions": 0}])
    check_alignment(ok, "synthétique")
    with pytest.raises(ValueError, match="alignement"):
        check_alignment(ok.assign(substitutions=0, deletions=1), "synthétique")


@data_available
def test_groups_and_reading():
    occ = occurrences().set_index("caractere")
    assert set(occ.index[occ["groupe"] == TRAIN_ONLY]) == set("،\u0655٠١٥ژڭگ")
    assert (occ.loc[occ["groupe"] == TRAIN_ONLY, "occurrences_val"] == 0).all()
    assert (occ.loc[occ["groupe"] == TEST_ONLY, "occurrences_train"] == 0).all()
    assert not occ.loc["\u200c", "dans_codec"] and occ.loc["\u200c", "occurrences_test_interne"] == 2  # Q2
    assert not occ.loc["ٮ", "dans_codec"] and not occ.loc["ڡ", "dans_codec"]  # décision 24
    present = occ.index[occ["occurrences_test_interne"] > 0].tolist()
    read = reading(present)
    for row in read.itertuples():
        assert row.reference == occ.loc[row.caractere, "occurrences_test_interne"]
        assert row.lus + row.supprimes + row.remplaces == row.reference
        if not occ.loc[row.caractere, "dans_codec"]:
            assert row.lus == row.ecrits_par_le_modele == 0  # hors codec : jamais écrit
