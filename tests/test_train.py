"""Tests de htr_ottoman.train, sans lancer d'entraînement."""
import copy
from datetime import datetime

import click
import pytest

from htr_ottoman.config import BASE_MODEL, CONFIGS, MAKHZAN_PROCESSED, MODELS, REPORTS
from htr_ottoman.train import (add_experiment_row, build_command, cap_of, check, experiment_row, launcher,
                               load_config, output_paths, plot_curves, read_metrics, stop_reason, stop_rule,
                               technical_bases, to_args, uncommitted, validate_with_ketos)

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


# F12, décision 43 : règle d'arrêt lag 15, plafond 150, appliquée par ketos_capped

LAG15 = {seed: CONFIGS / f"f8_lag15_seed{seed}.yml" for seed in (42, 43, 44)}
TECHNICAL = CONFIGS / "essai_technique_plafond.yml"
TECHNICAL_B = CONFIGS / "essai_technique_b_augment.yml"
TECHNICAL_A = CONFIGS / "essai_technique_a_lr3e-4.yml"
TECHNICAL_C = CONFIGS / "essai_technique_c_sans_gen2.yml"
C_TRAIN = "data/processed/makhzan/train_sans_gen2.lst"  # variante C : train de F8 sans les pages gen2
c_available = pytest.mark.skipif(not (MAKHZAN_PROCESSED / "train_sans_gen2.lst").exists(),
                                 reason="jeu de C absent : uv run python -m htr_ottoman.prepare_sans_gen2")


@data_available
@pytest.mark.parametrize("seed", [42, 43, 44])
def test_lag15_configs_are_f8_with_f12_stop_rule(config, seed, tmp_path):
    path = LAG15[seed]
    lag15 = load_config(path)
    check(lag15, path)
    expected = copy.deepcopy(config)
    expected["ketos"]["seed"] = seed
    expected["train"].update(lag=15, epochs=150)
    assert lag15 == expected
    assert stop_rule(lag15) == {"quit": "early", "lag": 15, "epochs": 150, "min-epochs": 5}
    assert launcher(lag15)[0] == ["uv", "run", "python", "-m", "htr_ottoman.ketos_capped"]
    assert cap_of(lag15) == 150 and cap_of(lag15, trial=True) is None  # --trial : 1 époque fixe, ketos seul
    (tmp_path / "logs").mkdir()
    global_args, train_args = build_command(lag15, tmp_path)
    validate_with_ketos(global_args, train_args)
    pairs = dict(zip(train_args, train_args[1:]))
    assert (pairs["--quit"], pairs["--lag"], pairs["--epochs"]) == ("early", "15", "150")


@data_available
@pytest.mark.parametrize("path", [F8_CONFIG, CONFIGS / "f8_finetune_seed43.yml", CONFIGS / "f8_finetune_seed44.yml"])
def test_lag5_configs_never_use_the_capped_launcher(path):
    lag5 = load_config(path)
    check(lag5, path)
    assert cap_of(lag5) is None and launcher(lag5)[0] == ["uv", "run", "ketos"]


def _f12(**train):
    bad = load_config(LAG15[42])
    bad["train"].update(train)
    return bad


@data_available
@pytest.mark.parametrize("changes, name, message", [
    ({"epochs": None}, "variante", "exige 150"),                      # lag 15 sans plafond
    ({"lag": 5}, "variante", "réservé à la règle d'arrêt de F12"),    # plafond avec lag 5
    ({"epochs": 100}, "variante", "la règle de F12 est 150"),         # autre plafond, hors essai technique
    ({"lrate": 0.0003}, "f8_lag15_seed42", "décision 43"),            # la référence ne change que seed, lag, plafond
    ({"epochs": 2, "lrate": 0.0005}, "essai_technique_x", "à un plafond plus petit près"),  # taux d'aucune variante
    ({"epochs": 150}, "essai_technique_x", "plafond plus petit"),
    ({"epochs": 1, "augment": True, "lrate": 0.0003}, "essai_technique_x", "à un plafond plus petit près"),  # B + autre chose
    ({"epochs": 150, "augment": True}, "essai_technique_x", "plafond plus petit"),  # B au plafond de F12
])
def test_stop_rule_guards(changes, name, message):
    with pytest.raises(ValueError, match=message):
        check(_f12(**changes), CONFIGS / f"{name}.yml")


