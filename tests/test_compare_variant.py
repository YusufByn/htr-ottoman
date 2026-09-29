"""Tests de htr_ottoman.compare_variant : seuil de bruit, bootstrap apparié par page, règle de la décision 42."""
import math

import pandas as pd
import pytest

from htr_ottoman.compare import pair
from htr_ottoman.compare_variant import (
    BETTER, NO_DIFFERENCE, WORSE, conditions, page_ci, run, tables, threshold, verdict,
)
from htr_ottoman.config import REPORTS
from htr_ottoman.evaluate import bootstrap_ci, score_lines, script_groups

TEXTS = ["كتاب اول", "علي ديلر", "بيله", "قلور ايدى", "باش", "اول كسك"]
# une erreur par ligne (4 substitutions, 2 suppressions)
NOISY_PREDS = ["كتان اول", "على ديلر", "بيل", "قلور ايدي", "باس", "اولكسك"]


def scored(preds, split="val"):
    """Validation miniature : 2 manuscrits de 3 pages, une ligne par page."""
    n = len(TEXTS)
    df = pd.DataFrame({
        "part_id": range(n), "line_id": [f"l{i}" for i in range(n)], "text": TEXTS, "pred": preds,
        "doc_id": [2937] * 3 + [2939] * 3, "work": "Manāfi' al-nās", "script": "naskh",
        "category": "clean; once vetted", "is_multilingual": False, "split": split,
    })
    df["script_group"] = script_groups(df["script"])
    return score_lines(df)


PERFECT, NOISY = scored(TEXTS), scored(NOISY_PREDS)


@pytest.mark.parametrize("cers, spread, limit", [
    ([0.163, 0.165, 0.161], 0.004, 0.008),       # 2 × écart au-dessus de 0,5 point
    ([0.1630, 0.1632, 0.1634], 0.0004, 0.005),   # plancher de 0,5 point
    ([0.16, 0.16, 0.16], 0.0, 0.005),
])
def test_threshold(cers, spread, limit):
    assert threshold(cers) == pytest.approx((spread, limit))


def test_page_ci_of_identical_evaluations_is_zero():
    assert page_ci(pair(NOISY, NOISY)) == (0.0, 0.0)


def test_page_ci_uses_the_draws_of_evaluate_with_pages_as_units():
    # référence parfaite : chaque différence tirée vaut le CER du modèle sur les mêmes pages ;
    # l'IC apparié par page est donc l'IC d'evaluate où chaque page tient lieu de manuscrit
    by_page = NOISY.assign(doc_id=NOISY["part_id"])
    assert page_ci(pair(PERFECT, NOISY)) == pytest.approx(bootstrap_ci(by_page))


def test_page_ci_is_reproducible_and_brackets_estimate():
    half = scored(["كتان اول", "علي ديلر", "بيل", "قلور ايدى", "باس", "اول كسك"])
    paired = pair(NOISY, half)
    low, high = page_ci(paired)
    difference = (paired["errors_modele"].sum() - paired["errors_reference"].sum()) / paired["ref_chars"].sum()
    assert low <= difference <= high
    assert page_ci(paired) == (low, high)  # seed fixée


def test_no_page_interval_under_three_pages():
    low, high = page_ci(pair(NOISY.iloc[:2], PERFECT.iloc[:2]))
    assert math.isnan(low) and math.isnan(high)
    assert verdict(conditions(-0.1, low, high, [-0.1], 0.005)) == NO_DIFFERENCE


