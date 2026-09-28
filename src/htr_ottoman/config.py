"""Chemins du projet, définis une seule fois pour tous les modules."""
from pathlib import Path

# src/htr_ottoman/config.py -> racine du projet
ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
DATA_RAW = DATA / "raw"  # lecture seule, jamais modifié
DATA_INTERIM = DATA / "interim"
DATA_PROCESSED = DATA / "processed"

MODELS = ROOT / "models"
CONFIGS = ROOT / "configs"
SPLITS = ROOT / "splits"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

# MAKHZAN, version 2026.1.2 (voir README)
MAKHZAN_RAW = DATA_RAW / "makhzan"
MAKHZAN_METADATA = MAKHZAN_RAW / "OpenITI-Makhzan_Metadata_2026-1-2.tsv"
MAKHZAN_ZIP = MAKHZAN_RAW / "OpenITI-Makhzan_Data_2026-1-2.zip"
