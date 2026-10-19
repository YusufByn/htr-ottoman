"""Tests de htr_ottoman.analysis.red_ink_errors (F13, Q3, après la lecture), sans modèle ni prédiction."""
import pandas as pd
import pytest

from htr_ottoman.analysis.period_errors import MODELS
from htr_ottoman.analysis.red_ink_errors import (DOC_TEST, DOC_VAL, OUTPUT, TEST_MODELS, crossing, outcomes_table,
                                                 period_outcomes, summary)

data_available = pytest.mark.skipif(
    not all((p / "lignes.parquet").exists() for p in [*MODELS.values(), *TEST_MODELS.values()])
    or not (OUTPUT / "jugements.csv").exists(),
    reason="prédictions sauvegardées ou jugements absents",
)


def test_period_outcomes():
    assert period_outcomes("اب . ج . د .", "اب . ج ه د") == [
        {"index_caractere": 3, "issue": "lu", "predit": "."},
        {"index_caractere": 7, "issue": "remplacé", "predit": "ه"},
        {"index_caractere": 11, "issue": "supprimé", "predit": ""},
    ]


@data_available
def test_saved_predictions():
    points = [outcomes_table(path, DOC_VAL, name) for name, path in MODELS.items()]
    table = summary(pd.concat(points)).set_index("modele")
    assert (table["reference"] == 86).all()
    assert (table["lu"] + table["supprimé"] + table["remplacé"] == table["reference"]).all()
    assert table.loc["f8_finetune", "supprimé"] + table.loc["f8_finetune", "remplacé"] == 74  # comme Q5
    cross = crossing(pd.concat(points))
    assert (cross.groupby("modele")[["lu", "supprimé", "remplacé"]].sum().sum(axis=1) == 40).all()
    test = summary(pd.concat([outcomes_table(p, DOC_TEST, n) for n, p in TEST_MODELS.items()]))
    assert (test["reference"] == 23).all()  # ؞ de Doc 3230, décision 21
