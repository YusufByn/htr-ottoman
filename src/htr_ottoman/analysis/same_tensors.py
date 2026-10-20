"""Contrôle du meilleur modèle : de quel checkpoint viennent les poids de `best_*.safetensors` ?

kraken convertit le meilleur checkpoint en `best_<score>.safetensors` à la fin de
l'entraînement. Ce module compare les tenseurs de ce fichier à ceux de chaque
checkpoint gardé (`checkpoint_*.ckpt`) : un seul checkpoint doit avoir tous ses
tenseurs identiques (égalité exacte, `torch.equal`), celui de l'époque attendue.
L'époque est lue dans le checkpoint (kraken numérote à partir de 0 : époque = epoch + 1).

Lecture seule : aucun modèle chargé avec kraken, aucune prédiction, aucune donnée.
Reprend le script ponctuel de la vérification de la variante C (F12) ; celui de la
variante A est perdu (F14).

Code de sortie 1 si aucun checkpoint, ou un autre que celui de `--expected-epoch`,
n'a tous ses tenseurs identiques.

Usage : uv run python -m htr_ottoman.analysis.same_tensors --model-dir models/f8_finetune --expected-epoch 86
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import torch
from safetensors.torch import load_file

from htr_ottoman.config import REPORTS, ROOT

OUT_DIR = REPORTS / "f14" / "tenseurs"


def best_tensors(path: Path) -> dict[str, torch.Tensor]:
    """Tenseurs de `best_*.safetensors`, sans le préfixe propre au modèle (`<uuid>.`)."""
    return {k.split(".", 1)[1]: v for k, v in load_file(path).items()}


def checkpoint_tensors(path: Path) -> tuple[int, dict[str, torch.Tensor]]:
    """Époque (comptée à partir de 1) et tenseurs du réseau d'un checkpoint, sans le préfixe `net.`."""
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    return ckpt["epoch"] + 1, {k.removeprefix("net."): v for k, v in ckpt["state_dict"].items()}


def compare(best: dict[str, torch.Tensor], name: str, epoch: int, tensors: dict[str, torch.Tensor]) -> dict:
    """Tenseurs communs et identiques entre `best` et un checkpoint."""
    common = [k for k in best if k in tensors]
    same = sum(torch.equal(best[k], tensors[k]) for k in common)
    return {
        "checkpoint": name,
        "epoque": epoch,
        "tenseurs_best": len(best),
        "tenseurs_checkpoint": len(tensors),
        "communs": len(common),
        "identiques": same,
        "tous_identiques": len(common) == len(best) == len(tensors) == same,
    }


def check_model_dir(model_dir: Path) -> pd.DataFrame:
    bests = sorted(model_dir.glob("best_*.safetensors"))
    if len(bests) != 1:
        raise ValueError(f"{len(bests)} fichiers best_*.safetensors dans {model_dir}, attendu 1")
    best = best_tensors(bests[0])
    rows = [compare(best, ck.name, *checkpoint_tensors(ck)) for ck in sorted(model_dir.glob("checkpoint_*.ckpt"))]
    if not rows:
        raise ValueError(f"Aucun checkpoint dans {model_dir}")
    table = pd.DataFrame(rows).sort_values("epoque").reset_index(drop=True)
    table.insert(0, "best", bests[0].name)
    return table


def matching_epochs(table: pd.DataFrame) -> list[int]:
    return [int(e) for e in table.loc[table["tous_identiques"], "epoque"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--expected-epoch", type=int, required=True)
    args = parser.parse_args()
    model_dir = args.model_dir.resolve()

    table = check_model_dir(model_dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{model_dir.name}.csv"
    table.to_csv(out, index=False)
    print(table.drop(columns="best").to_string(index=False))
    found = matching_epochs(table)
    ok = found == [args.expected_epoch]
    print(f"\n{table['best'][0]} : tenseurs identiques à l'époque {found or 'aucune'}, "
          f"attendue {args.expected_epoch} : {'OK' if ok else 'ÉCART'} ({out.relative_to(ROOT)})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
