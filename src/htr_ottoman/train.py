"""Fine-tuning kraken piloté par un fichier de configs/ (F8).

La config YAML a deux sections : `ketos` (options globales, placées avant
`train`) et `train` (options de `ketos train`). Les clés sont les noms longs des
options de ketos sans les tirets (`lrate`, `batch-size`, `reorder`...) ; les
chemins sont relatifs à la racine du projet. Une clé inconnue arrête tout : le
format natif de ketos (`--config`) ne ferait qu'avertir.

Garde-fous avant lancement :
- réglages de texte identiques à `prepare.KRAKEN_TEXT_OPTIONS` (décision 26) ;
- validation donnée explicitement, jamais le test interne, ni dans la config ni
  dans les manifestes (décisions 1 et 32) ;
- seed égale à `splits.SEED`, sauf pour les répétitions qui mesurent le bruit
  (seeds 43 et 44) : leur config doit être celle de F8 à la seed près
  (décision 42), ou celle de F8 avec la règle d'arrêt de F12 à la seed près
  (décision 43) ;
- règle d'arrêt : un plafond d'époques (`epochs` avec `quit: early`) n'est
  permis qu'avec la règle de F12, lag 15 et plafond 150 (décision 43), et un
  lag 15 exige ce plafond ; les configs `f8_lag15_seed<N>` doivent être celle
  de F8 avec cette règle et la seed N ; un essai technique
  (`essai_technique_*.yml`) doit être `f8_lag15_seed42` ou une variante
  versionnée (`configs/f12_*.yml`) à un plafond plus petit près (décision 43,
  complément du 2026-10-01) ;
- commande acceptée par ketos (analyse des options sans lancement) ;
- dossier de sortie absent ou vide : rien n'est écrasé ;
- tout le travail committé (hors EXPERIMENTS.md) : le commit enregistré décrit
  exactement le code lancé. Une ligne « en cours » avec ce commit est ajoutée à
  EXPERIMENTS.md dès le lancement, à compléter avec les résultats.

Le module ajoute la sortie (models/<config>/), le journal TensorBoard et `-v`
(journal texte lisible, sans barre de progression). Une config à plafond
(règle de F12) est lancée par `htr_ottoman.ketos_capped`, les autres par
`ketos`. Il écrit dans la sortie la commande exacte, une copie de la config, le
journal de ketos et run.json (commit, lanceur, plafond, raison de l'arrêt :
lag, plafond ou nombre fixe d'époques, horaires, durée de chaque phase, lignes
remplacées par kraken, avertissements du mode déterministe), puis les
métriques par époque et les courbes : reports/training/<config>.csv et
reports/figures/<config>_courbes.png. Un essai (`--trial`, 1 époque) écrit tout
dans models/<config>_essai/, et un essai technique (`essai_technique_*.yml`)
tout dans models/<config>/ : ni l'un ni l'autre ne touche reports/.
Au lancement, une ligne « prévu » d'EXPERIMENTS.md pour ce modèle est remplacée
par la ligne « en cours » ; sinon la ligne est ajoutée à la fin.

Usage :
  uv run python -m htr_ottoman.train configs/f8_finetune.yml           # entraînement complet
  uv run python -m htr_ottoman.train configs/f8_finetune.yml --trial   # essai court : 1 époque
  uv run python -m htr_ottoman.train configs/f8_finetune.yml --plot-only   # métriques et courbes seulement,
                                                                           # relues dans le journal existant
"""
import argparse
import contextlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from htr_ottoman.config import CONFIGS, EXPERIMENTS_LOG, FIGURES, MODELS, ROOT, TRAINING_REPORTS
from htr_ottoman.prepare import KRAKEN_TEXT_OPTIONS
from htr_ottoman.splits import SEED

