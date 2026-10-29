"""Tests de l'expérience témoin de F15 (htr_ottoman.analysis.format_control, predict.predict_line_images)."""
import inspect
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from htr_ottoman.analysis import format_control as fc
from htr_ottoman.predict import predict_line_images


def test_validation_only_and_control_first():
    assert fc.SPLIT == "val"
    first = next(iter(fc.CONDITIONS))
    assert first == "c0_controle" and fc.CONDITIONS[first].crop == "decoupe"
    principal = [c for c in fc.CONDITIONS.values() if c.role == "principal"]
    assert all(c.mode == "b" and c.binarize in (None, "otsu") for c in principal)


def test_rectangle_is_clipped_bounding_box():
    page = Image.new("L", (100, 50), 255)
    assert fc.rectangle(page, [(10, 5), (40, 8), (38, 20), (12, 18)]).size == (31, 16)
    assert fc.rectangle(page, [(-5, -3), (120, 10), (90, 60)]).size == (100, 50)


def test_scale_factor_and_rescale():
    factor = fc.scale_factor([100, 168, 200])
    assert factor == pytest.approx(0.5)
    assert fc.rescale(Image.new("L", (300, 168)), factor).size == (150, 84)


def test_otsu_two_levels():
    grey = Image.fromarray(np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (8, 1)))
    out = fc.otsu(grey)
    assert out.mode == "L" and set(np.unique(np.asarray(out))) == {0, 255}
    flat = Image.new("L", (10, 4), 200)
    assert np.array_equal(np.asarray(fc.otsu(flat)), np.asarray(flat))


def test_predict_line_images_guards():
    seg = SimpleNamespace(type="bbox", lines=[1])
    with pytest.raises(ValueError):
        predict_line_images(SimpleNamespace(net=SimpleNamespace()), seg, [Image.new("L", (2, 2))])
    seg = SimpleNamespace(type="baselines", lines=[1, 2])
    with pytest.raises(ValueError):
        predict_line_images(SimpleNamespace(net=SimpleNamespace()), seg, [Image.new("L", (2, 2))])

    class Pool:  # processus de découpe : la substitution de _extract_line n'y serait pas vue
        pass

    with pytest.raises(ValueError, match="processus"):
        predict_line_images(SimpleNamespace(net=SimpleNamespace(_line_extraction_pool=Pool())),
                            SimpleNamespace(type="baselines", lines=[1]), [Image.new("L", (2, 2))])


def test_kraken_extract_line_signature():
    """predict_line_images remplace kraken.models.ctc._extract_line (kraken 7.1.1)."""
    import kraken.models.ctc as ctc

    assert list(inspect.signature(ctc._extract_line).parameters) == ["im", "segmentation", "line_idx", "legacy"]
    assert "_extract_line" in inspect.getsource(ctc.CTCRecognitionInferenceMixin._recognition_pred)
