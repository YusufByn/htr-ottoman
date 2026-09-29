"""Tests de htr_ottoman.analysis.seed_curves : époques sans progrès, arrêts simulés, tableaux versionnés."""
import math

import pandas as pd
import pytest

from htr_ottoman.analysis.seed_curves import (
    OUTPUT, RUNS, epochs_without_progress, equal_epochs, load_curves, longest_stall, oscillations, stop_triggers,
    tables, write_tables,
)
from htr_ottoman.config import TRAINING_REPORTS

ACC = [0.70, 0.75, 0.75, 0.74, 0.80, 0.79, 0.78, 0.77, 0.81]  # égalité = pas de progrès (strict)


def curve(acc):
    return pd.DataFrame({"epoque": range(1, len(acc) + 1), "val_accuracy": acc, "cer_val_kraken": [1 - a for a in acc]})


def test_epochs_without_progress_by_hand():
    assert epochs_without_progress(ACC) == [0, 0, 1, 2, 0, 1, 2, 3, 0]


def test_stop_triggers_and_min_epochs():
    assert stop_triggers(ACC, lag=2, min_epochs=1) == [4, 7]
    assert stop_triggers(ACC, lag=2, min_epochs=5) == [7]
    assert stop_triggers(ACC, lag=3, min_epochs=1) == [8]
    assert stop_triggers(ACC, lag=4, min_epochs=1) == []


def test_longest_stall_before_best():
    assert longest_stall(ACC, before=9) == (3, 8)
    assert longest_stall(ACC, before=5) == (2, 4)
    assert longest_stall([0.1, 0.2, 0.3], before=3) == (0, None)


def test_equal_epochs_uses_only_seeds_that_reached_the_epoch():
    curves = {1: curve(ACC), 2: curve(ACC[:4])}
    out = equal_epochs(curves, epochs=[3, 6])
    assert out.loc[3, "seeds"] == 2 and out.loc[3, "ecart_brut"] == pytest.approx(0)
    assert out.loc[6, "seeds"] == 1 and math.isnan(out.loc[6, "ecart_brut"])
    assert out.loc[6, "cer_brut_seed1"] == pytest.approx(0.21) and out.loc[6, "cer_meilleur_seed1"] == pytest.approx(0.20)


def test_oscillations_by_hand():
    out = oscillations({1: curve([0.70, 0.72, 0.71, 0.74])}, last=3).loc[1]
    assert out["max"] == pytest.approx(0.03) and out["mediane"] == pytest.approx(0.02)
    assert out["max_3_dernieres"] == pytest.approx(0.03)  # variations entre les 3 dernières époques : 0,01 et 0,03


available = pytest.mark.skipif(not all((TRAINING_REPORTS / f"{c}.csv").exists() for c in RUNS.values()),
                               reason="métriques d'entraînement absentes")


@available
def test_simulation_finds_the_real_stops_and_versioned_tables(tmp_path):
    curves = load_curves()
    out = tables(curves)  # lève une erreur si le lag 5 ne retrouve pas les arrêts réels
    lag5 = out["arrets"].xs(5, level="lag")
    assert lag5["premier_declenchement"].tolist() == [91, 76, 49]
    assert lag5["meilleure_epoque"].tolist() == [86, 71, 44]
    assert (out["arrets"]["declenchements_avant_meilleure"] == 0).all()
    write_tables(out, tmp_path)
    for path in tmp_path.glob("*.csv"):
        assert path.read_bytes() == (OUTPUT / path.name).read_bytes(), path.name
