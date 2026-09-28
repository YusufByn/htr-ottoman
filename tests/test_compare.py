"""Tests de htr_ottoman.compare : appariement, bootstrap apparié, règle de conclusion."""
import math

import pandas as pd
import pytest

from htr_ottoman.compare import compare, conclusion, pair, paired_bootstrap_ci, report
from htr_ottoman.evaluate import bootstrap_ci, score_lines, script_groups

TEXTS = ["كتاب اول", "علي ديلر", "بيله", "قلور ايدى", "باش", "اول كسك"]
SCRIPTS = ["naskh", "naskh", "naskh", "divani", "naskh_varied", "taliq"]


def scored(preds, texts=TEXTS, scripts=SCRIPTS):
    """Lignes évaluées comme par evaluate : une ligne par manuscrit, métadonnées minimales."""
    n = len(texts)
    df = pd.DataFrame({
        "part_id": range(n), "line_id": [f"l{i}" for i in range(n)], "text": texts, "pred": preds,
        "doc_id": range(100, 100 + n), "work": [f"oeuvre {i}" for i in range(n)], "script": scripts,
        "category": ["once", "twice"] * (n // 2) + ["once"] * (n % 2), "is_multilingual": [False] * (n - 1) + [True],
    })
    df["script_group"] = script_groups(df["script"])
    return score_lines(df)


PERFECT = scored(TEXTS)
NOISY = scored(["كتان اول", "على ديلر", "بيل", "قلور ايدي", "باس", "اولكسك"])


def test_identical_evaluations_give_zero_difference():
    row = compare(pair(NOISY, NOISY), with_conclusion=True).loc["tout"]
    assert row["difference"] == 0 and row["ic95_bas"] == 0 and row["ic95_haut"] == 0
    assert row["manuscrits_ameliores"] == 0 and row["conclusion"] == "pas de conclusion"


def test_difference_and_counts_computed_by_hand():
    # NOISY : 6 erreurs (4 substitutions, 2 suppressions) sur 39 caractères ; PERFECT : aucune
    row = compare(pair(NOISY, PERFECT)).loc["tout"]
    assert row["caracteres"] == 39 and row["erreurs_reference"] == 6 and row["erreurs_modele"] == 0
    assert row["difference"] == pytest.approx(-6 / 39)
    assert row["reduction_relative"] == pytest.approx(1.0)
    assert row["manuscrits_ameliores"] == 6
    assert row["suppressions_reference"] == 2 and row["substitutions_reference"] == 4


def test_gain_and_regression():
    # erreurs dans chaque manuscrit d'un côté, aucune de l'autre : l'IC exclut 0
    assert compare(pair(NOISY, PERFECT), with_conclusion=True).loc["tout", "conclusion"] == "gain"
    assert compare(pair(PERFECT, NOISY), with_conclusion=True).loc["tout", "conclusion"] == "régression"


@pytest.mark.parametrize("low, high, expected", [
    (-0.05, -0.01, "gain"), (0.01, 0.05, "régression"), (-0.01, 0.02, "pas de conclusion"),
    (-0.02, 0.0, "pas de conclusion"), (float("nan"), float("nan"), "pas de conclusion"),
])
def test_conclusion_rule(low, high, expected):
    assert conclusion(low, high) == expected


def test_paired_ci_uses_the_draws_of_evaluate():
    # référence parfaite : chaque différence tirée vaut le CER du modèle sur le même tirage,
    # l'IC apparié est donc exactement l'IC de evaluate pour le modèle
    paired = pair(PERFECT, NOISY)
    per_doc = paired.groupby("doc_id")[["ref_chars", "errors_reference", "errors_modele"]].sum()
    assert paired_bootstrap_ci(per_doc) == pytest.approx(bootstrap_ci(NOISY))


def test_paired_ci_reproducible_and_brackets_estimate():
    half = scored(["كتان اول", "علي ديلر", "بيل", "قلور ايدى", "باس", "اول كسك"])
    table = compare(pair(NOISY, half))
    row = table.loc["tout"]
    assert row["ic95_bas"] <= row["difference"] <= row["ic95_haut"]
    pd.testing.assert_frame_equal(table, compare(pair(NOISY, half)))  # seed fixée


def test_no_interval_under_three_manuscripts():
    row = compare(pair(NOISY.iloc[:2], PERFECT.iloc[:2]), with_conclusion=True).loc["tout"]
    assert math.isnan(row["ic95_bas"]) and row["conclusion"] == "pas de conclusion"


def test_report_tables_follow_decision_38():
    tables = report(pair(NOISY, PERFECT))
    assert set(tables) == {"global", "par_ecriture", "par_relecture", "par_manuscrit",
                           "sans_multilingue", "par_multilinguisme", "par_groupe_ecriture"}
    assert "conclusion" in tables["global"] and "conclusion" in tables["par_groupe_ecriture"]
    for name in ["par_ecriture", "par_relecture", "par_manuscrit", "sans_multilingue", "par_multilinguisme"]:
        assert "conclusion" not in tables[name]
    # par écriture : descriptif, sans IC, même pour un groupe d'au moins 3 manuscrits
    assert tables["par_ecriture"].loc["naskh", "manuscrits"] == 3
    assert tables["par_ecriture"][["ic95_bas", "ic95_haut"]].isna().all().all()
    groups = tables["par_groupe_ecriture"]
    assert groups.loc["naskh", "manuscrits"] == 3 and groups.loc["autres", "manuscrits"] == 3
    assert tables["sans_multilingue"].loc["tout", "manuscrits"] == 5


def test_pair_refuses_different_lines():
    with pytest.raises(ValueError, match="mêmes lignes"):
        pair(NOISY, PERFECT.iloc[1:])


def test_pair_refuses_different_ground_truth():
    other = scored(TEXTS, texts=["كتاب ثاني"] + TEXTS[1:])
    with pytest.raises(ValueError, match="ref_norm"):
        pair(NOISY, other)


def test_script_groups_put_mixed_scripts_with_others():
    scripts = pd.Series(["naskh", "naskh_varied", "naskh_shikaste_mixed", "divani", "taliq"])
    assert script_groups(scripts).tolist() == ["naskh", "autres", "autres", "autres", "autres"]


def test_internal_test_has_7_naskh_and_10_other_manuscripts():
    # métadonnées des pages seulement (splits/), aucune prédiction (décision 38)
    from htr_ottoman.splits import load_split

    pages = load_split("test_interne")
    per_doc = pages.groupby("doc_id")["script"].agg(lambda s: set(s))
    assert (per_doc.map(len) == 1).all()  # une seule écriture par manuscrit
    groups = script_groups(pages.groupby("doc_id")["script"].first())
    assert groups.value_counts().to_dict() == {"autres": 10, "naskh": 7}