@data_available
def test_f12_variant_and_technical_trial_accepted():
    check(_f12(augment=True), CONFIGS / "f12_b_augment.yml")  # variante : seed 42, règle de F12, une variable
    technical = load_config(TECHNICAL)
    check(technical, TECHNICAL)
    assert technical == _f12(epochs=2) and cap_of(technical) == 2


VARIANTS = {  # variante de F12 : seule différence avec f8_lag15_seed42 (décision 42)
    "f12_b_augment": {"augment": True},
    "f12_a_lr3e-4": {"lrate": 0.0003},
    "f12_c_sans_gen2": {"training-data": C_TRAIN},
}


@data_available
@pytest.mark.parametrize("name, change", [
    pytest.param(name, change, marks=c_available) if name == "f12_c_sans_gen2" else (name, change)
    for name, change in VARIANTS.items()
])
def test_variant_is_reference_with_one_change(name, change, tmp_path):
    path = CONFIGS / f"{name}.yml"
    variant = load_config(path)
    check(variant, path)
    assert variant == _f12(**change)
    assert variant["ketos"]["seed"] == 42 and stop_rule(variant) == {"quit": "early", "lag": 15, "epochs": 150,
                                                                    "min-epochs": 5}
    assert launcher(variant)[0] == ["uv", "run", "python", "-m", "htr_ottoman.ketos_capped"] and cap_of(variant) == 150
    (tmp_path / "logs").mkdir()
    global_args, train_args = build_command(variant, tmp_path)
    validate_with_ketos(global_args, train_args)
    assert ("--augment" in train_args) == bool(change.get("augment"))  # A : sans augmentation
    pairs = dict(zip(train_args, train_args[1:]))
    assert float(pairs["--lrate"]) == change.get("lrate", 0.0001)
    assert pairs["--training-data"] == change.get("training-data", "data/processed/makhzan/train.lst")
    assert pairs["--evaluation-data"] == "data/processed/makhzan/val.lst"


# Empreintes des jeux de F8 compilés le 2026-09-28 (reports/train_sans_gen2.csv), avant F8 : la validation de C
# doit être le même fichier, au même contenu, que celle de la référence.
VAL_SHA256 = "aeb0188cec9cbbd75241ffd36c317d64897e4a060a345e16b6308859491022a7"
TRAIN_SHA256 = "1c88a502281e7342e0d5e3e63f72785a8112f2267b722d725c96f849f3763e69"


def _differences(a: dict, b: dict) -> set[tuple[str, str]]:
    return {(section, key) for section in a for key in set(a[section]) | set(b[section])
            if a[section].get(key) != b[section].get(key)}


@data_available
@c_available
def test_variant_c_changes_only_training_data():
    from htr_ottoman.prepare_sans_gen2 import sha256

    reference, variant = load_config(LAG15[42]), load_config(CONFIGS / "f12_c_sans_gen2.yml")
    assert _differences(reference, variant) == {("train", "training-data")}
    assert variant["train"]["training-data"] == C_TRAIN
    assert (MAKHZAN_PROCESSED / "train_sans_gen2.lst").read_text() == "data/processed/makhzan/train_sans_gen2.arrow\n"
    # validation : même manifeste, même fichier compilé, même empreinte que la référence
    assert variant["train"]["evaluation-data"] == reference["train"]["evaluation-data"] == "data/processed/makhzan/val.lst"
    assert (MAKHZAN_PROCESSED / "val.lst").read_text() == "data/processed/makhzan/val.arrow\n"
    assert sha256(MAKHZAN_PROCESSED / "val.arrow") == VAL_SHA256
    assert sha256(MAKHZAN_PROCESSED / "train.arrow") == TRAIN_SHA256  # train de F8 non modifié


