"""Tests de htr_ottoman.analysis.category_check_results (F13, Q1, après la lecture), sans modèle ni prédiction."""
import pandas as pd
import pytest

import htr_ottoman.analysis.category_check_results as results
from htr_ottoman.analysis.category_check_results import (GROUPINGS, JUDGMENTS, TEST, VALIDATION, by_category,
                                                         by_model, groupings, judged, overall)
from htr_ottoman.analysis.error_analysis import CATEGORIES

data_available = pytest.mark.skipif(not all(p.exists() for p in (JUDGMENTS, TEST, VALIDATION)),
                                    reason="jugements ou tableaux d'error_analysis absents")


def test_groupings_cover_every_category_once():
    for groups in GROUPINGS.values():
        members = [c for m in groups.values() for c in m]
        assert sorted(members) == sorted(CATEGORIES)


@data_available
def test_refuses_incomplete_judgments(tmp_path, monkeypatch):
    answers = pd.read_csv(JUDGMENTS, keep_default_na=False)
    answers.loc[0, "réponse"] = ""
    broken = tmp_path / "jugements.csv"
    answers.to_csv(broken, index=False)
    monkeypatch.setattr(results, "JUDGMENTS", broken)
    with pytest.raises(ValueError, match="100 réponses"):
        judged()


@data_available
def test_tables():
    table = judged()
    categories = by_category(table)
    assert (categories["tirées"] == 10).all() and categories["erreurs (deux modèles)"].sum() == 13440
    assert (categories[["oui", "non", "incertain"]].sum(axis=1) == 10).all()
    assert by_model(table)[["oui", "non", "incertain"]].sum().sum() == 100
    total = overall(table).iloc[0]
    expected = (categories["erreurs (deux modèles)"] * categories["taux d'accord"]).sum() / 13440
    assert total["taux pondéré"] == pytest.approx(expected)
    groups = groupings(categories)
    for grouping, g in groups.groupby("regroupement"):
        assert g["points test interne f8_finetune"].sum() == pytest.approx(26.331, abs=1e-3)  # F9 : 26,3 %
        assert g["part du gain validation"].sum() == pytest.approx(1)
