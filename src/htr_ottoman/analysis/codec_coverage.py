"""Couverture du codec du modèle de départ par les caractères de MAKHZAN (F6).

Chaque ligne transcrite est passée par `normalize` (sous cette forme qu'elle
sera donnée au modèle), puis ses caractères sont comptés par jeu (splits/) et
comparés au codec du modèle OpenITI. Les lignes annotées (décision 15), qui
seront exclues en F4, sont comptées à part.

Sortie : reports/codec_coverage.csv, une ligne par caractère présent dans
MAKHZAN ou dans le codec.

Usage : uv run python -m htr_ottoman.analysis.codec_coverage
"""
import unicodedata
from collections import Counter, defaultdict

import pandas as pd

from htr_ottoman.base_model import codec_labels, load
from htr_ottoman.config import MAKHZAN_LINES, REPORTS
from htr_ottoman.data.annotations import has_annotation
from htr_ottoman.normalize import normalize
from htr_ottoman.splits import SPLIT_NAMES, load_split

OUTPUT = REPORTS / "codec_coverage.csv"


def usable_lines() -> pd.DataFrame:
    """Lignes transcrites, texte normalisé, jeu et marqueur d'annotation."""
    lines = pd.read_parquet(MAKHZAN_LINES)
    lines = lines[~lines["is_empty"]].copy()
    split_of = {pid: name for name in SPLIT_NAMES for pid in load_split(name)["part_id"]}
    lines["split"] = lines["part_id"].map(split_of)
    if lines["split"].isna().any():
        raise ValueError("Des pages de la table des lignes n'ont pas de jeu dans splits/")
    lines["annotated"] = lines["text"].map(has_annotation)
    lines["norm"] = lines["text"].map(normalize)
    return lines


def coverage(lines: pd.DataFrame, codec: set[str]) -> pd.DataFrame:
    counts = defaultdict(Counter)  # colonne -> caractère -> occurrences
    n_lines = Counter()
    for row in lines.itertuples():
        chars = Counter(row.norm)
        key = "count_annotated_lines" if row.annotated else f"count_{row.split}"
        counts[key].update(chars)
        n_lines.update(chars.keys())

    chars = set(n_lines) | codec
    table = pd.DataFrame(
        {
            "codepoint": [f"U+{ord(c):04X}" for c in chars],
            "char": list(chars),
            "name": [unicodedata.name(c, "?") for c in chars],
            "category": [unicodedata.category(c) for c in chars],
            "in_codec": [c in codec for c in chars],
        }
    )
    cols = [f"count_{s}" for s in SPLIT_NAMES] + ["count_annotated_lines"]
    for col in cols:
        table[col] = table["char"].map(counts[col]).fillna(0).astype(int)
    table["count_total"] = table[cols].sum(axis=1)
    table["n_lines"] = table["char"].map(n_lines).fillna(0).astype(int)
    return table.sort_values(["in_codec", "count_total", "codepoint"], ascending=[True, False, True], ignore_index=True)


def main() -> None:
    codec = set(codec_labels(load()))
    if any(len(k) != 1 for k in codec):
        raise ValueError("Le codec contient des suites de plusieurs caractères : comparaison à adapter")
    lines = usable_lines()
    table = coverage(lines, codec)
    table.to_csv(OUTPUT, index=False, lineterminator="\n")

    kept = lines[~lines["annotated"]]
    in_makhzan = table[table["count_total"] > 0]
    unknown = in_makhzan[~in_makhzan["in_codec"]]
    print(f"Codec : {len(codec)} caractères. MAKHZAN normalisé : {len(in_makhzan)} caractères distincts, "
          f"{len(unknown)} inconnus du codec, {len(table) - len(in_makhzan)} caractères du codec jamais utilisés.")
    print(f"Lignes annotées (exclues en F4) : {lines['annotated'].sum()}\n")
    print("Lignes non annotées : part des caractères connus, lignes avec au moins un caractère inconnu")
    for name in SPLIT_NAMES:
        s = kept[kept["split"] == name]
        text = "".join(s["norm"])
        unk = sum(1 for c in text if c not in codec)
        bad = s["norm"].map(lambda t: any(c not in codec for c in t)).sum()
        print(f"  {name:13} {len(s):5} lignes  {100 * (1 - unk / len(text)):6.2f} % connus  "
              f"{bad:4} lignes touchées ({unk} caractères)")
    print("\nCaractères inconnus du codec :")
    cols = ["codepoint", "char", "name"] + [f"count_{s}" for s in SPLIT_NAMES] + ["count_annotated_lines"]
    print(unknown[cols].to_string(index=False))
    print(f"\n-> {OUTPUT.relative_to(OUTPUT.parents[1])}")


if __name__ == "__main__":
    main()