SECTIONS = ("ketos", "train")
MANAGED = {"output", "logger", "log-dir", "verbose", "config", "partition"}  # réglés ici, interdits dans la config
TEXT_OPTIONS = {
    "normalization": KRAKEN_TEXT_OPTIONS["normalization"],
    "normalize-whitespace": KRAKEN_TEXT_OPTIONS["normalize_whitespace"],
    "reorder": KRAKEN_TEXT_OPTIONS["bidi_reordering"],
}
PATH_KEYS = ("load", "training-data", "evaluation-data")
MANIFEST_KEYS = ("training-data", "evaluation-data")
TRIAL = {"quit": "fixed", "epochs": 1, "min-epochs": 1}
TRIAL_SUFFIX = "_essai"
JOURNALS = {EXPERIMENTS_LOG.name}  # modifiés par les lancements, n'empêchent pas de lancer
REPLACED = "Replacing with sample"  # kraken remplace en silence une ligne illisible (skill kraken, section 10)
DETERMINISM_WARNING = "deterministic implementation"
FORBIDDEN_SPLIT = "test_interne"
# Répétitions de F8 avec une autre seed, pour mesurer le bruit entre entraînements (F12, décision 42)
NOISE_SEEDS = (43, 44)
NOISE_REFERENCE = CONFIGS / "f8_finetune.yml"
# Règle d'arrêt de F12 (décision 43) : arrêt anticipé, lag 15, plafond de 150 époques (ketos_capped)
F12_STOP = {"quit": "early", "lag": 15, "epochs": 150}
F12_REFERENCE = re.compile(r"f8_lag15_seed(\d+)")  # F8 avec la règle d'arrêt de F12, seed N
TECHNICAL_PREFIX = "essai_technique_"  # essais techniques : jamais utilisés dans F12, sorties dans models/<config>/
F12_VARIANTS = "f12_*.yml"  # configs des variantes de F12 (décision 42), base possible d'un essai technique
STOP_KEYS = ("quit", "lag", "epochs", "min-epochs")
PLANNED = "(prévu)"  # marque d'une ligne d'EXPERIMENTS.md écrite avant le lancement


def load_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict) or set(config) != set(SECTIONS):
        raise ValueError(f"{path} : sections attendues {SECTIONS}")
    return config


def _as_list(value) -> list:
    return value if isinstance(value, list) else [value]


def f8_config(seed: int = SEED, stop: dict | None = None) -> dict:
    """Config de F8, avec une autre seed et, au besoin, une autre règle d'arrêt."""
    config = load_config(NOISE_REFERENCE)
    config["ketos"]["seed"] = seed
    config["train"].update(stop or {})
    return config


def stop_rule(config: dict) -> dict:
    """Règle d'arrêt d'une config : quit, lag, plafond (epochs) et min-epochs."""
    return {key: config["train"].get(key) for key in STOP_KEYS}


def technical_bases(configs_dir: Path = CONFIGS) -> list[dict]:
    """Configs qu'un essai technique peut reprendre à un plafond plus petit près : f8_lag15_seed42 et
    les variantes de F12 (configs/f12_*.yml ; versionnées, car `git_commit` refuse de lancer sinon)."""
    return [f8_config(SEED, F12_STOP)] + [load_config(p) for p in sorted(configs_dir.glob(F12_VARIANTS))]


