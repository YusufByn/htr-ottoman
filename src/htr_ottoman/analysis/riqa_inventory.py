"""Inventaire de RiqaTestset (F15, décision 46), sans aucune prédiction ni aucun modèle chargé.

Lit la table des lignes (data.riqa) et écrit, en chiffres agrégés seulement (ni
image ni transcription, décision 46) :
- reports/riqa/unites.csv : une ligne par unité (préfixe UUID des noms de
  fichiers) : lignes, numérotation, caractères, formes Unicode, images ;
- reports/riqa/caracteres.csv : une ligne par caractère, compté sur le texte
  brut et après `normalize`, avec sa présence dans le codec du modèle de départ
  (reports/codec_modele_depart.json, lu sans charger le modèle) et son nombre
  d'occurrences dans le train (reports/codec_coverage.csv, après `normalize`,
  lignes non annotées) ;
- reports/riqa/resume.json : totaux.

Usage : uv run python -I -m htr_ottoman.analysis.riqa_inventory
"""
import json
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from PIL import Image

from htr_ottoman.analysis.akis_inventory import script_of, unicode_form
from htr_ottoman.base_model import codec_chars
from htr_ottoman.config import RIQA_INTERIM, RIQA_LINES, RIQA_REPORTS, ROOT
from htr_ottoman.data.annotations import has_annotation
from htr_ottoman.normalize import normalize

UNITS_OUTPUT = RIQA_REPORTS / "unites.csv"
CHARACTERS_OUTPUT = RIQA_REPORTS / "caracteres.csv"
SUMMARY_OUTPUT = RIQA_REPORTS / "resume.json"
TRAIN_COVERAGE = ROOT / "reports" / "codec_coverage.csv"


def image_colours(path) -> dict:
    """Mode PIL, image en gris de fait (canaux égaux) et nombre de niveaux distincts."""
    with Image.open(ROOT / path) as im:
        mode = im.mode
        a = np.asarray(im.convert("RGB"))
    grey = bool((a[..., 0] == a[..., 1]).all() and (a[..., 1] == a[..., 2]).all())
    return {"mode": mode, "grey": grey, "levels": len(np.unique(a.reshape(-1, 3), axis=0))}


def prepare(lines: pd.DataFrame) -> pd.DataFrame:
    colours = pd.DataFrame([image_colours(p) for p in lines["image_path"]], index=lines.index)
    return lines.assign(
        form=lines["text"].map(unicode_form),
        norm=lines["text"].map(normalize),
        annotated=lines["text"].map(has_annotation),
        n_chars=lines["text"].str.len(),
        image_grey=colours["grey"],
        image_levels=colours["levels"],
    ).assign(n_chars_norm=lambda d: d["norm"].str.len())


def units_table(lines: pd.DataFrame) -> pd.DataFrame:
    g = lines.groupby("unit")
    table = g.agg(
        lignes=("line_id", "size"),
        numero_min=("line_number", "min"),
        numero_max=("line_number", "max"),
        lignes_vides=("is_empty", "sum"),
        lignes_annotees=("annotated", "sum"),
        caracteres_bruts=("n_chars", "sum"),
        caracteres_normalises=("n_chars_norm", "sum"),
        hauteur_min=("image_height", "min"),
        hauteur_mediane=("image_height", "median"),
        hauteur_max=("image_height", "max"),
        largeur_mediane=("image_width", "median"),
    )
    table["numerotation_continue"] = table["numero_max"] - table["numero_min"] + 1 == table["lignes"]
    forms = pd.crosstab(lines["unit"], lines["form"]).add_prefix("lignes_")
    return table.join(forms).reset_index()


def characters_table(lines: pd.DataFrame) -> pd.DataFrame:
    codec = codec_chars()
    train = pd.read_csv(TRAIN_COVERAGE, keep_default_na=False)
    train = dict(zip(train["char"], train["count_train"]))
    raw, norm, n_lines, units = Counter(), Counter(), Counter(), defaultdict(set)
    for unit, text, normed in zip(lines["unit"], lines["text"], lines["norm"]):
        raw.update(text)
        norm.update(normed)
        for c in set(normed):
            n_lines[c] += 1
            units[c].add(unit)
    rows = [
        {
            "codepoint": f"U+{ord(c):04X}",
            "char": c,
            "name": unicodedata.name(c, "?"),
            "category": unicodedata.category(c),
            "script": script_of(c),
            "count_brut": raw[c],
            "count_normalise": norm[c],
            "lignes_normalise": n_lines[c],
            "unites_normalise": len(units[c]),
            "in_base_codec": c in codec,
            "count_train": int(train.get(c, 0)),
        }
        for c in set(raw) | set(norm)
    ]
    return pd.DataFrame(rows).sort_values(["count_normalise", "count_brut", "codepoint"], ascending=[False, False, True]).reset_index(drop=True)


