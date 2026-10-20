"""Tests de htr_ottoman.analysis.error_analysis : alignement, catégories, garde-fous, tableaux versionnés,
mode exploratoire du test interne (F13, décision 39)."""
import pandas as pd
import pytest

import json
import re
import shutil
import subprocess
import sys

import htr_ottoman.analysis.error_analysis as error_analysis
from htr_ottoman.analysis.error_analysis import (
    EXPLORATORY_INPUTS, MENTION, _marked, align, analyse, category, check_split, line_errors, tables, write_html,
    write_tables,
)
from htr_ottoman.config import MAKHZAN_PROCESSED, REPORTS
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


@pytest.mark.skipif(not all((d / "lignes.parquet").exists() for d in VAL.values())
                    or not (MAKHZAN_PROCESSED / "val.arrow").exists(), reason="évaluations ou jeu compilé absents")
def test_versioned_page_is_reproduced(tmp_path):
    names = ("baseline", "f8_finetune")
    out = tables(pd.read_parquet(VAL["baseline"] / "lignes.parquet"),
                 pd.read_parquet(VAL["f8_finetune"] / "lignes.parquet"), names)
    write_html(out["pires_lignes"], names, tmp_path)
    assert (tmp_path / "pires_lignes.html").read_bytes() == (OUTPUT / "pires_lignes.html").read_bytes()


# Mode exploratoire du test interne (F13, complément du 2026-10-19 à la décision 39)
TEST_DIRS = list(EXPLORATORY_INPUTS)
f9_available = pytest.mark.skipif(not all((d / "lignes.parquet").exists() for d in TEST_DIRS),
                                  reason="prédictions sauvegardées de F9 absentes")
FORBIDDEN_MODULES = ("htr_ottoman.predict", "kraken", "torch")
CHILD = """
import json, os, subprocess, sys
from pathlib import Path
def forbidden(*args, **kwargs):
    raise RuntimeError("sous-processus interdit en mode exploratoire")
subprocess.Popen = subprocess.run = subprocess.call = subprocess.check_output = os.system = forbidden
import htr_ottoman.analysis.error_analysis as ea
root = Path(sys.argv[1])
ea.EXPLORATORY_ROOT = root
reference, model = ea.EXPLORATORY_INPUTS
ea.analyse(reference, model, root / "q1" / "test_interne", exploratory=True)
print(json.dumps(sorted(m for m in %r if m in sys.modules)))
""" % (FORBIDDEN_MODULES,)


@pytest.fixture(scope="module")
def exploratory_run(tmp_path_factory):
    """Le mode exploratoire en entier, dans un autre processus : aucun sous-processus permis."""
    root = tmp_path_factory.mktemp("f13")
    result = subprocess.run([sys.executable, "-c", CHILD, str(root)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]
    return root / "q1" / "test_interne", json.loads(result.stdout.strip().splitlines()[-1])


@f9_available
def test_exploratory_never_predicts(exploratory_run):
    output, loaded = exploratory_run
    assert loaded == []  # ni predict, ni kraken, ni torch importés ; aucun sous-processus (ketos) lancé
    assert sorted(p.name for p in output.iterdir()) == sorted(
        f"{n}.csv" for n in ("categories", "categories_par_manuscrit", "categories_par_operation", "operations",
                             "par_longueur", "par_manuscrit", "pires_lignes"))  # pas de page : aucune image lue


@f9_available
def test_exploratory_counts_only(exploratory_run):
    output, _ = exploratory_run
    forbidden = {"ic", "bootstrap", "verdict", "intervalle", "borne", "seuil", "difference", "différence", "p"}
    for path in output.glob("*.csv"):
        table = pd.read_csv(path)
        assert (table["mention"] == MENTION).all(), path.name
        tokens = {t for c in table.columns for t in re.split(r"[_ .]", c.lower())}
        assert not tokens & forbidden, (path.name, tokens & forbidden)
    total = pd.read_csv(output / "categories.csv", index_col=0).loc["total"]
    lines = {d.parent.name: pd.read_parquet(d / "lignes.parquet") for d in TEST_DIRS}
    assert total["erreurs_baseline"] == lines["baseline"]["errors"].sum()  # mêmes erreurs qu'evaluate
    assert total["erreurs_f8_finetune"] == lines["f8_finetune"]["errors"].sum()


@f9_available
def test_exploratory_refuses_output_outside_f13(tmp_path):
    for output in (tmp_path / "q1", REPORTS / "erreurs" / "test_interne"):
        with pytest.raises(ValueError, match="n'écrit que sous"):
            analyse(*TEST_DIRS, output, exploratory=True)
        assert not output.exists()


@f9_available
def test_exploratory_refuses_other_inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(error_analysis, "EXPLORATORY_ROOT", tmp_path)
    for reference, model in [(VAL["baseline"], VAL["f8_finetune"]), (TEST_DIRS[1], TEST_DIRS[0]),
                             (TEST_DIRS[0], REPORTS / "f8_lag15_seed42" / "val")]:
        with pytest.raises(ValueError, match="seules les prédictions sauvegardées de F9"):
            analyse(reference, model, tmp_path / "q1", exploratory=True)


@f9_available
def test_internal_test_refused_without_option(tmp_path):
    with pytest.raises(ValueError, match="décision 39"):
        analyse(*TEST_DIRS, tmp_path / "q1")
    assert not (tmp_path / "q1").exists()


@f9_available
def test_exploratory_refuses_modified_file(tmp_path, monkeypatch):
    copies = {}
    for directory, sha in EXPLORATORY_INPUTS.items():
        copy = tmp_path / directory.parent.name / directory.name
        copy.mkdir(parents=True)
        shutil.copy(directory / "lignes.parquet", copy / "lignes.parquet")
        copies[copy] = sha
    with open(list(copies)[0] / "lignes.parquet", "ab") as f:
        f.write(b"\0")  # un octet de plus : l'empreinte ne correspond plus
    monkeypatch.setattr(error_analysis, "EXPLORATORY_INPUTS", copies)
    monkeypatch.setattr(error_analysis, "EXPLORATORY_ROOT", tmp_path)
    monkeypatch.setattr(error_analysis.pd, "read_parquet", lambda *a, **k: pytest.fail("lecture avant le contrôle"))
    with pytest.raises(ValueError, match="SHA-256"):
        analyse(*copies, tmp_path / "q1", exploratory=True)
