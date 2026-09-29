"""Tests de htr_ottoman.analysis.error_analysis : alignement, catégories, garde-fou, tableaux versionnés."""
import pandas as pd
import pytest

from htr_ottoman.analysis.error_analysis import (
    _marked, align, category, check_split, line_errors, tables, write_tables,
)
from htr_ottoman.config import REPORTS
from htr_ottoman.evaluate import edit_counts
from htr_ottoman.normalize import normalize

VAL = {"baseline": REPORTS / "baseline" / "val", "f8_finetune": REPORTS / "f8_finetune" / "val"}
OUTPUT = REPORTS / "erreurs" / "f8_finetune_baseline" / "val"


def test_align_by_hand():
    assert align("باب", "باب") == [("ب", "ب"), ("ا", "ا"), ("ب", "ب")]
    assert align("باب", "بات") == [("ب", "ب"), ("ا", "ا"), ("ب", "ت")]
    assert align("باب", "بب") == [("ب", "ب"), ("ا", ""), ("ب", "ب")]
    assert align("بب", "باب") == [("ب", "ب"), ("", "ا"), ("ب", "ب")]
    assert align("", "اب") == [("", "ا"), ("", "ب")]
    assert align("اب", "") == [("ا", ""), ("ب", "")]


@pytest.mark.parametrize("ref, hyp", [
    ("كتاب اول", "كتان اول"), ("اول كسك", "اولكسك"), ("kitten", "sitting"),
    ("بياننده باب", "ييانده باب ."), ("چونكه نامكلهابتدا ايتدم .", "چونكه نامخله ابتدا ايندم"), ("", ""),
])
def test_align_gives_same_counts_as_evaluate(ref, hyp):
    errors = line_errors(ref, hyp)
    counts = edit_counts(ref, hyp)
    assert sum(e["operation"] == "substitution" for e in errors) == counts.substitutions
    assert sum(e["operation"] == "suppression" for e in errors) == counts.deletions
    assert sum(e["operation"] == "insertion" for e in errors) == counts.insertions


@pytest.mark.parametrize("ref, hyp, expected", [
    (" ", "", "espace"), ("", " ", "espace"), ("ا", " ", "espace"),
    (".", "ه", "séparateur ."), (" ", ".", "espace"),  # ordre des catégories : l'espace d'abord
    ("", "٥", "chiffre"), ("", "5", "chiffre"), ("", "«", "ponctuation"), ("", "*", "ponctuation"),
    ("ي", "ى", "ي / ى"), ("ى", "ي", "ي / ى"),
    ("ب", "ي", "même squelette (points)"), ("ج", "خ", "même squelette (points)"), ("ه", "ة", "même squelette (points)"),
    ("ر", "و", "autre substitution"), ("ب", "ى", "autre substitution"),
    ("ن", "", "autre suppression"), ("", "ه", "autre insertion"),
])
def test_category(ref, hyp, expected):
    assert category(ref, hyp) == expected


def test_hamza_of_yeh_is_its_own_category():
    # En NFD, ئ = ي + hamza. ئ lu ى : deux alignements de même coût (1 S + 1 D) ; la préférence
    # d'evaluate retient « ي supprimé, hamza lue ى ». Seule la hamza compte alors dans ئ (limite connue).
    assert [e["categorie"] for e in line_errors(normalize("قائم"), "قاىم")] == ["autre suppression", "ئ"]
    assert [e["categorie"] for e in line_errors(normalize("قائم"), "قايم")] == ["ئ"]
    assert [e["categorie"] for e in line_errors("قايم", normalize("قائم"))] == ["ئ"]
    # la hamza de أ n'est pas celle de ئ
    assert [e["categorie"] for e in line_errors(normalize("أمر"), "امر")] == ["autre suppression"]


def test_marked_keeps_combining_mark_with_its_letter():
    madda = normalize("آ")  # ا + madda
    pairs = align(madda + "ب", "اب")  # madda oubliée
    assert _marked(pairs, 0) == f"<mark>{madda}</mark>ب"
    assert _marked(pairs, 1) == "اب"
    assert _marked(align("باب", "بات"), 1) == "با<mark>ت</mark>"


def test_only_validation_is_accepted():
    check_split(pd.DataFrame({"split": ["val", "val"]}), "val")
    for split in (["test_interne"], ["val", "test_interne"], ["train"]):
        with pytest.raises(ValueError, match="décision 39"):
            check_split(pd.DataFrame({"split": split}), "x")


@pytest.mark.skipif(not all((d / "lignes.parquet").exists() for d in VAL.values()), reason="évaluations absentes")
def test_versioned_tables_are_reproduced(tmp_path):
    out = tables(pd.read_parquet(VAL["baseline"] / "lignes.parquet"),
                 pd.read_parquet(VAL["f8_finetune"] / "lignes.parquet"), ("baseline", "f8_finetune"))
    # Les catégories partagent toutes les erreurs d'evaluate (F7 : 5 938 ; F8 : 3 491 sur 21 393 caractères)
    total = out["categories"].loc["total"]
    assert total["erreurs_baseline"] == 5938 and total["erreurs_f8_finetune"] == 3491
    assert total["points_cer_f8_finetune"] == pytest.approx(100 * 3491 / 21393)
    assert out["categories_par_operation"]["erreurs_f8_finetune"].sum() == 3491
    assert out["categories_par_manuscrit"]["erreurs_f8_finetune"].sum() == 3491
    assert out["operations"]["erreurs_baseline"].sum() == 5938
    assert out["par_longueur"]["lignes"].sum() == out["par_manuscrit"]["lignes"].sum() == 412
    write_tables(out, tmp_path)
    for path in tmp_path.glob("*.csv"):
        assert path.read_bytes() == (OUTPUT / path.name).read_bytes(), path.name
