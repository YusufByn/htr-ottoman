"""Tests de htr_ottoman.analysis.period_errors (F13, Q5, validation), sans modèle ni prédiction."""
import pandas as pd
import pytest

from htr_ottoman.analysis.period_errors import MODELS, counts, model_table

data_available = pytest.mark.skipif(not all((p / "lignes.parquet").exists() for p in MODELS.values()),
                                    reason="prédictions sauvegardées de la validation absentes")


def test_counts():
    pairs = [(".", "."), (".", ""), (".", "ه"), ("", "."), ("ب", "."), ("ا", "ا")]
    assert counts(pairs) == {"reference": 3, "lus": 1, "oublies_supprimes": 1, "oublies_remplaces": 1,
                             "ajoutes_inseres": 1, "ajoutes_a_la_place": 1, "ecrits": 3}


def test_validation_only(tmp_path):
    pd.DataFrame([{"split": "test_interne", "line_id": "l", "ref_norm": "", "hyp_norm": "", "substitutions": 0,
                   "deletions": 0, "insertions": 0, "doc_id": 1}]).to_parquet(tmp_path / "lignes.parquet")
    with pytest.raises(ValueError, match="validation seulement"):
        model_table("x", tmp_path)


@data_available
def test_saved_predictions():
    tables = {name: model_table(name, path).set_index("doc_id") for name, path in MODELS.items()}
    for table in tables.values():
        assert table.loc["tout", "reference"] == 123 and table.loc["2937", "reference"] == 86
        assert (table["lus"] + table["oublies_supprimes"] + table["oublies_remplaces"] == table["reference"]).all()
    f8 = tables["f8_finetune"].loc["2937"]
    assert f8["oublies_supprimes"] + f8["oublies_remplaces"] == 74  # comme F12, étape 1 (séparateur, Doc 2937)
