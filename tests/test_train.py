"""Tests de htr_ottoman.train, sans lancer d'entraînement."""
import copy
from datetime import datetime

import click
import pytest

from htr_ottoman.config import BASE_MODEL, CONFIGS, MAKHZAN_PROCESSED, MODELS, REPORTS
from htr_ottoman.train import (build_command, check, experiment_row, load_config, output_paths, plot_curves,
                               read_metrics, to_args, uncommitted, validate_with_ketos)

F8_CONFIG = CONFIGS / "f8_finetune.yml"
data_available = pytest.mark.skipif(
    not (BASE_MODEL.exists() and (MAKHZAN_PROCESSED / "train.lst").exists()),
    reason="modèle de départ ou jeux compilés absents",
)


@pytest.fixture
def config():
    return load_config(F8_CONFIG)


def test_long_names_and_flags():
    assert to_args("train", {"lrate": 0.0001, "batch-size": 16}) == ["--lrate", "0.0001", "--batch-size", "16"]
    assert to_args("train", {"reorder": True, "augment": False}) == ["--reorder", "--no-augment"]
    assert to_args("train", {"legacy-polygons": False}) == []
    assert to_args("ketos", {"seed": 42, "deterministic": True}) == ["--seed", "42", "--deterministic"]


@pytest.mark.parametrize("values", [{"lrat": 0.1}, {"output": "models/x"}, {"partition": 0.9}, {"reorder": "yes"}])
def test_bad_keys_rejected(values):
    with pytest.raises(ValueError):
        to_args("train", values)


@data_available
def test_f8_config_is_valid(config, tmp_path):
    check(config)
    global_args, train_args = build_command(config, MODELS / "f8_finetune")
    assert train_args[-6:] == ["--output", "models/f8_finetune", "--logger", "tensorboard",
                               "--log-dir", "models/f8_finetune/logs"]
    (tmp_path / "logs").mkdir()  # ketos exige que --log-dir existe
    validate_with_ketos(*build_command(config, tmp_path))
    assert global_args == ["-v", "--device", "mps", "--seed", "42", "--deterministic"]
    pairs = dict(zip(train_args, train_args[1:]))
    assert pairs["--lrate"] == "0.0001" and pairs["--resize"] == "fail" and pairs["--quit"] == "early"
    assert pairs["--evaluation-data"] == "data/processed/makhzan/val.lst"
    assert "--reorder" in train_args and "--normalize-whitespace" in train_args


@data_available
def test_trial_overrides_stop_condition(config):
    _, train_args = build_command(config, MODELS / "f8_finetune_essai", trial=True)
    pairs = dict(zip(train_args, train_args[1:]))
    assert (pairs["--quit"], pairs["--epochs"], pairs["--min-epochs"]) == ("fixed", "1", "1")
    assert train_args.count("--quit") == 1


@data_available
@pytest.mark.parametrize("section, key, value", [
    ("train", "normalization", "NFC"),
    ("train", "reorder", False),
    ("train", "evaluation-data", "data/processed/makhzan/test_interne.lst"),
    ("ketos", "seed", 1),
])
def test_check_rejects(config, section, key, value):
    bad = copy.deepcopy(config)
    bad[section][key] = value
    with pytest.raises(ValueError):
        check(bad)


@data_available
def test_check_requires_validation(config):
    bad = copy.deepcopy(config)
    del bad["train"]["evaluation-data"]
    with pytest.raises(ValueError):
        check(bad)


@data_available
@pytest.mark.parametrize("seed", [43, 44])
def test_noise_configs_are_f8_with_another_seed(config, seed, tmp_path):
    # répétitions de F8 pour le bruit (décision 42) : seule la seed change
    path = CONFIGS / f"f8_finetune_seed{seed}.yml"
    noise = load_config(path)
    check(noise)
    assert noise["ketos"]["seed"] == seed and {**noise["ketos"], "seed": 42} == config["ketos"]
    assert noise["train"] == config["train"]
    assert output_paths(path, trial=False)["output"] == MODELS / f"f8_finetune_seed{seed}"
    (tmp_path / "logs").mkdir()
    global_args, train_args = build_command(noise, tmp_path)
    validate_with_ketos(global_args, train_args)
    assert global_args == ["-v", "--device", "mps", "--seed", str(seed), "--deterministic"]


