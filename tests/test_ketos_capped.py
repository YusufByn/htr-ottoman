"""Tests de htr_ottoman.ketos_capped (décision 43) : hypothèses sur le code de kraken 7.1.1,
lecture du plafond, et lancement de `ketos train` sans entraînement, comparé à un lancement normal."""
import importlib.metadata
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from htr_ottoman import ketos_capped
from htr_ottoman.config import BASE_MODEL, CONFIGS, MAKHZAN_PROCESSED, ROOT
from htr_ottoman.train import build_command, load_config


def _line(module, number: int) -> str:
    return Path(inspect.getfile(module)).read_text().splitlines()[number - 1].strip()


def test_kraken_code_the_launcher_relies_on():
    # (a) Si kraken change, ces lignes changent : le lanceur doit être revu avant tout entraînement.
    from kraken.ketos import recognition
    from kraken.train import vgsl

    assert importlib.metadata.version("kraken") == "7.1.1"
    assert _line(recognition, 280) == "max_epochs=m_config.epochs if m_config.quit == 'fixed' else -1,"
    assert _line(recognition, 214) == "from kraken.train import KrakenTrainer"  # importé au lancement
    assert _line(vgsl, 622) == "if self.hparams.config.quit == 'early':"
    assert _line(vgsl, 625) == "patience=self.hparams.config.lag,"
    assert _line(recognition, 319) == "score = checkpoint_callback.best_model_score.item()"  # conversion finale


@pytest.mark.parametrize("args, cap", [
    (["-v", "--seed", "42", "train", "--quit", "early", "--lag", "15", "--epochs", "150"], 150),
    (["train", "--epochs", "2", "--quit", "early"], 2),
])
def test_cap_is_read_from_the_train_arguments(args, cap):
    assert ketos_capped.cap_from_args(args) == cap


@pytest.mark.parametrize("args, message", [
    (["train", "--quit", "fixed", "--epochs", "150"], "--quit early"),
    (["train", "--quit", "early", "--lag", "15"], "--epochs"),
    (["train", "--quit", "early", "--epochs", "0"], "invalide"),
    (["train", "--quit", "early", "--epochs", "5", "--epochs", "6"], "une fois"),
    (["test", "--quit", "early", "--epochs", "150"], "ketos train"),
])
def test_cap_refused(args, message):
    with pytest.raises(ValueError, match=message):
        ketos_capped.cap_from_args(args)


class _Base:
    def __init__(self, *args, max_epochs=100, **kwargs):
        self.max_epochs, self.kwargs = max_epochs, kwargs


def test_capped_trainer_replaces_no_limit_only():
    trainer_cls = ketos_capped.capped_trainer(_Base, 150)
    trainer = trainer_cls(max_epochs=-1, min_epochs=5)
    assert trainer.max_epochs == 150 and trainer.kwargs == {"min_epochs": 5}
    with pytest.raises(ValueError, match="déjà fixé"):
        trainer_cls(max_epochs=1)  # --quit fixed : pas d'arrêt anticipé, le lanceur refuse


def test_capped_context_restores_kraken_trainer():
    import kraken.train

    original = kraken.train.KrakenTrainer
    with ketos_capped.capped(150):
        assert kraken.train.KrakenTrainer is not original and kraken.train.KrakenTrainer.cap == 150
    assert kraken.train.KrakenTrainer is original


data_available = pytest.mark.skipif(
    not (BASE_MODEL.exists() and (MAKHZAN_PROCESSED / "train.lst").exists()),
    reason="modèle de départ ou jeux compilés absents",
)


class _Stop(Exception):
    """Interrompt `ketos train` juste avant l'entraînement."""


def _describe(value):
    """Valeur comparable d'un argument : les callbacks sont décrits par leur classe et leurs réglages simples."""
    if isinstance(value, list):
        return [_describe(v) for v in value]
    if hasattr(value, "__dict__") and not isinstance(value, (str, int, float, bool, Path)):
        simple = (str, int, float, bool, type(None), Path)
        return type(value).__name__, {k: v for k, v in vars(value).items() if isinstance(v, simple)}
    return value


