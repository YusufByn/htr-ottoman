"""Vérifie que PyTorch voit le backend MPS (GPU Apple Silicon)."""
import platform

import torch

print(f"Python  : {platform.python_version()} ({platform.machine()})")
print(f"PyTorch : {torch.__version__}")
print(f"MPS compilé    : {torch.backends.mps.is_built()}")
print(f"MPS disponible : {torch.backends.mps.is_available()}")

if torch.backends.mps.is_available():
    x = torch.rand(1024, 1024, device="mps")
    y = (x @ x).sum().item()
    print(f"Test calcul sur MPS : OK (somme = {y:.1f})")
