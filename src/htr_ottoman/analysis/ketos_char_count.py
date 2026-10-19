"""F13, Q2 : écart entre le nombre de caractères de `ketos test` et celui d'`evaluate`.

`evaluate` compte les caractères de la vérité terrain passée par `normalize`
(`ref_chars`). `ketos test` compte ceux de la vérité terrain après ses propres
transformations du texte, appliquées au chargement du jeu compilé (`-u NFD -n
--reorder`, comme en F9 : `final_eval.ketos_test_command`) :
`Counter(''.join(batch['target']))`, kraken/train/vgsl.py.

Le module applique ces transformations avec la classe de jeu de kraken
(`ArrowIPCRecognitionDataset._apply_text_transform`) au texte normalisé de
chaque ligne compilée (`prepare.select_lines`), vérifie que ces textes sont
exactement ceux du jeu compilé, puis compare les longueurs ligne par ligne.
Vérité terrain seulement : aucun modèle chargé, aucune prédiction (le test
interne reste clos, décision 39 ; sorties exploratoires, F13).

Sorties (reports/f13/q2_ketos_evaluate/) : resume.csv (un jeu par ligne) et
lignes_differentes.csv (lignes dont la longueur change, caractères perdus ou
ajoutés, transformation responsable).

Usage : uv run python -m htr_ottoman.analysis.ketos_char_count
"""
import unicodedata
from collections import Counter

import pandas as pd

from htr_ottoman.config import REPORTS, ROOT
from htr_ottoman.prepare import KRAKEN_TEXT_OPTIONS, read_arrow, select_lines

SPLITS = ("val", "test_interne")
OUTPUT = REPORTS / "f13" / "q2_ketos_evaluate"
NOTE = {"val": "", "test_interne": "exploratoire, décision 39 (vérité terrain seulement)"}


def kraken_text_steps():
    """Transformations du texte de `ketos test`, dans l'ordre de kraken, avec leur nom."""
    from kraken.lib import functional_im_transforms as F_t

    return [
        ("NFD", lambda t: F_t.text_normalize(t, KRAKEN_TEXT_OPTIONS["normalization"])),
        ("-n", F_t.text_whitespace_normalize),
        ("BiDi", F_t.text_reorder),
    ]


def kraken_text(text: str) -> str:
    """Texte de référence tel que `ketos test` le compte (classe de jeu de kraken, réglages de F9)."""
    from kraken.lib.dataset import ArrowIPCRecognitionDataset

    ds = ArrowIPCRecognitionDataset(normalization=KRAKEN_TEXT_OPTIONS["normalization"],
                                    whitespace_normalization=KRAKEN_TEXT_OPTIONS["normalize_whitespace"],
                                    reorder=KRAKEN_TEXT_OPTIONS["bidi_reordering"])
    return ds._apply_text_transform(text)


def responsible_step(text: str) -> str:
    """Première transformation qui change la longueur du texte."""
    for name, step in kraken_text_steps():
        new = step(text)
        if len(new) != len(text):
            return name
        text = new
    return ""


def describe(chars: Counter) -> str:
    return " ".join(f"U+{ord(c):04X} {unicodedata.name(c, '?')} ×{n}" for c, n in sorted(chars.items()))


def split_table(name: str) -> tuple[dict, pd.DataFrame]:
    lines = select_lines()
    lines = lines[(lines["split"] == name) & lines["exclusion"].isna()].copy()
    compiled, _ = read_arrow(name)
    if Counter(compiled) != Counter(lines["norm"]):
        raise ValueError(f"{name} : textes compilés différents des textes normalisés attendus")
    lines["kraken"] = lines["norm"].map(kraken_text)
    lines["caracteres_evaluate"] = lines["norm"].str.len()
    lines["caracteres_ketos"] = lines["kraken"].str.len()
    diff = lines[lines["caracteres_evaluate"] != lines["caracteres_ketos"]]
    rows = pd.DataFrame({
        "jeu": name,
        "doc_id": diff["doc_id"],
        "part_id": diff["part_id"],
        "line_id": diff["line_id"],
        "ecriture": diff["script"],
        "caracteres_evaluate": diff["caracteres_evaluate"],
        "caracteres_ketos": diff["caracteres_ketos"],
        "perdus": [describe(Counter(a) - Counter(b)) for a, b in zip(diff["norm"], diff["kraken"])],
        "ajoutes": [describe(Counter(b) - Counter(a)) for a, b in zip(diff["norm"], diff["kraken"])],
        "transformation": diff["norm"].map(responsible_step),
        "note": NOTE[name],
    })
    summary = {
        "jeu": name,
        "lignes": len(lines),
        "caracteres_evaluate": int(lines["caracteres_evaluate"].sum()),
        "caracteres_ketos": int(lines["caracteres_ketos"].sum()),
        "ecart": int(lines["caracteres_evaluate"].sum() - lines["caracteres_ketos"].sum()),
        "lignes_differentes": len(diff),
        "note": NOTE[name],
    }
    return summary, rows


def main() -> None:
    results = [split_table(name) for name in SPLITS]
    summary = pd.DataFrame([s for s, _ in results])
    rows = pd.concat([r for _, r in results], ignore_index=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT / "resume.csv", index=False, lineterminator="\n")
    rows.to_csv(OUTPUT / "lignes_differentes.csv", index=False, lineterminator="\n")
    print(summary.drop(columns="note").to_string(index=False))
    print(rows.drop(columns="note").to_string(index=False))
    print(f"-> {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