class _WeightlessModel:
    """Tient lieu du modèle chargé : sans poids, avec la vraie méthode de kraken qui installe
    l'arrêt anticipé d'après la config de l'entraînement."""

    def __init__(self, config):
        self.hparams = SimpleNamespace(config=config)


def _launch_without_training(monkeypatch, args: list[str], capped: bool) -> dict:
    """Lance `ketos train` (normal ou par ketos_capped) dans ce processus. Ni le jeu ni les poids ne
    sont chargés (plusieurs minutes), et l'entraînement est remplacé par un relevé : arguments reçus
    par l'entraîneur de kraken, nombre maximal d'époques, callbacks d'arrêt installés par le modèle."""
    import lightning as L
    from kraken.ketos import cli
    from kraken.train import utils
    from kraken.train.vgsl import VGSLRecognitionDataModule, VGSLRecognitionModel

    _WeightlessModel.configure_callbacks = VGSLRecognitionModel.configure_callbacks

    seen = {}
    original_init = utils.KrakenTrainer.__init__

    def spy_init(self, *a, **kwargs):
        seen["kwargs"] = dict(kwargs)
        original_init(self, *a, **kwargs)

    def light_data_module(self, data_config):  # le vrai charge tout le jeu (environ 7 min)
        L.LightningDataModule.__init__(self)

    def no_fit(self, model, *a, **kwargs):
        seen.update(max_epochs=self.max_epochs, min_epochs=self.min_epochs, callbacks=model.configure_callbacks())
        raise _Stop

    monkeypatch.setattr(utils.KrakenTrainer, "__init__", spy_init)
    monkeypatch.setattr(utils.KrakenTrainer, "fit", no_fit)
    monkeypatch.setattr(VGSLRecognitionDataModule, "__init__", light_data_module)
    monkeypatch.setattr(VGSLRecognitionModel, "load_from_weights",
                        classmethod(lambda cls, path, config, **kw: _WeightlessModel(config)))
    with pytest.raises(_Stop):
        if capped:
            ketos_capped.run(args, standalone_mode=False)
        else:
            cli.main(args=args, prog_name="ketos", standalone_mode=False)
    return seen


@pytest.fixture
def restore_torch_determinism():
    import torch

    yield
    torch.use_deterministic_algorithms(False)  # réglage global posé par --deterministic


@data_available
def test_launch_without_training_matches_plain_ketos(monkeypatch, tmp_path, restore_torch_determinism):
    # (b) Même commande que train pour la référence de F12 : seul le nombre maximal d'époques change.
    monkeypatch.chdir(ROOT)
    config = load_config(CONFIGS / "f8_lag15_seed42.yml")
    (tmp_path / "logs").mkdir()  # ketos exige que --log-dir existe
    global_args, train_args = build_command(config, tmp_path)
    args = [*global_args, "train", *train_args]  # mêmes arguments pour les deux lancements
    runs = {capped: _launch_without_training(monkeypatch, args, capped) for capped in (False, True)}
    plain, capped_run = runs[False], runs[True]
    assert plain["max_epochs"] == -1  # ketos seul : --epochs ignoré avec --quit early
    assert capped_run["max_epochs"] == 150 and capped_run["kwargs"]["max_epochs"] == 150
    assert plain["min_epochs"] == capped_run["min_epochs"] == 5
    for seen in (plain, capped_run):
        stops = [cb for cb in seen["callbacks"] if type(cb).__name__ == "EarlyStopping"]
        assert len(stops) == 1
        assert (stops[0].patience, stops[0].monitor, stops[0].mode) == (15, "val_accuracy", "max")
    others = lambda kw: {k: _describe(v) for k, v in kw.items() if k != "max_epochs"}  # noqa: E731
    assert others(capped_run["kwargs"]) == others(plain["kwargs"])