def check_stop_rule(config: dict, path: Path | None = None) -> None:
    """Plafond seulement avec la règle de F12, lag 15 seulement avec le plafond (décision 43)."""
    train, name = config["train"], path.stem if path else ""
    capped = train.get("quit") == "early" and train.get("epochs") is not None
    if capped and train.get("lag") != F12_STOP["lag"]:
        raise ValueError(f"Plafond d'époques réservé à la règle d'arrêt de F12, lag {F12_STOP['lag']} (décision 43)")
    if train.get("lag") == F12_STOP["lag"] and not capped:
        raise ValueError(f"Lag {F12_STOP['lag']} sans plafond : la règle de F12 exige {F12_STOP['epochs']} époques "
                         f"au plus (décision 43)")
    if name.startswith(TECHNICAL_PREFIX):
        cap = train.get("epochs")
        if not (capped and isinstance(cap, int) and 0 < cap < F12_STOP["epochs"]):
            raise ValueError("Essai technique : règle de F12 avec un plafond plus petit que 150")
        if config not in [{**base, "train": {**base["train"], "epochs": cap}} for base in technical_bases()]:
            raise ValueError("Essai technique : la config doit être f8_lag15_seed42 ou une variante "
                             f"configs/{F12_VARIANTS} à un plafond plus petit près")
    elif capped and train.get("epochs") != F12_STOP["epochs"]:
        raise ValueError(f"Plafond de {train.get('epochs')} époques : la règle de F12 est {F12_STOP['epochs']} "
                         f"(décision 43)")
    if match := F12_REFERENCE.fullmatch(name):
        if config != f8_config(int(match.group(1)), F12_STOP):
            raise ValueError(f"{name} doit être la config de F8 avec la règle d'arrêt de F12 et la seed "
                             f"{match.group(1)} (décision 43)")


def check(config: dict, path: Path | None = None) -> None:
    """Garde-fous de méthode, avant tout lancement. `path` : fichier de la config (son nom compte
    pour les configs de référence de F12 et les essais techniques)."""
    train = config["train"]
    for key, expected in TEXT_OPTIONS.items():
        if train.get(key) != expected:
            raise ValueError(f"train.{key} doit valoir {expected!r} (décision 26), trouvé {train.get(key)!r}")
    if "evaluation-data" not in train:
        raise ValueError("train.evaluation-data manquant : kraken couperait le train au hasard (-p)")
    check_stop_rule(config, path)
    seed = config["ketos"].get("seed")
    if seed in NOISE_SEEDS:
        if config not in (f8_config(seed), f8_config(seed, F12_STOP)):
            raise ValueError(f"Seed {seed} réservée aux répétitions : la config doit être {NOISE_REFERENCE.name} "
                             f"à la seed près (décision 42), ou avec la règle d'arrêt de F12 (décision 43)")
    elif seed != SEED:
        raise ValueError(f"ketos.seed doit valoir {SEED} (splits.SEED), ou {NOISE_SEEDS} pour les "
                         f"répétitions de F8 (décisions 42 et 43)")
    for key in PATH_KEYS:
        for value in _as_list(train.get(key)):
            if value is not None and not (ROOT / value).exists():
                raise FileNotFoundError(ROOT / value)
    texts = [yaml.safe_dump(config)]
    texts += [(ROOT / v).read_text() for key in MANIFEST_KEYS for v in _as_list(train.get(key)) if v]
    if any(FORBIDDEN_SPLIT in t for t in texts):
        raise ValueError("Le test interne apparaît dans la config ou un manifeste : il ne sert jamais au réglage")


def _command(section: str):
    from kraken.ketos import cli

    return cli if section == "ketos" else cli.get_command(None, "train")


def to_args(section: str, values: dict) -> list[str]:
    """Options d'une section en arguments de ligne de commande (noms longs)."""
    options = {o[2:]: p for p in _command(section).params for o in p.opts if o.startswith("--")}
    args = []
    for key, value in values.items():
        if key in MANAGED:
            raise ValueError(f"{section}.{key} est réglé par htr_ottoman.train : à retirer de la config")
        if key not in options:
            raise ValueError(f"Option inconnue de ketos : {section}.{key}")
        param = options[key]
        if param.is_flag:  # booléen : --reorder / --no-reorder
            if not isinstance(value, bool):
                raise ValueError(f"{section}.{key} doit valoir true ou false")
            if value:
                args.append(f"--{key}")
            elif param.secondary_opts:
                args.append(param.secondary_opts[0])
            continue
        for v in _as_list(value):
            args += [f"--{key}", str(v)]
    return args


