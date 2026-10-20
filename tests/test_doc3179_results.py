"""Tests de htr_ottoman.analysis.doc3179_results (F13, Q6, après la lecture), sans modèle ni prédiction."""
import subprocess
import sys

import pytest

from htr_ottoman.analysis.doc3179 import OUTPUT
from htr_ottoman.analysis.doc3179_results import EXPLORATORY_TABLES, categories, crossing, load_lines, manuscripts, worst
from htr_ottoman.analysis.error_analysis import EXPLORATORY_INPUTS

data_available = pytest.mark.skipif(
    not all((d / "lignes.parquet").exists() for d in EXPLORATORY_INPUTS)
    or not (OUTPUT / "jugements.csv").exists() or not (EXPLORATORY_TABLES / "par_manuscrit.csv").exists(),
    reason="prédictions sauvegardées de F9, jugements ou tableaux exploratoires absents")


@data_available
def test_runs_with_model_loading_forbidden():
    code = """
import sys, htr_ottoman.base_model as bm
def forbidden(*args, **kwargs):
    raise RuntimeError("chargement de modèle interdit")
bm.load = bm.codec_chars = forbidden
from htr_ottoman.analysis import doc3179_results as r
lines = r.load_lines()
r.crossing(lines)
print(len(lines), [m for m in ('kraken', 'torch', 'htr_ottoman.predict') if m in sys.modules])
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "13 []"


@data_available
def test_tables_match_f9():
    lines = load_lines()
    assert len(lines) == 13 and lines["caracteres"].sum() == 598
    for m, cer in (("baseline", 0.565), ("f8_finetune", 0.495)):  # plan : 56,5 % et 49,5 %
        assert lines[f"erreurs_{m}"].sum() / 598 == pytest.approx(cer, abs=5e-4)
    doc = manuscripts().set_index("doc_id").loc[3179]
    assert doc["S_f8_finetune"] == lines["S_f8_finetune"].sum() and doc["D_baseline"] == lines["D_baseline"].sum()
    total = categories().loc["total"]
    assert total["points_cer Doc 3179 f8_finetune"] == pytest.approx(100 * lines["erreurs_f8_finetune"].sum() / 598)
    assert len(worst(lines)) == 8 and (worst(lines)["caracteres"] >= 20).all()
    cross = crossing(lines)
    assert (cross.groupby("question")["lignes"].sum() == 13).all()
