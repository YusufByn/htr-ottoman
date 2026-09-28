"""Tests du modèle de départ (htr_ottoman.base_model), sautés s'il n'est pas téléchargé."""
import pytest

from htr_ottoman.config import BASE_MODEL
from htr_ottoman.data.download import md5sum

pytestmark = pytest.mark.skipif(
    not BASE_MODEL.exists(), reason="modèle absent : uv run python -m htr_ottoman.base_model"
)


def test_md5_matches_zenodo():
    assert md5sum(BASE_MODEL) == "3c0db8cfab67fd709c7e6b49c237591d"


@pytest.fixture(scope="module")
def model():
    from htr_ottoman.base_model import load

    return load()


def test_model_loads_with_expected_input(model):
    assert model.input[2] == 120  # hauteur des lignes en pixels
    assert model.one_channel_mode == "L"  # niveaux de gris
    assert model.seg_type == "baselines"
    assert model.hyper_params["normalization"] == "NFD"


def test_codec(model):
    from htr_ottoman.base_model import codec_labels

    codec = codec_labels(model)
    assert len(codec) == 196
    assert all(len(k) == 1 for k in codec)
    assert {"ا", "ٓ", "ٔ", ".", " "} <= set(codec)  # alif, madda, hamza, point, espace
