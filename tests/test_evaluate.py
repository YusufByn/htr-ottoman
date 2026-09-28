"""Tests de htr_ottoman.evaluate : cas calculés à la main, agrégation, bootstrap."""
import math
import unicodedata

import pandas as pd
import pytest

from htr_ottoman.evaluate import EditCounts, bootstrap_ci, edit_counts, score_lines, summarize


# Cas calculés à la main (référence, hypothèse) -> (S, D, I)
@pytest.mark.parametrize(
    "ref, hyp, expected",
    [
        ("كتاب", "كتاب", EditCounts(0, 0, 0)),  # identiques
        ("كتاب", "كتان", EditCounts(1, 0, 0)),  # une substitution
        ("كتاب", "كتابل", EditCounts(0, 0, 1)),  # une insertion (caractère en trop)
        ("كتاب", "كتا", EditCounts(0, 1, 0)),  # une suppression (caractère manquant)
        ("كتاب", "", EditCounts(0, 4, 0)),  # prédiction vide
        ("", "", EditCounts(0, 0, 0)),
        ("", "اب", EditCounts(0, 0, 2)),
        ("كتاب", "كنان", EditCounts(2, 0, 0)),  # exemple du concept
        ("kitten", "sitting", EditCounts(2, 0, 1)),  # exemple classique : distance 3
    ],
)
def test_hand_computed_cases(ref, hyp, expected):
    assert edit_counts(ref, hyp) == expected


def test_errors_total():
    assert edit_counts("kitten", "sitting").errors == 3


def test_reversal_does_not_change_distance():
    # ordre logique ou ordre d'affichage : même distance pour un texte de droite à gauche
    for ref, hyp in [("كتاب اول", "كنان اول"), ("علي ديلر قنده", "على ديار قند")]:
        assert edit_counts(ref, hyp).errors == edit_counts(ref[::-1], hyp[::-1]).errors


def lines(pairs, doc_ids=None):
    return pd.DataFrame(
        {"text": [r for r, _ in pairs], "pred": [h for _, h in pairs], "doc_id": doc_ids or [1] * len(pairs)}
    )


def test_nfc_and_nfd_inputs_give_same_result():
    ref_nfc = "آل كتورب"
    pred_nfd = unicodedata.normalize("NFD", ref_nfc)
    assert ref_nfc != pred_nfd
    scored = score_lines(lines([(ref_nfc, pred_nfd)]))
    assert scored["errors"].sum() == 0


def test_normalize_applied_to_both_sides():
    # voyelles et keheh dans la prédiction : supprimées / unifiées par normalize (décisions 12, 13)
    scored = score_lines(lines([("كتاب", "کِتاب")]))
    assert scored["errors"].sum() == 0


def test_space_counts_as_character():
    scored = score_lines(lines([("اول كسك", "اولكسك")]))
    assert scored.loc[0, "deletions"] == 1 and scored.loc[0, "ref_chars"] == 7


def test_micro_aggregation():
    # 1 erreur sur 4 caractères, puis 1 erreur sur 1 caractère : micro = 2/5 (macro serait 0,625)
    scored = score_lines(lines([("كتاب", "كتان"), ("و", "ر")]))
    assert summarize(scored).loc["tout", "cer"] == pytest.approx(2 / 5)


def test_matches_torchmetrics():
    from torchmetrics.text import CharErrorRate

    pairs = [("علي ديلر قنده كيم", "على ديار قند كيم"), ("اول كسك باش", "اول كسك باس"), ("بيله", "بيلهلر"), ("قلور", "")]
    metric = CharErrorRate()
    for ref, hyp in pairs:
        metric.update(hyp, ref)
    ours = summarize(score_lines(lines(pairs))).loc["tout", "cer"]
    assert ours == pytest.approx(metric.compute().item())


def test_bootstrap_reproducible_and_brackets_estimate():
    pairs = [("كتاب اول", "كتان اول"), ("علي ديلر", "على ديلر"), ("بيله", "بيله"), ("قلور ايدى", "قلور ايدي"), ("باش", "باس")]
    scored = score_lines(lines(pairs, doc_ids=[1, 2, 3, 4, 5]))
    low, high = bootstrap_ci(scored)
    assert (low, high) == bootstrap_ci(scored)  # seed fixée
    cer = summarize(scored).loc["tout", "cer"]
    assert low <= cer <= high


def test_no_interval_under_three_manuscripts():
    scored = score_lines(lines([("كتاب", "كتان"), ("اول", "اول")], doc_ids=[1, 2]))
    low, high = bootstrap_ci(scored)
    assert math.isnan(low) and math.isnan(high)
    row = summarize(scored).loc["tout"]
    assert row["manuscrits"] == 2 and math.isnan(row["ic95_bas"])


def test_summarize_by_group():
    df = lines([("كتاب", "كتان"), ("اول", "اول"), ("باش", "باس")], doc_ids=[1, 2, 3])
    df["script"] = ["naskh", "naskh", "taliq"]
    table = summarize(score_lines(df), "script")
    assert table.loc["naskh", "lignes"] == 2 and table.loc["naskh", "cer"] == pytest.approx(1 / 7)
    assert table.loc["taliq", "cer"] == pytest.approx(1 / 3)


# Bout en bout sur les vraies lignes de validation (sautés si les données sont absentes)
def _val_data_available():
    from htr_ottoman.config import MAKHZAN_LINES

    return MAKHZAN_LINES.exists()


@pytest.mark.skipif(not _val_data_available(), reason="table des lignes absente")
def test_perfect_predictions_give_zero_cer():
    from htr_ottoman.evaluate import attach_metadata, report
    from htr_ottoman.prepare import select_lines

    lines = select_lines()
    val = lines[(lines["split"] == "val") & lines["exclusion"].isna()]
    preds = val[["part_id", "line_id"]].assign(pred=val["text"].values)
    tables = report(score_lines(attach_metadata(preds, "val")))
    assert tables["global"].loc["tout", "lignes"] == 412
    assert tables["global"].loc["tout", "erreurs"] == 0


@pytest.mark.skipif(not _val_data_available(), reason="table des lignes absente")
def test_missing_prediction_raises():
    from htr_ottoman.evaluate import attach_metadata
    from htr_ottoman.prepare import select_lines

    lines = select_lines()
    val = lines[(lines["split"] == "val") & lines["exclusion"].isna()]
    preds = val[["part_id", "line_id"]].assign(pred="").iloc[1:]  # une ligne sans prédiction
    with pytest.raises(ValueError):
        attach_metadata(preds, "val")
