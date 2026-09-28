"""Tests de htr_ottoman.final_eval : config pré-enregistrée et contrôles bloquants.

Aucun test ne prédit ni n'évalue sur le test interne : les contrôles sur les
données sont exercés sur la validation."""
import contextlib
import hashlib

import pandas as pd
import pytest

from htr_ottoman.config import CONFIGS, MAKHZAN_LINES, REPORTS, ROOT
from htr_ottoman.final_eval import (ControlFailed, check_hash, check_split, ketos_test_command, load_config,
                                    parse_ketos_report, sha256)

F9 = CONFIGS / "f9_test_interne.yml"


def test_f9_config_is_complete():
    config = load_config(F9)
    assert config["split"] == "test_interne"
    for value in [config["model"]["sha256"], config["reference"]["sha256"], config["reference"]["predictions_sha256"]]:
        assert len(value) == 64 and set(value) <= set("0123456789abcdef")
    assert config["expected"] == {"manuscripts": 17, "lines": 544, "reference_chars": 21211}


def test_f9_config_matches_committed_reference_predictions():
    reference = load_config(F9)["reference"]
    assert sha256(ROOT / reference["reports"] / "predictions.parquet") == reference["predictions_sha256"]


@pytest.mark.skipif(not (ROOT / load_config(F9)["model"]["path"]).exists(), reason="modèle F8 absent")
def test_f9_config_matches_model_file():
    model = load_config(F9)["model"]
    assert sha256(ROOT / model["path"]) == model["sha256"]


def test_sha256_and_check_hash(tmp_path):
    path = tmp_path / "f.bin"
    path.write_bytes(b"abc")
    assert sha256(path) == hashlib.sha256(b"abc").hexdigest()
    check_hash(path, hashlib.sha256(b"abc").hexdigest(), "fichier")
    with pytest.raises(ControlFailed):
        check_hash(path, "0" * 64, "fichier")


REPORT = ("=== report test_interne.arrow ===\n\n21211\tCharacters\n3100\tErrors\n85.39%\tCharacter Accuracy\n"
          "85.39%\tCharacter Accuracy (Case-insensitive)\n60.00%\tWord Accuracy\n\n300\tInsertions\n")


def test_parse_ketos_report():
    parsed = parse_ketos_report(REPORT)
    assert parsed["caracteres"] == 21211 and parsed["erreurs"] == 3100
    assert parsed["cer"] == pytest.approx(3100 / 21211)
    assert parse_ketos_report("rien") == {}


@pytest.mark.skipif(not (ROOT / load_config(F9)["model"]["path"]).exists(), reason="modèle F8 absent")
def test_ketos_test_command_is_accepted_by_ketos():
    # analyse des options comme ketos le ferait, sans rien lancer
    from kraken.ketos import cli

    args = ketos_test_command(ROOT / load_config(F9)["model"]["path"], "test_interne")
    i = args.index("test")
    assert args[:i] == ["-d", "cpu"]
    assert args[args.index("-e") + 1] == "data/processed/makhzan/test_interne.lst"
    assert {"-u", "NFD", "-n", "--reorder"} <= set(args)
    with contextlib.chdir(ROOT):
        ctx = cli.make_context("ketos", args[:i] + ["test"])
        cli.get_command(None, "test").make_context("test", args[i + 1:], parent=ctx)


@pytest.mark.skipif(not MAKHZAN_LINES.exists(), reason="table des lignes absente")
def test_check_split_on_validation():
    reference = pd.read_parquet(REPORTS / "baseline" / "val" / "lignes.parquet")
    check_split("val", {"manuscripts": 2, "lines": 412, "reference_chars": 21393}, reference)
    with pytest.raises(ControlFailed, match="Effectifs"):
        check_split("val", {"manuscripts": 2, "lines": 413, "reference_chars": 21393}, reference)
    changed = reference.copy()
    changed.loc[0, "ref_norm"] += "ا"
    with pytest.raises(ControlFailed, match="1 lignes diffèrent"):
        check_split("val", {"manuscripts": 2, "lines": 412, "reference_chars": 21393}, changed)