@pytest.mark.parametrize("difference, low, high, docs, expected", [
    (-0.010, -0.015, -0.005, [-0.012, -0.008], BETTER),
    (-0.004, -0.006, -0.002, [-0.005, -0.003], NO_DIFFERENCE),   # (a) baisse sous le seuil
    (-0.005, -0.008, -0.002, [-0.006, -0.004], NO_DIFFERENCE),   # (a) baisse égale au seuil : pas assez
    (-0.010, -0.020, 0.001, [-0.012, -0.008], NO_DIFFERENCE),    # (b) l'IC touche 0
    (-0.010, -0.015, -0.005, [-0.022, 0.001], NO_DIFFERENCE),    # (c) hausse dans un manuscrit
    (0.010, 0.005, 0.015, [0.012, 0.008], WORSE),
    (0.010, -0.001, 0.015, [0.012, 0.008], NO_DIFFERENCE),       # (b) inverse non rempli
    (0.010, 0.005, 0.015, [0.022, -0.001], NO_DIFFERENCE),       # (c) inverse non rempli
])
def test_rule_of_decision_42(difference, low, high, docs, expected):
    assert verdict(conditions(difference, low, high, docs, 0.005)) == expected


def test_tables_better_worse_and_no_difference():
    noise = {"42": NOISY, "43": NOISY, "44": NOISY}  # aucun écart : seuil de 0,5 point
    better = tables(NOISY, PERFECT, noise)["global"].loc["tout"]
    assert better["difference"] == pytest.approx(-6 / 39) and better["seuil"] == 0.005
    assert better["pages"] == 6 and better["ic95_pages_haut"] < 0 and better["conclusion"] == BETTER
    assert tables(PERFECT, NOISY, {"a": PERFECT, "b": PERFECT, "c": PERFECT})["global"].loc["tout", "conclusion"] == WORSE
    assert tables(NOISY, NOISY, noise)["global"].loc["tout", "conclusion"] == NO_DIFFERENCE


def test_noise_spread_raises_the_threshold():
    one_error = scored(["كتان اول", *TEXTS[1:]])  # CER de 1/39 contre 0 : écart de 2,6 points
    out = tables(NOISY, PERFECT, {"42": PERFECT, "43": PERFECT, "44": one_error})
    assert out["global"].loc["tout", "ecart_bruit"] == pytest.approx(1 / 39)
    assert out["global"].loc["tout", "seuil"] == pytest.approx(2 / 39)
    assert list(out["bruit"].index) == ["42", "43", "44"]


def test_noise_needs_three_runs_on_the_same_lines():
    with pytest.raises(ValueError, match="au moins 3"):
        tables(NOISY, PERFECT, {"42": NOISY, "43": NOISY})
    with pytest.raises(ValueError, match="mêmes lignes"):
        tables(NOISY, PERFECT, {"42": NOISY, "43": NOISY, "44": NOISY.iloc[1:]})


def _write(tmp_path, name, lines):
    directory = tmp_path / name / "val"
    directory.mkdir(parents=True)
    lines.to_parquet(directory / "lignes.parquet", index=False)
    return directory


def test_run_requires_the_reference_among_noise_runs_and_validation_only(tmp_path):
    ref, s43, s44 = (_write(tmp_path, n, NOISY) for n in ("f8", "s43", "s44"))
    variant = _write(tmp_path, "variante", PERFECT)
    out = run(ref, variant, [ref, s43, s44], tmp_path / "out")
    assert out["global"].loc["tout", "conclusion"] == BETTER
    assert {p.name for p in (tmp_path / "out").iterdir()} == {"global.csv", "par_manuscrit.csv", "bruit.csv"}
    with pytest.raises(ValueError, match="référence"):
        run(ref, variant, [s43, s44, variant], tmp_path / "out2")
    closed = _write(tmp_path, "test", scored(TEXTS, split="test_interne"))
    with pytest.raises(ValueError, match="décision 39"):
        run(ref, closed, [ref, s43, s44], tmp_path / "out3")


VAL = {m: REPORTS / m / "val" / "lignes.parquet" for m in ("baseline", "f8_finetune")}


@pytest.mark.skipif(not all(p.exists() for p in VAL.values()), reason="évaluations absentes")
def test_page_ci_on_the_validation():
    # contrôle de vraisemblance, sans rôle dans les choix : F8 contre la baseline, 19 pages
    paired = pair(pd.read_parquet(VAL["baseline"]), pd.read_parquet(VAL["f8_finetune"]))
    assert paired["part_id"].nunique() == 19
    low, high = page_ci(paired)
    assert low < (3491 - 5938) / 21393 < high < 0