def build_command(config: dict, output: Path, trial: bool = False) -> tuple[list[str], list[str]]:
    """Arguments globaux et arguments de `train`, sortie et journal TensorBoard compris."""
    train = {**config["train"], **(TRIAL if trial else {})}
    out = output.relative_to(ROOT) if output.is_relative_to(ROOT) else output
    global_args = ["-v"] + to_args("ketos", config["ketos"])
    train_args = to_args("train", train) + ["--output", str(out), "--logger", "tensorboard", "--log-dir", str(out / "logs")]
    return global_args, train_args


def validate_with_ketos(global_args: list[str], train_args: list[str]) -> None:
    """Analyse les options comme ketos le ferait (types, choix, fichiers existants), sans
    rien lancer. Les chemins relatifs sont lus depuis la racine, comme au lancement."""
    cli = _command("ketos")
    with contextlib.chdir(ROOT):
        ctx = cli.make_context("ketos", global_args + ["train"])
        _command("train").make_context("train", list(train_args), parent=ctx)


def uncommitted(porcelain: str) -> list[str]:
    """Fichiers modifiés ou non suivis d'après `git status --porcelain`, hors journaux."""
    paths = [line[3:] for line in porcelain.splitlines() if line.strip()]
    return [p for p in paths if p not in JOURNALS]


def git_commit() -> str:
    """Commit courant. Refuse de lancer si du travail n'est pas committé (hors journaux)."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout

    dirty = uncommitted(git("status", "--porcelain"))
    if dirty:
        raise RuntimeError(f"Travail non committé, à committer avant de lancer : {', '.join(dirty)}")
    return git("rev-parse", "--short", "HEAD").strip()


def output_paths(config_path: Path, trial: bool) -> dict[str, Path]:
    """Dossier de sortie, métriques et courbes. L'essai (--trial) et l'essai technique gardent
    tout dans leur propre dossier."""
    output = MODELS / (config_path.stem + (TRIAL_SUFFIX if trial else ""))
    if trial or config_path.stem.startswith(TECHNICAL_PREFIX):
        return {"output": output, "metrics": output / "metriques.csv", "figure": output / "courbes.png"}
    return {"output": output, "metrics": TRAINING_REPORTS / f"{output.name}.csv",
            "figure": FIGURES / f"{output.name}_courbes.png"}


def experiment_row(config: dict, config_path: Path, output: Path, commit: str, trial: bool, start: datetime) -> str:
    """Ligne « en cours » d'EXPERIMENTS.md, écrite au lancement."""
    train = config["train"]
    rel = lambda p: p.relative_to(ROOT) if p.is_relative_to(ROOT) else p  # noqa: E731
    kind = ("essai, 1 époque, non retenu" if trial else
            "essai technique, non retenu" if config_path.stem.startswith(TECHNICAL_PREFIX) else "entraînement")
    return (f"| {start:%Y-%m-%d} | {commit} | `{train['training-data']}` / `{train['evaluation-data']}` "
            f"(jeux compilés, anciens polygones) | `{train['load']}` | **{output.name}** ({kind}) : "
            f"`{rel(config_path)}`{' --trial' if trial else ''}, commande dans `{rel(output)}/commande.txt` "
            f"| en cours | non mesuré | Lancé à {start:%H:%M}, sortie `{rel(output)}/`. Résultats à compléter. |")


def add_experiment_row(text: str, row: str, name: str) -> str:
    """Remplace la ligne « prévu » du modèle `name` par `row`, ou ajoute `row` à la fin."""
    marker = f"**{name}** {PLANNED}"
    lines = text.rstrip("\n").split("\n")
    planned = [i for i, line in enumerate(lines) if marker in line]
    if len(planned) > 1:
        raise ValueError(f"EXPERIMENTS.md : plusieurs lignes prévues pour {name}")
    if planned:
        lines[planned[0]] = row
    else:
        lines.append(row)
    return "\n".join(lines) + "\n"


def cap_of(config: dict, trial: bool = False) -> int | None:
    """Plafond d'époques appliqué par ketos_capped (règle de F12), None sinon."""
    train = config["train"]
    if trial or train.get("quit") != "early":
        return None
    return train.get("epochs")


