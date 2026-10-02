"""Jeu d'entraînement de la variante C de F12 : le train de F8 sans les pages en couche gen2 (décision 42).

- Pages retirées : celles dont la couche de transcription est `gen2-print-n7m5-union-ft_best`
  (Doc 83 et Doc 6398, 18 pages, décisions 4 et 16) ; aucune autre ligne ne change.
- Lignes gardées : exactement celles du train de F8 (mêmes exclusions, `prepare.select_lines`,
  même texte normalisé), compilées depuis les ALTO normalisés de `prepare`, relus sans être
  réécrits, avec les mêmes réglages (`prepare.compile_split` : ancien extracteur, un processus).
- Sortie à part : data/processed/makhzan/train_sans_gen2.arrow et .lst. Le train et la validation
  de F8 (train.arrow, val.arrow et leurs manifestes) ne sont pas touchés : empreintes SHA-256
  vérifiées avant et après.
- Vérifications : 254 lignes retirées sur 2 757 (décision 42) ; chaque ligne compilée (texte et
  image) est une ligne de train.arrow, et les lignes manquantes sont exactement celles des pages
  gen2 ; texte dans le codec du modèle de départ (`--resize fail`, décision 33) ; lecture par kraken
  sans ligne remplacée.
- Rapport : reports/train_sans_gen2.csv (effectifs, empreintes, caractères absents du nouveau jeu).

Usage : uv run python -m htr_ottoman.prepare_sans_gen2
"""
import hashlib
from collections import Counter
from pathlib import Path

import pandas as pd
import pyarrow as pa

from htr_ottoman.base_model import codec_chars
from htr_ottoman.config import MAKHZAN_PROCESSED, REPORTS, ROOT
from htr_ottoman.data.makhzan import MODEL_LAYERS
from htr_ottoman.prepare import check_split, compile_split, processed_alto_path, select_lines, verify_with_kraken

NAME = "train_sans_gen2"
GEN2_LAYER = "gen2-print-n7m5-union-ft_best"  # décision 4
GEN2_DOCS = {83, 6398}
EXPECTED = {"pages_retirees": 18, "lignes_retirees": 254, "lignes": 2503}  # décision 42 : 254 lignes sur 2 757
UNTOUCHED = ["train.arrow", "train.lst", "val.arrow", "val.lst"]  # jeux de F8, à l'identique
REPORT = REPORTS / f"{NAME}.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprints() -> dict[str, str]:
    return {name: sha256(MAKHZAN_PROCESSED / name) for name in UNTOUCHED}


def select() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lignes compilées du train de F8, séparées en (gardées, retirées) selon la couche gen2."""
    assert GEN2_LAYER in MODEL_LAYERS
    lines = select_lines()
    train = lines[(lines["split"] == "train") & lines["exclusion"].isna()]
    gen2_pages = set(train.loc[train["layer"] == GEN2_LAYER, "part_id"])
    removed = train[train["part_id"].isin(gen2_pages)]
    if (removed["layer"] != GEN2_LAYER).any():
        raise ValueError("Page en partie seulement en couche gen2 : décision 4 non applicable telle quelle")
    if set(removed["doc_id"]) != GEN2_DOCS:
        raise ValueError(f"Pages gen2 hors de Doc 83 et 6398 : {sorted(set(removed['doc_id']))}")
    return train[~train["part_id"].isin(gen2_pages)], removed


def records(name: str) -> Counter:
    """Lignes d'un jeu compilé, comptées par (texte, empreinte de l'image)."""
    with pa.memory_map(str(MAKHZAN_PROCESSED / f"{name}.arrow")) as source:
        table = pa.ipc.open_file(source).read_all()
    return Counter((r["text"], hashlib.sha256(r["im"]).hexdigest()) for r in table.column("lines").to_pylist())


def check_subset(kept: pd.DataFrame, removed: pd.DataFrame) -> None:
    """Chaque ligne du nouveau jeu (texte et image) est une ligne de train.arrow ; celles qui
    manquent sont exactement les lignes des pages gen2."""
    new, old = records(NAME), records("train")
    if new - old:
        raise ValueError(f"{NAME}.arrow : {sum((new - old).values())} lignes absentes de train.arrow")
    missing = Counter(text for (text, _), n in (old - new).items() for _ in range(n))
    if missing != Counter(removed["norm"]) or len(new) != len(kept):
        raise ValueError(f"{NAME}.arrow : lignes retirées différentes des lignes des pages gen2")


def main() -> None:
    before = fingerprints()
    kept, removed = select()
    counts = {"pages_retirees": removed["part_id"].nunique(), "lignes_retirees": len(removed), "lignes": len(kept)}
    if counts != EXPECTED:
        raise ValueError(f"Effectifs {counts}, attendus {EXPECTED} (décision 42)")
    pages = kept.groupby("part_id", sort=True).first()  # même ordre que prepare (pages par part_id)
    alto_paths = [processed_alto_path(p.doc_id, p.alto_path) for p in pages.itertuples()]
    if missing := [p for p in alto_paths if not p.exists()]:
        raise FileNotFoundError(f"ALTO normalisés absents, lancer d'abord htr_ottoman.prepare : {missing[:3]}")
    print(f"{NAME} : {len(alto_paths)} ALTO normalisés existants, compilation…", flush=True)
    compile_split(NAME, [str(p.relative_to(ROOT)) for p in alto_paths])
    meta = check_split(NAME, kept["norm"].tolist())
    check_subset(kept, removed)
    texts = "".join(kept["norm"])
    if outside := set(texts) - codec_chars():
        raise ValueError(f"{NAME}.arrow : caractères hors du codec du modèle de départ {sorted(outside)}")
    if fingerprints() != before:
        raise ValueError("Le train ou la validation de F8 a changé pendant la compilation")
    gone = sorted(set("".join(removed["norm"])) - set(texts))
    report = pd.DataFrame([{
        "jeu": NAME,
        "manuscrits": kept["doc_id"].nunique(),
        **{k: counts[k] for k in ("pages_retirees", "lignes_retirees")},
        "pages": kept["part_id"].nunique(),
        "lignes": len(kept),
        "caracteres": len(texts),
        "caracteres_retires": int(removed["norm"].str.len().sum()),
        "caracteres_distincts": len(set(texts)),
        "absents_apres_retrait": " ".join(f"U+{ord(c):04X}" for c in gone),
        "legacy_polygons": meta["legacy_polygons"],
        "sha256": sha256(MAKHZAN_PROCESSED / f"{NAME}.arrow"),
        **{f"sha256_{n.replace('.', '_')}": h for n, h in before.items()},
    }])
    report.to_csv(REPORT, index=False, lineterminator="\n")
    print(report.T.to_string(header=False))
    print(f"lecture kraken {NAME} : {verify_with_kraken(NAME)} lignes lues sans erreur", flush=True)
    print(f"-> data/processed/makhzan/{NAME}.arrow et .lst ; {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
