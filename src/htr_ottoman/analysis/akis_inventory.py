"""Inventaire du jeu de test Akis (F10), sans aucune prédiction.

Lit la table des lignes (data.akis) et écrit :
- reports/akis_sources.csv : une ligne par source (livre imprimé) : année,
  pages, lignes, caractères, formes Unicode, taille des images ;
- reports/akis_characters.csv : une ligne par caractère, compté après NFD (la
  forme du modèle de départ et de `normalize`), avec son écriture Unicode, ses
  fréquences et sa présence dans le codec du modèle de départ.

Le texte est lu tel quel ; seule la forme NFD est appliquée pour le décompte
des caractères (les transcriptions mêlent NFC et NFD, voir akis_sources.csv).

Usage : uv run python -m htr_ottoman.analysis.akis_inventory
"""
import unicodedata
from collections import Counter, defaultdict

import pandas as pd

from htr_ottoman.base_model import codec_chars
from htr_ottoman.config import AKIS_LINES, REPORTS

SOURCES_OUTPUT = REPORTS / "akis_sources.csv"
CHARACTERS_OUTPUT = REPORTS / "akis_characters.csv"


def unicode_form(text: str) -> str:
    nfc, nfd = unicodedata.is_normalized("NFC", text), unicodedata.is_normalized("NFD", text)
    if nfc and nfd:
        return "sans_composition"  # aucun caractère composable (ASCII, ı, ş précomposé absent...)
    return "NFC" if nfc else "NFD" if nfd else "mixte"


def script_of(char: str) -> str:
    """Écriture d'après le nom Unicode : arabe, latin, ou autre (chiffres, ponctuation, combinants)."""
    name = unicodedata.name(char, "")
    if "ARABIC" in name:
        return "arabe"
    if "LATIN" in name:
        return "latin"
    return "autre"


def sources_table(lines: pd.DataFrame) -> pd.DataFrame:
    lines = lines.assign(form=lines["text"].map(unicode_form), n_chars=lines["text"].str.len())
    forms = pd.crosstab(lines["source"], lines["form"]).add_prefix("lignes_")
    table = lines.groupby("source").agg(
        annee=("year", "first"),
        pages=("page", "nunique"),
        lignes=("line_id", "size"),
        caracteres=("n_chars", "sum"),
        hauteur_min=("image_height", "min"),
        hauteur_max=("image_height", "max"),
        largeur_mediane=("image_width", "median"),
    )
    table = table.join(forms).reset_index()
    total = table.drop(columns=["source", "annee"]).sum(numeric_only=True)
    total["hauteur_min"], total["hauteur_max"] = table["hauteur_min"].min(), table["hauteur_max"].max()
    total["largeur_mediane"] = lines["image_width"].median()
    table = pd.concat([table, pd.DataFrame([{"source": "TOTAL", **total}])], ignore_index=True)
    int_columns = [c for c in table.columns if c not in ("source", "annee")]
    return table.astype({c: "int64" for c in int_columns} | {"annee": "Int64"})


def characters_table(lines: pd.DataFrame) -> pd.DataFrame:
    codec = codec_chars()
    counts, n_lines, sources = Counter(), Counter(), defaultdict(set)
    for source, text in zip(lines["source"], lines["text"]):
        text = unicodedata.normalize("NFD", text)
        counts.update(text)
        for c in set(text):
            n_lines[c] += 1
            sources[c].add(source)
    rows = [
        {
            "codepoint": f"U+{ord(c):04X}",
            "char": c,
            "name": unicodedata.name(c, "?"),
            "category": unicodedata.category(c),
            "script": script_of(c),
            "occurrences": n,
            "lines": n_lines[c],
            "sources": len(sources[c]),
            "in_base_codec": c in codec,
        }
        for c, n in counts.items()
    ]
    return pd.DataFrame(rows).sort_values(["occurrences", "codepoint"], ascending=[False, True]).reset_index(drop=True)


def main() -> None:
    lines = pd.read_parquet(AKIS_LINES)
    sources = sources_table(lines)
    chars = characters_table(lines)
    sources.to_csv(SOURCES_OUTPUT, index=False)
    chars.to_csv(CHARACTERS_OUTPUT, index=False)

    total = chars["occurrences"].sum()
    by_script = chars.groupby("script")["occurrences"].sum()
    arabic_lines = lines["text"].map(lambda t: any(script_of(c) == "arabe" for c in t)).sum()
    missing = chars[~chars["in_base_codec"]]
    print(f"{len(lines)} lignes, {lines['source'].nunique()} sources, {lines['page'].groupby(lines['source']).nunique().sum()} pages")
    print(f"Caractères (NFD) : {total} ; par écriture : {by_script.to_dict()}")
    print(f"Lignes contenant au moins une lettre arabe : {arabic_lines}")
    print(f"Caractères absents du codec du modèle de départ : {len(missing)} types, "
          f"{missing['occurrences'].sum()} occurrences ({missing['occurrences'].sum() / total:.1%})")
    print(f"-> {SOURCES_OUTPUT.name}, {CHARACTERS_OUTPUT.name}")


if __name__ == "__main__":
    main()