def launcher(config: dict, trial: bool = False) -> tuple[list[str], list[str]]:
    """Début de la commande : tel qu'affiché (commande.txt) et tel qu'exécuté. ketos_capped pour
    une config à plafond (règle de F12, décision 43), ketos sinon."""
    if cap_of(config, trial) is not None:
        module = ["-m", "htr_ottoman.ketos_capped"]
        return ["uv", "run", "python", *module], [sys.executable, *module]
    return ["uv", "run", "ketos"], [str(Path(sys.executable).with_name("ketos"))]


def stop_reason(accuracy: list[float], config: dict, trial: bool = False) -> str:
    """Raison de l'arrêt, d'après la précision de validation par époque : « lag » (le nombre
    d'époques sans progrès a atteint le lag), « plafond » (nombre maximal d'époques atteint),
    « lag et plafond » (les deux à la dernière époque), « nombre fixe d'époques » (--quit fixed),
    « inexpliqué » sinon (à examiner dans ketos.log)."""
    from htr_ottoman.analysis.seed_curves import epochs_without_progress

    train = {**config["train"], **(TRIAL if trial else {})}
    if train.get("quit") == "fixed":
        return "nombre fixe d'époques"
    by_lag = epochs_without_progress(accuracy)[-1] >= train["lag"]
    cap = cap_of(config, trial)
    by_cap = cap is not None and len(accuracy) >= cap
    if by_lag and by_cap:
        return "lag et plafond"
    if by_lag or by_cap:
        return "lag" if by_lag else "plafond"
    return "inexpliqué (ni lag ni plafond)"  # jamais d'erreur ici : l'entraînement est déjà fini


def read_metrics(log_dir: Path) -> pd.DataFrame:
    """Métriques par époque du journal TensorBoard : perte CTC du train (somme par lot, moyenne des lots),
    précision caractère de validation calculée par kraken (sans nos règles sur la
    prédiction, donc proche mais pas égale au CER de `evaluate`) et durées.
    `epoque` compte à partir de 1 ; le checkpoint kraken de l'époque n s'appelle
    checkpoint_{n-1}-….ckpt.

    Durées estimées d'après les horodatages : Lightning enregistre la perte tous
    les 50 pas ; la durée d'un pas est la moyenne entre le premier et le dernier
    enregistrement de l'époque, prolongée jusqu'au début et à la fin de l'époque.
    La validation va de la fin estimée de l'entraînement à l'enregistrement de
    val_accuracy. `debut_s` : début estimé de l'époque (horloge Unix)."""
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    runs = sorted({p.parent for p in log_dir.rglob("events.out.tfevents.*")})
    if len(runs) != 1:
        raise ValueError(f"{len(runs)} journaux TensorBoard dans {log_dir}, attendu 1")
    acc = EventAccumulator(str(runs[0]), size_guidance={"scalars": 0})
    acc.Reload()
    epoch_of = {e.step: int(e.value) for e in acc.Scalars("epoch")}

    def per_epoch(tag: str) -> pd.Series:
        return pd.Series({epoch_of[e.step] + 1: e.value for e in acc.Scalars(tag)}, name=tag)

    metrics = pd.concat([per_epoch("train_loss_epoch"), per_epoch("val_accuracy")], axis=1)
    metrics = metrics.rename_axis("epoque").reset_index().rename(columns={"train_loss_epoch": "perte_train"})
    metrics["cer_val_kraken"] = 1 - metrics["val_accuracy"]

    steps = pd.DataFrame([(epoch_of[e.step] + 1, e.step, e.wall_time) for e in acc.Scalars("train_loss_step")],
                         columns=["epoque", "pas", "t"])
    vals = pd.DataFrame([(epoch_of[e.step] + 1, e.step, e.wall_time) for e in acc.Scalars("val_accuracy")],
                        columns=["epoque", "pas", "t"]).set_index("epoque")
    timing, prev_end = [], 0
    for epoch in metrics["epoque"]:
        s = steps[steps["epoque"] == epoch].sort_values("pas")
        v = vals.loc[epoch]
        if len(s) < 2:
            timing.append((float("nan"),) * 3)
        else:
            per_step = (s["t"].iloc[-1] - s["t"].iloc[0]) / (s["pas"].iloc[-1] - s["pas"].iloc[0])
            start = s["t"].iloc[0] - (s["pas"].iloc[0] - prev_end) * per_step
            end = s["t"].iloc[-1] + (v["pas"] - s["pas"].iloc[-1]) * per_step
            timing.append((start, end - start, v["t"] - end))
        prev_end = v["pas"]
    metrics[["debut_s", "duree_train_s", "duree_val_s"]] = timing
    return metrics


