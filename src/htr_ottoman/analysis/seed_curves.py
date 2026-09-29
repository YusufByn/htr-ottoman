"""Diagnostic des courbes de validation des répétitions de F8 (F12, décision 42).

Relit seulement les métriques par époque déjà écrites par `train`
(reports/training/<config>.csv) : aucun entraînement, aucune prédiction.
Mesure : CER de validation calculé par kraken à chaque époque
(1 − précision caractère), proche du CER d'`evaluate` (0,01 à 0,07 point
d'écart pour ces trois modèles).

- À époque égale : CER de chaque seed et écart entre seeds (max moins min des
  seeds qui ont atteint l'époque), brut et « meilleur jusque-là » (le CER que
  garderait un entraînement arrêté à cette époque).
- Oscillations : variation absolue du CER d'une époque à la suivante, sur
  toute la courbe et sur les 20 dernières époques.
- Arrêts simulés : règle de l'arrêt anticipé de kraken (une époque compte comme
  un progrès si la précision dépasse strictement la meilleure précédente ;
  arrêt quand le nombre d'époques sans progrès atteint le lag, pas avant
  min-epochs). Pour chaque lag : déclenchements avant la meilleure époque de la
  seed, premier déclenchement, plus longue série sans progrès avant la
  meilleure époque. Contrôle : avec le lag de F8 (5), la simulation retrouve
  l'époque d'arrêt réelle. Les courbes s'arrêtent à ce lag 5 : un lag plus long
  ne peut être simulé qu'à l'intérieur des époques enregistrées.

Sorties : reports/bruit/f8_finetune/{epoques_egales,oscillations,arrets}.csv,
reports/figures/f12_bruit_seeds.png.

Usage : uv run python -m htr_ottoman.analysis.seed_curves
"""
import pandas as pd

from htr_ottoman.config import FIGURES, REPORTS, ROOT, TRAINING_REPORTS

RUNS = {42: "f8_finetune", 43: "f8_finetune_seed43", 44: "f8_finetune_seed44"}  # seed -> config
EPOCHS = [10, 30, 44, 49, 71]  # 49 : arrêt de la seed 44
LAGS = [5, 10, 15]
TRAINED_LAG, MIN_EPOCHS = 5, 5  # configs/f8_finetune.yml
LAST_EPOCHS = 20
OUTPUT = REPORTS / "bruit" / "f8_finetune"
FIGURE = FIGURES / "f12_bruit_seeds.png"
LABEL_BELOW = {44}  # sur le zoom, l'étiquette au bout de la courbe couvrirait les autres courbes


def load_curves(runs: dict[int, str] = RUNS) -> dict[int, pd.DataFrame]:
    """Métriques par époque de chaque seed (époques 1, 2, ... sans trou)."""
    curves = {}
    for seed, config in runs.items():
        m = pd.read_csv(TRAINING_REPORTS / f"{config}.csv")
        if m["epoque"].tolist() != list(range(1, len(m) + 1)):
            raise ValueError(f"{config} : époques manquantes ou désordonnées")
        curves[seed] = m
    return curves


def epochs_without_progress(accuracy: list[float]) -> list[int]:
    """Pour chaque époque, nombre d'époques écoulées depuis le dernier progrès strict."""
    best, count, out = float("-inf"), 0, []
    for a in accuracy:
        if a > best:
            best, count = a, 0
        else:
            count += 1
        out.append(count)
    return out


def stop_triggers(accuracy: list[float], lag: int, min_epochs: int = MIN_EPOCHS) -> list[int]:
    """Époques (à partir de 1) où un arrêt anticipé de patience `lag` se déclencherait,
    si l'entraînement continuait après chaque déclenchement."""
    return [e for e, n in enumerate(epochs_without_progress(accuracy), 1) if n == lag and e >= min_epochs]


def longest_stall(accuracy: list[float], before: int) -> tuple[int, int | None]:
    """Plus longue série d'époques sans progrès avant l'époque `before` : longueur et époque
    où elle atteint cette longueur pour la première fois (None si aucune)."""
    counts = epochs_without_progress(accuracy)[: before - 1]
    length = max([0] + counts)
    return length, (counts.index(length) + 1 if length else None)


def best_so_far(cer: pd.Series) -> pd.Series:
    return cer.cummin()


def equal_epochs(curves: dict[int, pd.DataFrame], epochs: list[int] = EPOCHS) -> pd.DataFrame:
    rows = {}
    for e in epochs:
        row = {}
        for kind, transform in [("brut", lambda s: s), ("meilleur", best_so_far)]:
            values = {seed: transform(m["cer_val_kraken"]).iloc[e - 1] for seed, m in curves.items() if len(m) >= e}
            for seed in curves:
                row[f"cer_{kind}_seed{seed}"] = values.get(seed, float("nan"))
            row[f"ecart_{kind}"] = max(values.values()) - min(values.values()) if len(values) > 1 else float("nan")
        row["seeds"] = sum(len(m) >= e for m in curves.values())
        rows[e] = row
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("epoque")


