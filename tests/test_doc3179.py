"""Tests de htr_ottoman.analysis.doc3179 (F13, Q6, avant la lecture), sans modèle ni prédiction."""
import inspect
import re
import subprocess
import sys

import pandas as pd
import pytest
from PIL import Image

import htr_ottoman.analysis.doc3179 as doc3179
from htr_ottoman.analysis.doc3179 import (HEADER, OUTPUT, PAGE, QUESTIONS, check_settings, color_view,
                                          compiled_images, doc_lines, sample)
from htr_ottoman.config import MAKHZAN_LINES, MAKHZAN_PROCESSED

data_available = pytest.mark.skipif(not MAKHZAN_LINES.exists() or not (MAKHZAN_PROCESSED / "test_interne.arrow").exists(),
                                    reason="table des lignes ou jeu compilé absents")


def test_never_reads_predictions_nor_loads_a_model():
    source = inspect.getsource(doc3179)
    assert "lignes.parquet" not in source and "hyp_norm" not in source and "load_models" not in source


@data_available
def test_preparation_runs_with_model_loading_forbidden():
    """Échantillon et images préparés dans un autre processus où charger un modèle lève une erreur."""
    code = """
import sys, htr_ottoman.base_model as bm, kraken.models
def forbidden(*args, **kwargs):
    raise RuntimeError("chargement de modèle interdit")
bm.load = kraken.models.load_models = forbidden
from htr_ottoman.analysis import doc3179
chosen = doc3179.sample(doc3179.doc_lines())
images = doc3179.compiled_images(set(chosen["line_id"]))
print(len(images), 'htr_ottoman.predict' in sys.modules)
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.split() == ["13", "False"]


def test_settings_come_from_the_config():
    check_settings()


def test_color_view_keeps_a_margin():
    page = Image.new("RGB", (1000, 400), "white")
    view = color_view(page, [(100, 100), (900, 100), (900, 150), (100, 150)])
    assert view.width == 800 + 2 * doc3179.MARGIN_X and view.height == 50 + 2 * 30  # marge de 0,6 × hauteur


@data_available
def test_sample_and_page():
    lines = doc_lines()
    assert len(lines) == 13 and lines["part_id"].nunique() == 1  # toutes les lignes gardées (d4b3280)
    chosen = sample(lines)
    assert chosen.equals(sample(lines)) and set(chosen["line_id"]) == set(lines["line_id"])
    images = compiled_images(set(chosen["line_id"]))  # ordre de compilation vérifié sur tout le jeu
    assert set(images) == set(chosen["line_id"])
    if PAGE.exists():
        page = PAGE.read_text(encoding="utf-8")
        assert len(re.findall(r'<section class="item"', page)) == 13 and page.count("<img ") == 26
        assert not re.search(r"[؀-ۿ]", page)  # aucun texte
        visible = re.sub(r"data:image/[a-z]+;base64,[^\"]+", "", page)  # texte de la page, sans les images
        assert "CER" not in visible.replace("aucun CER", "")
        for q in QUESTIONS.values():
            assert q.split(" : ", 1)[1].replace("'", "&#x27;") in page
        saved = pd.read_csv(OUTPUT / "echantillon.csv")
        assert saved.columns.tolist() == ["identifiant", "doc_id", "part_id", "line_index", "line_id"]
        assert saved["identifiant"].tolist() == chosen["identifiant"].tolist()
        template = pd.read_csv(OUTPUT / "jugements.csv")
        assert template.columns.tolist() == list(HEADER)


@pytest.mark.skipif(not MAKHZAN_LINES.exists(), reason="table des lignes absente")
def test_without_codec_same_lines_outside_train():
    from htr_ottoman.base_model import BASE_MODEL
    if not BASE_MODEL.exists():
        pytest.skip("modèle de départ absent")
    with_codec, without = doc3179.select_lines(), doc3179.select_lines(with_codec=False)
    outside_train = with_codec["split"] != "train"
    assert with_codec.loc[outside_train, "exclusion"].equals(without.loc[outside_train, "exclusion"])