def plot_curves(metrics: pd.DataFrame, title: str, path: Path) -> None:
    """Deux graphiques côte à côte (une mesure par axe) : perte d'entraînement, CER de validation."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    ink, muted, grid, surface, series = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb", "#2a78d6"
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True, facecolor=surface)
    panels = [("perte_train", 1, "Perte CTC du train (somme par lot de lignes)"), ("cer_val_kraken", 100, "CER de validation, kraken (%)")]
    for ax, (col, scale, label) in zip(axes, panels):
        ax.set_facecolor(surface)
        marker = "o" if len(metrics) <= 30 else None  # au-delà, les marqueurs se chevauchent
        ax.plot(metrics["epoque"], scale * metrics[col], color=series, lw=2, marker=marker, ms=4)
        ax.set_title(label, color=ink, fontsize=11, loc="left")
        ax.set_xlabel("époque", color=muted)
        if len(metrics) <= 12:  # une graduation par époque ; au-delà, des entiers espacés
            ax.set_xticks(metrics["epoque"])
        else:
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_xlim(metrics["epoque"].min() - 0.5, metrics["epoque"].max() + 0.5)
        ax.grid(True, color=grid, lw=1)
        ax.tick_params(colors=muted)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(grid)
    best = metrics.loc[metrics["cer_val_kraken"].idxmin()]
    first, last = metrics["epoque"].min(), metrics["epoque"].max()
    position = (best["epoque"] - first) / (last - first) if last > first else 0.5
    align = "right" if position > 0.66 else "left" if position < 0.33 else "center"  # reste dans le cadre
    axes[1].plot(best["epoque"], 100 * best["cer_val_kraken"], "o", ms=9, color=series, mec=surface, mew=2)
    axes[1].annotate(f"meilleure : époque {int(best['epoque'])}, {100 * best['cer_val_kraken']:.1f} %",
                     (best["epoque"], 100 * best["cer_val_kraken"]), xytext=(0, -12), textcoords="offset points",
                     ha=align, va="top", color=ink, fontsize=9)  # sous le minimum : jamais sur la courbe
    axes[1].margins(y=0.15)
    fig.suptitle(title, color=ink, fontsize=12, x=0.01, ha="left")
    fig.savefig(path, dpi=120, metadata={"Software": None})
    plt.close(fig)


def write_outputs(metrics: pd.DataFrame, paths: dict[str, Path]) -> None:
    """Métriques par époque (CSV) et courbes d'apprentissage."""
    for key in ("metrics", "figure"):
        paths[key].parent.mkdir(parents=True, exist_ok=True)
    metrics.drop(columns="debut_s").to_csv(paths["metrics"], index=False, lineterminator="\n", float_format="%.6f")
    plot_curves(metrics, f"{paths['output'].name} : fine-tuning du modèle de départ", paths["figure"])


def plot_only(config_path: Path, trial: bool = False) -> None:
    """Réécrit métriques et courbes depuis le journal TensorBoard d'un entraînement terminé."""
    paths = output_paths(config_path, trial)
    write_outputs(read_metrics(paths["output"] / "logs"), paths)
    print(f"-> {paths['metrics'].relative_to(ROOT)}, {paths['figure'].relative_to(ROOT)}")