@data_available
@pytest.mark.parametrize("path, change", [
    (TECHNICAL_B, {"augment": True}),
    (TECHNICAL_A, {"lrate": 0.0003}),
    pytest.param(TECHNICAL_C, {"training-data": C_TRAIN}, marks=c_available),
])
def test_technical_trial_of_a_variant(path, change, tmp_path):
    # décision 43, complément du 2026-10-01 : essai technique d'une variante versionnée, plafond plus petit
    technical = load_config(path)
    check(technical, path)
    assert technical == _f12(**change, epochs=1)
    assert launcher(technical)[0] == ["uv", "run", "python", "-m", "htr_ottoman.ketos_capped"] and cap_of(technical) == 1
    (tmp_path / "logs").mkdir()
    validate_with_ketos(*build_command(technical, tmp_path))
    paths = output_paths(path, trial=False)
    assert paths["output"] == MODELS / path.stem
    assert all(p.is_relative_to(paths["output"]) for p in paths.values())


@data_available
def test_technical_bases_are_reference_and_f12_variants(tmp_path):
    reference = load_config(LAG15[42])
    assert technical_bases(tmp_path) == [reference]  # aucune variante : f8_lag15_seed42 seul
    (tmp_path / "f12_z.yml").write_text((CONFIGS / "f12_b_augment.yml").read_text())
    (tmp_path / "autre.yml").write_text((CONFIGS / "f12_b_augment.yml").read_text())  # hors f12_* : ignoré
    assert technical_bases(tmp_path) == [reference, _f12(augment=True)]
    assert _f12(augment=True) in technical_bases()  # configs/f12_b_augment.yml


@data_available
def test_noise_seed_with_f12_rule_refused_if_anything_else_changes():
    bad = load_config(LAG15[43])
    bad["train"]["augment"] = True
    with pytest.raises(ValueError, match="décision 43"):
        check(bad, CONFIGS / "variante.yml")


def test_technical_trial_writes_apart_from_reports():
    paths = output_paths(TECHNICAL, trial=False)
    assert paths["output"] == MODELS / "essai_technique_plafond"
    assert all(p.is_relative_to(paths["output"]) for p in paths.values())
    row = experiment_row({"train": {"training-data": "t.lst", "evaluation-data": "v.lst", "load": "m"}}, TECHNICAL,
                         paths["output"], "abc1234", False, datetime(2026, 9, 29, 17, 0))
    assert "(essai technique, non retenu)" in row


RULE = {"train": {"quit": "early", "lag": 3, "epochs": 6}}


@pytest.mark.parametrize("accuracy, config, trial, expected", [
    ([0.1, 0.2, 0.2, 0.2, 0.2], RULE, False, "lag"),                    # 3 époques sans progrès, 5 sur 6
    ([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], RULE, False, "plafond"),           # 6 époques, toujours en progrès
    ([0.1, 0.2, 0.3, 0.3, 0.3, 0.3], RULE, False, "lag et plafond"),    # égalité : pas un progrès
    ([0.1, 0.2, 0.3, 0.3, 0.3], {"train": {"quit": "early", "lag": 5}}, False, "inexpliqué (ni lag ni plafond)"),
    ([0.1], RULE, True, "nombre fixe d'époques"),                        # --trial : 1 époque fixe
])
def test_stop_reason(accuracy, config, trial, expected):
    # (c) raison de l'arrêt écrite dans run.json
    assert stop_reason(accuracy, config, trial) == expected


def test_planned_experiment_row_is_replaced_at_launch():
    text = "| a | b |\n| prévu | **f8_lag15_seed42** (prévu) : x |\n| c | d |\n"
    assert add_experiment_row(text, "| en cours |", "f8_lag15_seed42") == "| a | b |\n| en cours |\n| c | d |\n"
    assert add_experiment_row(text, "| en cours |", "autre").endswith("| c | d |\n| en cours |\n")
    with pytest.raises(ValueError, match="plusieurs"):
        add_experiment_row(text + "| prévu | **f8_lag15_seed42** (prévu) |\n", "| x |", "f8_lag15_seed42")
