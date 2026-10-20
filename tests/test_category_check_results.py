"""Tests de htr_ottoman.analysis.category_check_results (F13, Q1, après la lecture), sans modèle ni prédiction."""
import pandas as pd
import pytest

import htr_ottoman.analysis.category_check_results as results
from htr_ottoman.analysis.category_check_results import (GROUPINGS, JUDGMENTS, OTHER, TEST, VALIDATION,
                                                         by_category, by_model, groupings, judged, non_by_comment,
                                                         overall)
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


def test_non_by_comment_uses_label_presence_only():
    table = pd.DataFrame({
        "identifiant": ["a", "b", "c", "d", "e"],
        "categorie": ["espace", "espace", "ponctuation", "ponctuation", "espace"],
        "réponse": ["non", "non", "non", "non", "oui"],
        "commentaire": ["Décalage, zone brouillée", "", "signe supprimé avec un espace", "point supprimé avec un espace",
                        "décalage"],
    })
    counts, other = non_by_comment(table)
    assert counts.loc["espace", ["non", "décalage", "zone brouillée", OTHER, "plusieurs libellés"]].tolist() == [2, 1, 1, 1, 1]
    assert counts.loc["ponctuation", ["non", "signe supprimé avec un espace", OTHER]].tolist() == [2, 1, 1]
    assert other["identifiant"].tolist() == ["b", "d"]  # libellé absent : « autre », sans interprétation