def oscillations(curves: dict[int, pd.DataFrame], last: int = LAST_EPOCHS) -> pd.DataFrame:
    rows = {}
    for seed, m in curves.items():
        jumps = m["cer_val_kraken"].diff().abs().dropna()
        tail = jumps.iloc[-(last - 1):]  # variations entre les `last` dernières époques
        rows[seed] = {"epoques": len(m), "mediane": jumps.median(), "moyenne": jumps.mean(), "max": jumps.max(),
                      f"mediane_{last}_dernieres": tail.median(), f"max_{last}_dernieres": tail.max()}
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("seed")


def stops(curves: dict[int, pd.DataFrame], lags: list[int] = LAGS) -> pd.DataFrame:
    rows = []
    for seed, m in curves.items():
        acc = m["val_accuracy"].tolist()
        best = int(m.loc[m["val_accuracy"].idxmax(), "epoque"])
        stall, stall_end = longest_stall(acc, best)
        for lag in lags:
            triggers = stop_triggers(acc, lag)
            first = triggers[0] if triggers else None
            rows.append({
                "seed": seed, "lag": lag, "epoques": len(m), "meilleure_epoque": best,
                "declenchements_avant_meilleure": sum(t < best for t in triggers),
                "premier_declenchement": first,
                "cer_garde_au_premier": m["cer_val_kraken"].iloc[: first].min() if first else float("nan"),
                "plus_longue_serie_sans_progres_avant_meilleure": stall,
                "fin_de_cette_serie": stall_end,
                "cer_garde_a_cette_epoque": m["cer_val_kraken"].iloc[: stall_end].min() if stall_end else float("nan"),
            })
    out = pd.DataFrame(rows).set_index(["seed", "lag"])
    trained = out.xs(TRAINED_LAG, level="lag")
    if not (trained["premier_declenchement"] == trained["epoques"]).all():
        raise ValueError("La simulation avec le lag de F8 ne retrouve pas les arrêts réels")
    for col in ("premier_declenchement", "fin_de_cette_serie"):
        out[col] = out[col].astype("Int64")
    return out


def plot(curves: dict[int, pd.DataFrame], path=FIGURE) -> None:
    """CER kraken par époque des trois seeds : courbe entière et zoom sur la fin (même mesure)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    colors = dict(zip(curves, ["#2a78d6", "#eb6834", "#1baf7a"]))  # ordre fixe de la palette
    names = {42: "seed 42 (F8)", 43: "seed 43", 44: "seed 44"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), constrained_layout=True, facecolor=surface,
                             gridspec_kw={"width_ratios": [1, 1.3]})
    for ax, zoom in zip(axes, (False, True)):
        ax.set_facecolor(surface)
        for seed, m in curves.items():
            data = m[m["epoque"] >= 30] if zoom else m
            ax.plot(data["epoque"], 100 * data["cer_val_kraken"], color=colors[seed], lw=2, label=names[seed])
            best = m.loc[m["cer_val_kraken"].idxmin()]
            ax.plot(best["epoque"], 100 * best["cer_val_kraken"], "o", ms=8, color=colors[seed], mec=surface, mew=2)
            if zoom:
                end = m.iloc[-1]
                label = (f"{names[seed]} : arrêt {int(end['epoque'])}, meilleure {int(best['epoque'])} "
                         f"({100 * best['cer_val_kraken']:.2f} %)")
                if seed in LABEL_BELOW:  # arrêt précoce : étiquette dans la zone vide, reliée au meilleur point
                    ax.annotate(label, (best["epoque"], 100 * best["cer_val_kraken"]), xytext=(0.03, 0.07),
                                textcoords="axes fraction", va="center", color=ink, fontsize=8.5,
                                arrowprops={"arrowstyle": "-", "color": muted, "lw": 0.8})
                else:
                    ax.annotate(label, (end["epoque"], 100 * end["cer_val_kraken"]), xytext=(6, 0),
                                textcoords="offset points", va="center", color=ink, fontsize=8.5)
        ax.set_title("Courbe entière" if not zoom else "Zoom : époques 30 et suivantes (point : meilleure époque)",
                     color=ink, fontsize=10.5, loc="left")
        ax.set_xlabel("époque", color=muted)
        ax.set_ylabel("CER de validation, kraken (%)", color=muted)
        ax.grid(True, color=grid, lw=1)
        ax.tick_params(colors=muted)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(grid)
    axes[1].set_xlim(29, 128)  # place pour les étiquettes à droite des courbes
    axes[0].legend(frameon=False, labelcolor=ink, fontsize=9)
    fig.suptitle("F12 : répétitions de F8 (mêmes réglages, seeds 42, 43, 44), CER de validation par époque",
                 color=ink, fontsize=12, x=0.01, ha="left")
    fig.savefig(path, dpi=120, metadata={"Software": None})
    plt.close(fig)


def tables(curves: dict[int, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {"epoques_egales": equal_epochs(curves), "oscillations": oscillations(curves), "arrets": stops(curves)}


def write_tables(out: dict[str, pd.DataFrame], output_dir=OUTPUT) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, table in out.items():
        table.to_csv(output_dir / f"{name}.csv", lineterminator="\n", float_format="%.6f")


def main() -> None:
    curves = load_curves()
    out = tables(curves)
    write_tables(out)
    pd.set_option("display.width", 250)
    for name, table in out.items():
        print(f"== {name}\n{table.to_string(float_format=lambda x: f'{x:.4f}')}\n")
    plot(curves)
    print(f"-> {OUTPUT.relative_to(ROOT)}, {FIGURE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
