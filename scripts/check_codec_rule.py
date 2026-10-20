"""Vérifie que la règle « hors codec » de `prepare.select_lines` ne touche que le train.

Compare `select_lines(with_codec=True)` et `select_lines(with_codec=False)` sur le train
et la validation. Les lignes du test interne sont retirées de la table avant l'appel :
le modèle de départ (chargé pour lire son codec) ne voit jamais le test interne (décision 39).
Aucune prédiction. Ticket F14, complément du 2026-10-20. Depuis F14, le codec est lu dans
reports/codec_modele_depart.json : plus aucun modèle chargé ni kraken importé.
"""
import pandas as pd

from htr_ottoman import prepare
from htr_ottoman.splits import load_split

test_ids = set(load_split("test_interne")["part_id"])
read_parquet = pd.read_parquet


def read_without_test(path, *args, **kwargs):
    lines = read_parquet(path, *args, **kwargs)
    return lines[~lines["part_id"].isin(test_ids)].reset_index(drop=True)


prepare.pd.read_parquet = read_without_test
without = prepare.select_lines(with_codec=False)
assert not without["split"].eq("test_interne").any()
with_codec = prepare.select_lines(with_codec=True)
assert not with_codec["split"].eq("test_interne").any()

codec = prepare.codec_chars()
for split in ["train", "val"]:
    a = with_codec[with_codec["split"] == split].reset_index(drop=True)
    b = without[without["split"] == split].reset_index(drop=True)
    outside = b["norm"].map(lambda t: not set(t) <= codec)
    diff = (a["exclusion"].fillna("") != b["exclusion"].fillna("")).sum()
    print(f"{split} : {len(a)} lignes, {outside.sum()} avec un caractère hors codec, "
          f"{diff} exclusions différentes, tables identiques : {a.equals(b)}")
    print(f"  gardées avec codec : {a['exclusion'].isna().sum()}, sans codec : {b['exclusion'].isna().sum()}")
