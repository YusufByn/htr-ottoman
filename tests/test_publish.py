"""Tests de htr_ottoman.publish (copie du modèle publié, drapeau corrigé dans l'en-tête, F14)."""
import json
import struct

import pytest
import torch
from safetensors.torch import load_file, save_file

from htr_ottoman.publish import dump_header, header_differences, split_safetensors, with_legacy_flag


def fake_model(tmp_path, flag=False):
    meta = {"uuid-1": {"_model": "TorchVGSLModel", "legacy_polygons": flag, "codec": {"ا": [1], " ": [2]}}}
    path = tmp_path / "best.safetensors"
    save_file({"uuid-1.nn.w": torch.arange(6.0).reshape(2, 3)}, path, metadata={"kraken_meta": json.dumps(meta)})
    return path


def test_only_the_flag_changes(tmp_path):
    raw, data = split_safetensors(fake_model(tmp_path).read_bytes())
    new = with_legacy_flag(raw)
    assert len(new) % 8 == 0
    assert header_differences(raw, new) == {"tenseurs": [], "autres_metadonnees": [], "kraken_meta": ["legacy_polygons"]}
    # la copie se relit, tenseurs inchangés
    copy = tmp_path / "copie.safetensors"
    copy.write_bytes(struct.pack("<Q", len(new)) + new + data)
    assert torch.equal(load_file(copy)["uuid-1.nn.w"], torch.arange(6.0).reshape(2, 3))
    assert json.loads(json.loads(new)["__metadata__"]["kraken_meta"])["uuid-1"]["legacy_polygons"] is True


def test_header_reproduced_like_safetensors(tmp_path):
    raw, _ = split_safetensors(fake_model(tmp_path).read_bytes())
    assert dump_header(json.loads(raw)) == raw


def test_refuses_a_flag_already_true(tmp_path):
    raw, _ = split_safetensors(fake_model(tmp_path, flag=True).read_bytes())
    with pytest.raises(ValueError, match="attendu false"):
        with_legacy_flag(raw)