def run(config_path: Path, trial: bool = False) -> Path:
    config = load_config(config_path)
    check(config, config_path)
    commit = git_commit()
    paths = output_paths(config_path, trial)
    output = paths["output"]
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"{output} n'est pas vide : rien n'est écrasé")
    global_args, train_args = build_command(config, output, trial)
    logs = output / "logs"
    logs.mkdir(parents=True, exist_ok=True)  # ketos exige que --log-dir existe
    try:
        validate_with_ketos(global_args, train_args)
    except Exception:
        logs.rmdir()  # dossiers vides créés ci-dessus, rien d'autre
        output.rmdir()
        raise

    shutil.copy(config_path, output / "config.yml")
    shown, executed = launcher(config, trial)
    command = [*shown, *global_args, "train", *train_args]
    (output / "commande.txt").write_text(shlex.join(command) + "\n")
    started = datetime.now()
    info = {"config": str(config_path.relative_to(ROOT)), "essai": trial, "commit": commit,
            "lanceur": shown[-1], "plafond": cap_of(config, trial),
            "debut": started.isoformat(timespec="seconds")}
    row = experiment_row(config, config_path, output, commit, trial, started)
    EXPERIMENTS_LOG.write_text(add_experiment_row(EXPERIMENTS_LOG.read_text(), row, output.name))
    print(f"EXPERIMENTS.md : ligne « en cours » ajoutée (commit {commit})")
    print(shlex.join(command), flush=True)

    start = time.time()
    with open(output / "ketos.log", "w") as log:
        proc = subprocess.Popen([*executed, *global_args, "train", *train_args], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        code = proc.wait()
    end = time.time()
    log_text = (output / "ketos.log").read_text()
    info.update(fin=datetime.now().isoformat(timespec="seconds"), code_retour=code,
                lignes_remplacees=log_text.count(REPLACED),
                avertissements_determinisme=log_text.count(DETERMINISM_WARNING))
    metrics = read_metrics(logs) if code == 0 else None
    if metrics is not None:
        info["epoques"] = len(metrics)
        info["arret"] = stop_reason(metrics["val_accuracy"].tolist(), config, trial)
        load_s = metrics["debut_s"].iloc[0] - start  # préparation des jeux par kraken, avant la 1re époque
        train_s, val_s = metrics["duree_train_s"].sum(), metrics["duree_val_s"].sum()
        info["durees_min"] = {k: round(float(v) / 60, 2) for k, v in {
            "chargement": load_s, "entrainement": train_s, "validation": val_s,
            "reste": end - start - load_s - train_s - val_s,  # sauvegardes, conversion du meilleur modèle
            "total": end - start}.items()}
    (output / "run.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    if code != 0:
        raise SystemExit(f"ketos s'est arrêté avec le code {code} : voir {output / 'ketos.log'}")

    write_outputs(metrics, paths)
    best = sorted(output.glob("best_*.safetensors"))
    print(metrics.drop(columns="debut_s").to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"Durées (min) : {info['durees_min']}")
    print(f"Arrêt : {info['arret']} ({info['epoques']} époques ; lanceur {info['lanceur']}, plafond {info['plafond']})")
    print(f"Lignes remplacées par kraken : {info['lignes_remplacees']} ; "
          f"avertissements du mode déterministe : {info['avertissements_determinisme']}")
    print(f"Meilleur modèle : {', '.join(str(p.relative_to(ROOT)) for p in best)}")
    print(f"-> {paths['metrics'].relative_to(ROOT)}, {paths['figure'].relative_to(ROOT)}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--trial", action="store_true", help="essai court : 1 époque, sortie models/<config>_essai/")
    parser.add_argument("--plot-only", action="store_true", help="métriques et courbes seulement, sans entraîner")
    args = parser.parse_args()
    if args.plot_only:
        plot_only(args.config.resolve(), args.trial)
    else:
        run(args.config.resolve(), args.trial)


if __name__ == "__main__":
    main()
