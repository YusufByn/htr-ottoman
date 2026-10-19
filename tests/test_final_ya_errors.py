"""Tests de htr_ottoman.analysis.final_ya_errors (F13, Q4, après la lecture), sans modèle ni prédiction."""
import pandas as pd
import pytest

from htr_ottoman.analysis.final_ya import OUTPUT
from htr_ottoman.analysis.final_ya_errors import (MECHANICAL, RIGHT_DOTS, SENSITIVITY, confusions, judged,
                                                  train_counts, weighted, yeh_outcomes, yeh_positions)
from htr_ottoman.analysis.period_errors import MODELS

data_available = pytest.mark.skipif(
    not all((p / "lignes.parquet").exists() for p in MODELS.values()) or not (OUTPUT / "jugements.csv").exists(),
    reason="prédictions sauvegardées ou jugements absents")


def test_yeh_positions():
    assert yeh_positions("بي بيت بئ ى.") == {1: "fin", 4: "milieu", 11: "fin"}


def test_yeh_outcomes():
    assert [o["issue"] for o in yeh_outcomes("بي بيت بى", "بى بيت ب")] == ["confondu", "correct", "autre"]


@data_available
def test_saved_predictions_and_judgments():
    conf = confusions().set_index(["modele", "doc_id", "lettre", "position"])
    f8 = conf.loc["f8_finetune", 2937]
    assert f8.loc[("ي", "fin"), ["correct", "confondu", "autre"]].tolist() == [112, 82, 15]  # population de Q4
    assert f8.loc[("ى", "fin"), ["correct", "confondu", "autre"]].tolist() == [84, 2, 20]
    table = judged()
    assert len(table) == 40 and set(MECHANICAL) <= set(table["identifiant"])
    assert (table.loc[table["identifiant"].isin(MECHANICAL), "commentaire"] != "").all()
    right = table["commentaire"].str.contains("droite")
    assert sorted(table.loc[right, "identifiant"]) == sorted(RIGHT_DOTS)  # aucune autre entrée décrite ainsi
    for name in SENSITIVITY:  # les variantes ne touchent que les cinq entrées
        changed = table["identifiant"][table[name] != table["lecture 2"]]
        assert set(changed) <= set(RIGHT_DOTS)
    assert (table.loc[table["lecture 1"] == "oui", list(SENSITIVITY)] == "oui").all().all()
    total = weighted(table, "lecture 1").set_index("groupe").iloc[-1]
    assert total["population"] == 280 and total["tirés"] == 40
    assert pd.read_csv(OUTPUT / "jugements.csv", keep_default_na=False).shape == (40, 3)
    train = train_counts().set_index("doc_id").loc["total"]
    assert (train["ي fin"], train["ى fin"]) == (668, 3037)  # piste F15 n° 1
