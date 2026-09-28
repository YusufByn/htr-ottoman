"""Inventaire des caractères des lignes ottomanes de MAKHZAN.

Lit les ALTO directement dans le zip de data/raw/ (lecture seule, rien n'est
extrait sur le disque) et écrit reports/ottoman_characters.csv : une ligne par
caractère, avec son nom Unicode, sa catégorie et ses fréquences. Le texte est
compté tel quel, sans normalisation.

Usage : uv run python -m htr_ottoman.analysis.char_inventory
"""
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict

import pandas as pd

from htr_ottoman.config import MAKHZAN_METADATA, MAKHZAN_ZIP, REPORTS

OUTPUT = REPORTS / "ottoman_characters.csv"
LANGUAGE = "Ottoman Turkish"
PAGE_XML = re.compile(r"^(\d+)_(\d+)\.xml$")


def ottoman_pages() -> pd.DataFrame:
    df = pd.read_csv(MAKHZAN_METADATA, sep="\t", dtype=str, keep_default_na=False)
    return df[df["Language"].str.contains(LANGUAGE, regex=False)]


def iter_lines(pages: pd.DataFrame):
    """Renvoie (doc_id, part_id, liste des CONTENT des String) pour chaque TextLine."""
    wanted = set(pages["Doc Part ID"])
    with zipfile.ZipFile(MAKHZAN_ZIP) as outer:
        for doc_id in sorted(set(pages["Doc ID"]), key=int):
            with outer.open(f"Doc{doc_id}.zip") as f, zipfile.ZipFile(f) as inner:
                for name in inner.namelist():
                    m = PAGE_XML.match(name)
                    if not m or m.group(2) not in wanted:
                        continue
                    root = ET.fromstring(inner.read(name))
                    ns = {"a": root.tag.split("}")[0].strip("{")}
                    for line in root.iterfind(".//a:TextLine", ns):
                        strings = [s.get("CONTENT", "") for s in line.iterfind("a:String", ns)]
                        yield doc_id, m.group(2), strings


def main() -> None:
    pages = ottoman_pages()
    source = dict(zip(pages["Doc Part ID"], pages["Dataset Source"]))

    chars = Counter()
    by_source = defaultdict(Counter)
    lines_with, docs_with = defaultdict(set), defaultdict(set)
    n_strings = Counter()
    anomalies = Counter()
    n_lines = n_empty = 0

    for doc_id, part_id, strings in iter_lines(pages):
        n_lines += 1
        n_strings[len(strings)] += 1
        text = " ".join(strings)
        if not text.strip():
            n_empty += 1
            continue
        if text != text.strip():
            anomalies["espace en début ou en fin"] += 1
        if "  " in text:
            anomalies["espaces multiples"] += 1
        for c in text:
            chars[c] += 1
            by_source[source[part_id]][c] += 1
            lines_with[c].add((part_id, n_lines))
            docs_with[c].add(doc_id)

    rows = [
        {
            "codepoint": f"U+{ord(c):04X}",
            "char": c,
            "name": unicodedata.name(c, "?"),
            "category": unicodedata.category(c),
            "count": n,
            "n_lines": len(lines_with[c]),
            "n_docs": len(docs_with[c]),
            "count_research": by_source["Research"][c],
            "count_acdc_eval": by_source["ACDC-Evaluation"][c],
            "changes_in_nfd": unicodedata.normalize("NFD", c) != c,
        }
        for c, n in chars.most_common()
    ]
    inv = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(exist_ok=True)
    inv.to_csv(OUTPUT, index=False)

    print(f"{n_lines} lignes ({n_empty} vides), {sum(chars.values())} caractères, {len(chars)} distincts")
    print("String par ligne :", dict(sorted(n_strings.items())))
    print("Anomalies d'espacement (lignes) :", dict(anomalies) or "aucune")
    print("Caractères par catégorie Unicode :", inv.groupby("category")["count"].sum().to_dict())
    print(f"-> {OUTPUT.relative_to(OUTPUT.parents[1])}")


if __name__ == "__main__":
    main()
