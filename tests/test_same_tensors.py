"""Tests de htr_ottoman.analysis.same_tensors (meilleur modèle et checkpoints, F14)."""
import torch
from safetensors.torch import save_file

from htr_ottoman.analysis.same_tensors import check_model_dir, compare, matching_epochs


def weights(seed):
    g = torch.Generator().manual_seed(seed)
    return {"nn.C_0.co.weight": torch.rand(3, 2, generator=g), "nn.C_0.co.bias": torch.rand(3, generator=g)}


def test_compare_counts_identical_tensors():
    best = weights(0)
    assert compare(best, "a", 1, weights(0))["tous_identiques"]
    other = dict(weights(0), **{"nn.C_0.co.bias": torch.zeros(3)})
    result = compare(best, "b", 2, other)
    assert result["communs"] == 2 and result["identiques"] == 1 and not result["tous_identiques"]


def test_a_missing_tensor_is_not_identical():
    best = weights(0)
    assert not compare(best, "a", 1, {"nn.C_0.co.weight": best["nn.C_0.co.weight"]})["tous_identiques"]


def test_check_model_dir_finds_the_epoch_of_the_best_checkpoint(tmp_path):
    # même nommage que kraken : préfixe <uuid>. dans le safetensors, net. et epoch comptée à partir de 0 dans le ckpt
    save_file({f"uuid.{k}": v for k, v in weights(1).items()}, tmp_path / "best_0.9.safetensors")
    for epoch, seed in [(4, 0), (5, 1), (6, 2)]:
        state = {f"net.{k}": v for k, v in weights(seed).items()}
        torch.save({"epoch": epoch, "state_dict": state}, tmp_path / f"checkpoint_{epoch:02d}-0.9.ckpt")
    table = check_model_dir(tmp_path)
    assert list(table["epoque"]) == [5, 6, 7]
    assert matching_epochs(table) == [6]
