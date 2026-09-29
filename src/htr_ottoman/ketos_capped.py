"""Lance `ketos train` avec l'arrêt anticipé et un plafond d'époques (F12, décision 43).

kraken 7.1.1 ne permet pas les deux à la fois : avec `--quit early`, `--epochs`
est ignoré sans avertissement (`max_epochs=-1`, kraken/ketos/recognition.py,
ligne 280), et avec `--quit fixed` l'arrêt anticipé n'est pas installé
(kraken/train/vgsl.py, `configure_callbacks`).

Ce lanceur exécute la ligne de commande de ketos dans le même processus, avec
exactement les mêmes arguments, et ne change qu'une chose : l'entraîneur
`kraken.train.KrakenTrainer`, importé par `ketos train` au moment du
lancement, est remplacé par une sous-classe qui transforme « pas de limite »
(-1) en la valeur de `--epochs`. Tout le reste est le code normal de kraken :
arrêt anticipé (patience `--lag`), checkpoints, conversion finale du meilleur
modèle en `best_<score>.safetensors`. Le plafond est lu dans les arguments
eux-mêmes (`--epochs`) : une seule source, la config.

Utilisé par `htr_ottoman.train` pour les configs de F12 à règle d'arrêt
« lag 15, plafond 150 » (décision 43) et leurs essais techniques, jamais pour
les configs à lag 5 (F8 et ses répétitions). Les hypothèses sur le code de
kraken sont vérifiées par `tests/test_ketos_capped.py`.

Usage (appelé par train) : python -m htr_ottoman.ketos_capped <options globales> train <options de train>
"""
import contextlib
import sys


def _value(args: list[str], option: str) -> str:
    """Valeur d'une option longue (`--quit early`) parmi les arguments de `train`."""
    values = [args[i + 1] for i, a in enumerate(args[:-1]) if a == option]
    if len(values) != 1:
        raise ValueError(f"ketos_capped : l'option {option} doit apparaître une fois dans les arguments de train")
    return values[0]


def cap_from_args(ketos_args: list[str]) -> int:
    """Plafond d'époques lu dans les arguments de `ketos ... train ...` : exige `--quit early`
    et `--epochs N` (N > 0) après la sous-commande `train`."""
    if "train" not in ketos_args:
        raise ValueError("ketos_capped ne lance que `ketos train`")
    train_args = ketos_args[ketos_args.index("train") + 1:]
    if _value(train_args, "--quit") != "early":
        raise ValueError("ketos_capped exige --quit early : le plafond s'ajoute à l'arrêt anticipé")
    cap = int(_value(train_args, "--epochs"))
    if cap <= 0:
        raise ValueError(f"ketos_capped : plafond d'époques invalide ({cap})")
    return cap


def capped_trainer(base: type, cap: int) -> type:
    """Sous-classe de l'entraîneur de kraken dont le nombre maximal d'époques est `cap`.
    Refuse un maximum déjà fixé (ce serait `--quit fixed`, sans arrêt anticipé)."""

    class CappedKrakenTrainer(base):
        def __init__(self, *args, max_epochs: int = -1, **kwargs):
            if max_epochs != -1:
                raise ValueError(f"ketos_capped : max_epochs déjà fixé à {max_epochs}, plafond non appliqué")
            super().__init__(*args, max_epochs=cap, **kwargs)

    CappedKrakenTrainer.cap = cap
    return CappedKrakenTrainer


@contextlib.contextmanager
def capped(cap: int):
    """Remplace `kraken.train.KrakenTrainer` le temps du bloc, puis le restaure."""
    import kraken.train

    base = kraken.train.KrakenTrainer
    kraken.train.KrakenTrainer = capped_trainer(base, cap)
    try:
        yield
    finally:
        kraken.train.KrakenTrainer = base


def run(ketos_args: list[str], standalone_mode: bool = True):
    """Exécute la ligne de commande de ketos avec le plafond lu dans ses arguments."""
    from kraken.ketos import cli

    cap = cap_from_args(ketos_args)
    with capped(cap):
        return cli.main(args=list(ketos_args), prog_name="ketos", standalone_mode=standalone_mode)


def main() -> None:
    run(sys.argv[1:])


if __name__ == "__main__":
    main()
