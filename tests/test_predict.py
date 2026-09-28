"""Tests de htr_ottoman.predict (découpe : sautés si les modèles sont absents)."""
import pytest

from htr_ottoman.config import BASE_MODEL, MODELS
from htr_ottoman.prepare import LEGACY_POLYGONS
from htr_ottoman.predict import load_model, predict_split

MODEL_FILES = [BASE_MODEL, *sorted(MODELS.glob("*/best_*.safetensors"))]


@pytest.mark.parametrize("path", [p for p in MODEL_FILES if p.exists()], ids=lambda p: f"{p.parent.name}/{p.name}")
def test_line_extraction_imposed_by_project(path):
    # kraken 7.1.1 enregistre use_legacy_polygons=False dans les modèles convertis (décision 36)
    assert load_model(path).net.use_legacy_polygons is LEGACY_POLYGONS is True


def test_internal_test_is_closed(tmp_path):
    # refus avant tout chargement : le modèle n'existe même pas (décision 39)
    with pytest.raises(ValueError, match="décision 39"):
        predict_split(tmp_path / "absent.safetensors", "test_interne")