def summary(lines: pd.DataFrame, chars: pd.DataFrame) -> dict:
    codec = codec_chars()
    used = chars[chars["count_normalise"] > 0]
    out_codec = used[~used["in_base_codec"]]
    out_train = used[used["count_train"] == 0]
    raw_out_codec = chars[(chars["count_brut"] > 0) & ~chars["in_base_codec"]]
    n_norm = int(lines["n_chars_norm"].sum())
    turkish = sorted((RIQA_INTERIM / "turkish").iterdir())
    return {
        "lignes": len(lines),
        "unites": int(lines["unit"].nunique()),
        "lignes_par_unite": lines.groupby("unit").size().describe()[["min", "50%", "max"]].to_dict(),
        "transcriptions_turques": len(turkish),
        "lignes_vides": int(lines["is_empty"].sum()),
        "lignes_annotees": int(lines["annotated"].sum()),
        "fichiers_avec_bom": int(lines["has_bom"].sum()),
        "fichiers_avec_cr": int(lines["has_cr"].sum()),
        "fichiers_avec_saut_final": int(lines["has_final_newline"].sum()),
        "formes_unicode": lines["form"].value_counts().to_dict(),
        "lignes_changees_par_normalize": int((lines["text"] != lines["norm"]).sum()),
        "caracteres_bruts": int(lines["n_chars"].sum()),
        "caracteres_normalises": n_norm,
        "types_bruts": int((chars["count_brut"] > 0).sum()),
        "types_normalises": len(used),
        "hors_codec_brut": {"types": len(raw_out_codec), "occurrences": int(raw_out_codec["count_brut"].sum())},
        "hors_codec_normalise": {
            "types": len(out_codec),
            "occurrences": int(out_codec["count_normalise"].sum()),
            "part": round(out_codec["count_normalise"].sum() / n_norm, 5),
            "lignes_touchees": int(lines["norm"].map(lambda t: any(c not in codec for c in t)).sum()),
        },
        "absents_du_train_normalise": {
            "types": len(out_train),
            "occurrences": int(out_train["count_normalise"].sum()),
            "part": round(out_train["count_normalise"].sum() / n_norm, 5),
        },
        "images": {
            "modes": lines["image_mode"].value_counts().to_dict(),
            "gris_de_fait": int(lines["image_grey"].sum()),
            "deux_niveaux_ou_moins": int((lines["image_levels"] <= 2).sum()),
            "niveaux_median": float(lines["image_levels"].median()),
            "hauteur": lines["image_height"].describe()[["min", "50%", "max"]].to_dict(),
            "largeur": lines["image_width"].describe()[["min", "50%", "max"]].to_dict(),
        },
        "codec_modele_depart": len(codec),
    }


def main() -> None:
    lines = prepare(pd.read_parquet(RIQA_LINES))
    RIQA_REPORTS.mkdir(exist_ok=True)
    units = units_table(lines)
    chars = characters_table(lines)
    result = summary(lines, chars)
    units.to_csv(UNITS_OUTPUT, index=False, lineterminator="\n")
    chars.to_csv(CHARACTERS_OUTPUT, index=False, lineterminator="\n")
    SUMMARY_OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    cols = ["codepoint", "char", "name", "count_brut", "count_normalise", "in_base_codec", "count_train"]
    print("\nCaractères hors codec ou absents du train (après normalize) :")
    used = chars[chars["count_normalise"] > 0]
    print(used[~used["in_base_codec"] | (used["count_train"] == 0)][cols].to_string(index=False))
    print("\nCaractères bruts modifiés ou supprimés par normalize :")
    print(chars[chars["count_brut"] != chars["count_normalise"]][cols].to_string(index=False))
    print(f"\n-> {UNITS_OUTPUT.relative_to(ROOT)}, {CHARACTERS_OUTPUT.relative_to(ROOT)}, {SUMMARY_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
