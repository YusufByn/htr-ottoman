"""Tests de htr_ottoman.analysis.same_curve (contrôle de déterminisme, décision 43)."""
import pandas as pd
import pytest

from htr_ottoman.analysis.same_curve import compare_curves
from htr_ottoman.config import MODELS, TRAINING_REPORTS


def metrics(loss, acc):
    return pd.DataFrame({"epoque": range(1, len(loss) + 1), "perte_train": loss, "val_accuracy": acc})


REF = metrics([10.0, 8.0, 7.0, 6.5], [0.70, 0.74, 0.75, 0.76])


def test_identical_until_the_requested_epoch():
    run = metrics([10.0, 8.0, 7.0, 6.0, 5.0], [0.70, 0.74, 0.75, 0.77, 0.78])  # diffère à l'époque 4
    assert compare_curves(REF, run, until=3)["identiques"]
    result = compare_curves(REF, run, until=4)
    assert not result["identiques"] and result["premiere_difference"] == 4
    assert result["ecart_max_perte_train"] == pytest.approx(0.5) and result["ecart_max_val_accuracy"] == pytest.approx(0.01)


def test_a_run_that_stops_too_early_is_not_identical():
    result = compare_curves(REF, REF.iloc[:2], until=3)
    assert result["epoques_comparees"] == 2 and result["premiere_difference"] is None and not result["identiques"]


F8, TRIAL = TRAINING_REPORTS / "f8_finetune.csv", MODELS / "f8_finetune_essai" / "metriques.csv"


@pytest.mark.skipif(not (F8.exists() and TRIAL.exists()), reason="métriques de F8 ou de son essai absentes")
def test_f8_trial_reproduced_the_first_epoch_of_f8():
    # constat de F8 : l'essai d'une époque (même config, même seed) redonne exactement l'époque 1
    assert compare_curves(pd.read_csv(F8), pd.read_csv(TRIAL), until=1)["identiques"]