@data_available
@pytest.mark.parametrize("section, key, value", [("train", "lrate", 0.0003), ("train", "augment", True),
                                                 ("ketos", "deterministic", False)])
def test_noise_seed_refused_if_anything_else_changes(config, section, key, value):
    bad = copy.deepcopy(config)
    bad["ketos"]["seed"] = 43
    bad[section][key] = value
    with pytest.raises(ValueError, match="décision 42"):
        check(bad)


@data_available
def test_ketos_rejects_bad_value(config, tmp_path):
    (tmp_path / "logs").mkdir()
    bad = copy.deepcopy(config)
    bad["train"]["resize"] = "unionn"
    with pytest.raises(click.UsageError):
        validate_with_ketos(*build_command(bad, tmp_path))


def test_uncommitted_ignores_journal_only():
    porcelain = " M EXPERIMENTS.md\n M src/htr_ottoman/train.py\n?? configs/f9.yml\n"
    assert uncommitted(porcelain) == ["src/htr_ottoman/train.py", "configs/f9.yml"]
    assert uncommitted(" M EXPERIMENTS.md\n") == []


def test_trial_writes_apart_from_full_run():
    full, trial = output_paths(F8_CONFIG, trial=False), output_paths(F8_CONFIG, trial=True)
    assert full["output"] == MODELS / "f8_finetune" and trial["output"] == MODELS / "f8_finetune_essai"
    assert all(p.is_relative_to(trial["output"]) for p in trial.values())  # rien dans reports/
    assert full["metrics"].is_relative_to(REPORTS) and full["figure"].is_relative_to(REPORTS)


def test_experiment_row(config):
    row = experiment_row(config, F8_CONFIG, MODELS / "f8_finetune_essai", "abc1234", True, datetime(2026, 9, 28, 14, 5))
    cells = row.strip("|").split(" | ")
    assert len(cells) == 8  # colonnes d'EXPERIMENTS.md
    assert cells[0].strip() == "2026-09-28" and cells[1] == "abc1234" and cells[5] == "en cours"
    assert "--trial" in row and "models/f8_finetune_essai/" in row and "14:05" in row


def test_read_metrics_and_plot(tmp_path):
    from torch.utils.tensorboard import SummaryWriter

    # 2 pas par seconde, pertes enregistrées aux pas 5 et 15 de chaque époque de 20 pas,
    # validation de 4 s après chaque époque
    writer = SummaryWriter(tmp_path / "logs" / "version_0")
    t0 = 1000.0
    for epoch, (loss, acc) in enumerate([(2.0, 0.70), (1.0, 0.80), (0.5, 0.78)]):
        base_step, base_t = 20 * epoch, t0 + epoch * 14
        for k in (5, 15):
            writer.add_scalar("train_loss_step", loss + 0.1, base_step + k, walltime=base_t + k / 2)
            writer.add_scalar("epoch", epoch, base_step + k, walltime=base_t + k / 2)
        end = base_step + 20
        writer.add_scalar("val_accuracy", acc, end, walltime=base_t + 10 + 4)
        writer.add_scalar("train_loss_epoch", loss, end, walltime=base_t + 10 + 4)
        writer.add_scalar("epoch", epoch, end, walltime=base_t + 10 + 4)
    writer.close()

    metrics = read_metrics(tmp_path / "logs")
    assert metrics["epoque"].tolist() == [1, 2, 3]
    assert metrics["perte_train"].tolist() == pytest.approx([2.0, 1.0, 0.5])
    assert metrics["cer_val_kraken"].tolist() == pytest.approx([0.30, 0.20, 0.22])
    assert metrics["duree_train_s"].tolist() == pytest.approx([10, 10, 10])
    assert metrics["duree_val_s"].tolist() == pytest.approx([4, 4, 4])
    assert metrics["debut_s"].iloc[0] == pytest.approx(t0)

    plot_curves(metrics, "essai", tmp_path / "courbes.png")
    assert (tmp_path / "courbes.png").stat().st_size > 0
