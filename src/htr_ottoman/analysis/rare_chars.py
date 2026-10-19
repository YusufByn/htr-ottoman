"""F13, Q7 : caractères du train absents de la validation, et caractères du test interne absents du train.

- Groupe « train sans validation » : caractères du train compilé de F8 (`train.arrow`,
  aussi celui de F8 lag 15) qui n'apparaissent pas dans la validation ; aucun modèle
  n'y est donc mesuré pendant le réglage.
- Groupe « test sans train » : caractères de la vérité terrain du test interne absents
  du train compilé ; `dans_codec` dit si le modèle de départ, donc tout modèle affiné
  avec `--resize fail`, peut les écrire (lu dans reports/codec_coverage.csv, sans
  charger de modèle). Le ZWNJ en fait partie (décision 23, F13 Q2).
- Occurrences par jeu : train compilé, validation, test interne (vérité terrain
  normalisée d'`evaluate`).
- Lecture sur le test interne, baseline et F8 (lag 5), prédictions déjà sauvegardées
  (`reports/<modèle>/test_interne/lignes.parquet`), exploratoire et descriptif
  (décision 39) : pour chaque caractère, occurrences de référence lues correctement
  (alignées sur le même caractère), supprimées ou remplacées, et nombre de fois où le
  modèle l'écrit. Alignement d'`analysis.error_analysis.align` (celui d'`evaluate`),
  vérifié ligne par ligne contre les S, D, I d'`evaluate`.
- Aucun modèle chargé, aucune prédiction faite.

Sorties (reports/f13/q7_caracteres/) : occurrences.csv, test_interne_lecture.csv.

Usage : uv run python -m htr_ottoman.analysis.rare_chars
"""
import unicodedata
from collections import Counter

import pandas as pd

from htr_ottoman.analysis.error_analysis import align
from htr_ottoman.config import REPORTS, ROOT
from htr_ottoman.prepare import read_arrow

OUTPUT = REPORTS / "f13" / "q7_caracteres"
CODEC_REPORT = REPORTS / "codec_coverage.csv"
VAL_LINES = REPORTS / "f8_finetune" / "val" / "lignes.parquet"
TEST_MODELS = {"baseline": REPORTS / "baseline" / "test_interne" / "lignes.parquet",
               "f8_finetune": REPORTS / "f8_finetune" / "test_interne" / "lignes.parquet"}
TRAIN_ONLY, TEST_ONLY = "train sans validation", "test sans train"
NOTE = "exploratoire, décision 39 (prédictions sauvegardées, descriptif)"


def char_name(c: str) -> str:
    return unicodedata.name(c, f"U+{ord(c):04X}")


def codec_flags() -> dict[str, bool]:
    table = pd.read_csv(CODEC_REPORT, keep_default_na=False)
    return dict(zip(table["char"], table["in_codec"]))


def check_alignment(lines: pd.DataFrame, source: str) -> None:
    """Les S, D, I de l'alignement doivent être ceux d'`evaluate`, ligne par ligne."""
    for line in lines.itertuples():
        pairs = align(line.ref_norm, line.hyp_norm)
        n = Counter("S" if r and h and r != h else "D" if r and not h else "I" if h and not r else "="
                    for r, h in pairs)
        if (n["S"], n["D"], n["I"]) != (line.substitutions, line.deletions, line.insertions):
            raise ValueError(f"{source}, ligne {line.line_id} : alignement différent de celui d'evaluate")


def occurrences() -> pd.DataFrame:
    train_texts, _ = read_arrow("train")
    val = pd.read_parquet(VAL_LINES)
    test = pd.read_parquet(TEST_MODELS["f8_finetune"])
    counts = {"train": Counter("".join(train_texts)), "val": Counter("".join(val["ref_norm"])),
              "test_interne": Counter("".join(test["ref_norm"]))}
    groups = {c: TRAIN_ONLY for c in set(counts["train"]) - set(counts["val"])}
    groups |= {c: TEST_ONLY for c in set(counts["test_interne"]) - set(counts["train"])}
    flags = codec_flags()
    if missing := sorted(set(groups) - set(flags)):
        raise ValueError(f"Caractères absents de {CODEC_REPORT.name} : {missing}")
    docs = test.assign(chars=test["ref_norm"].map(set))
    rows = []
    for c, group in groups.items():
        in_docs = sorted(docs.loc[docs["chars"].map(lambda s: c in s), "doc_id"].unique())
        rows.append({
            "groupe": group, "codepoint": f"U+{ord(c):04X}", "caractere": c, "nom": char_name(c),
            "dans_codec": bool(flags[c]),
            **{f"occurrences_{name}": counts[name][c] for name in counts},
            "manuscrits_test_interne": " ".join(map(str, in_docs)),
        })
    return pd.DataFrame(rows).sort_values(["groupe", "codepoint"], ignore_index=True)


def reading(chars: list[str]) -> pd.DataFrame:
    """Lecture de chaque caractère par la baseline et F8 (lag 5) sur le test interne."""
    rows = []
    for model, path in TEST_MODELS.items():
        lines = pd.read_parquet(path)
        check_alignment(lines, str(path.relative_to(ROOT)))
        pairs = [p for line in lines.itertuples() for p in align(line.ref_norm, line.hyp_norm)]
        for c in chars:
            replaced = Counter(h for r, h in pairs if r == c and h and h != c)
            rows.append({
                "modele": model, "codepoint": f"U+{ord(c):04X}", "caractere": c,
                "reference": sum(r == c for r, _ in pairs),
                "lus": sum(r == c and h == c for r, h in pairs),
                "supprimes": sum(r == c and not h for r, h in pairs),
                "remplaces": sum(replaced.values()),
                "remplaces_le_plus_par": " ".join(f"{char_name(h)} ×{n}" for h, n in replaced.most_common(3)),
                "ecrits_par_le_modele": sum(h == c for _, h in pairs),
                "note": NOTE,
            })
    return pd.DataFrame(rows)


def main() -> None:
    occ = occurrences()
    read = reading([c for c, n in zip(occ["caractere"], occ["occurrences_test_interne"]) if n > 0])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    occ.to_csv(OUTPUT / "occurrences.csv", index=False, lineterminator="\n")
    read.to_csv(OUTPUT / "test_interne_lecture.csv", index=False, lineterminator="\n")
    with pd.option_context("display.width", 250, "display.max_columns", 20):
        print(occ.to_string(index=False))
        print(read.drop(columns="note").to_string(index=False))
    print(f"-> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
