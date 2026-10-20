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
EXPERIMENTS_LOG = ROOT / "EXPERIMENTS.md"  # journal des expériences, une ligne ajoutée à chaque lancement
SPLITS = ROOT / "splits"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
BASELINE_REPORTS = REPORTS / "baseline"  # F7 : prédictions et CER du modèle de départ, un dossier par jeu
TRAINING_REPORTS = REPORTS / "training"  # F8 : métriques par époque de chaque entraînement retenu

# MAKHZAN, version 2026.1.2 (voir README)
MAKHZAN_RAW = DATA_RAW / "makhzan"
MAKHZAN_METADATA = MAKHZAN_RAW / "OpenITI-Makhzan_Metadata_2026-1-2.tsv"
MAKHZAN_ZIP = MAKHZAN_RAW / "OpenITI-Makhzan_Data_2026-1-2.zip"
MAKHZAN_INTERIM = DATA_INTERIM / "makhzan"  # un dossier par manuscrit ottoman (<DocID>/)
MAKHZAN_LINES = MAKHZAN_INTERIM / "ottoman_lines.parquet"  # une ligne par TextLine
MAKHZAN_PROCESSED = DATA_PROCESSED / "makhzan"  # ALTO normalisés (alto/), <jeu>.arrow, <jeu>.lst

# Akis, jeu de test public (github.com/verimsu/Akis-Ottoman-Dataset, Apache 2.0) : évaluation finale seulement
AKIS_RAW = DATA_RAW / "akis"
AKIS_ZIP = AKIS_RAW / "akis_dataset_test.zip"
AKIS_INTERIM = DATA_INTERIM / "akis"  # contenu du zip (images/, annotations/, files.txt)
AKIS_LINES = AKIS_INTERIM / "akis_lines.parquet"  # une ligne par image de ligne

# Modèle de départ : OpenITI ottoman imprimé (DOI 10.5281/zenodo.7050342, CC0)
BASE_MODEL_DIR = MODELS / "openiti_ottoman_print"
BASE_MODEL = BASE_MODEL_DIR / "ottoman_best.mlmodel"
BASE_MODEL_CODEC = REPORTS / "codec_modele_depart.json"  # codec du modèle de départ, lu sans charger le modèle (F14)

# F14 : modèle publié (décision 44), copie de F8 (lag 5) au drapeau « anciens polygones » corrigé (décisions 36 et 45)
PUBLISHED_SOURCE = MODELS / "f8_finetune" / "best_0.8365.safetensors"
PUBLICATION_DIR = MODELS / "f14_publication"
PUBLISHED_MODEL = PUBLICATION_DIR / "ota_naskh_makhzan_v0.1.0.safetensors"  # nom fixé le 2026-10-20 (décision 45, complément)
MODEL_CARD = ROOT / "MODEL_CARD.md"  # carte du modèle publié (en-tête YAML au schéma v1 de htrmopo)
DEPOSIT_DIR = PUBLICATION_DIR / "depot"  # fichiers envoyés à Zenodo : modèle publié et metadata.json (htrmopo)
