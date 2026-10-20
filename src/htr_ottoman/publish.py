"""Modèle publié en F14 : copie de F8 (lag 5) avec le drapeau « anciens polygones » corrigé.

kraken 7.1.1 perd ce drapeau en convertissant le checkpoint en .safetensors (décision 36) :
`best_0.8365.safetensors` porte `legacy_polygons: false` alors que F8 a été entraîné et
évalué avec l'ancien extracteur. Ce module écrit une copie dont seul l'en-tête change :

- un fichier .safetensors = 8 octets (longueur de l'en-tête), l'en-tête JSON (complété
  par des espaces jusqu'à un multiple de 8), puis le bloc des tenseurs ;
- dans la copie, le bloc des tenseurs est recopié tel quel, et l'en-tête ne diffère que
  par `"legacy_polygons": true` dans les métadonnées `kraken_meta` ;
- l'original n'est jamais modifié : son SHA-256 est vérifié avant et après (décisions 37 et 44).

Aucun modèle chargé, kraken n'est pas importé. La preuve que la copie prédit comme le
modèle évalué est faite à part, sur la validation (scripts/f14_preuve_validation.py).

Usage : uv run python -m htr_ottoman.publish
"""
import hashlib
import json
import struct

from htr_ottoman.config import PUBLISHED_MODEL, PUBLISHED_SOURCE, ROOT

SOURCE_SHA256 = "3709c4f3b5600db2399ebd2260feba7c5fcf8999afaf71a9cb9a0bab9847f8dd"  # décision 37
FLAG = "legacy_polygons"


def sha256sum(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_safetensors(content: bytes) -> tuple[bytes, bytes]:
    """En-tête JSON brut (avec ses espaces de fin) et bloc des tenseurs."""
    (n,) = struct.unpack("<Q", content[:8])
    return content[8:8 + n], content[8 + n:]


def dump_header(header: dict) -> bytes:
    """En-tête sérialisé comme le fait safetensors : JSON compact, espaces jusqu'à un multiple de 8."""
    raw = json.dumps(header, separators=(",", ":")).encode("utf-8")
    return raw + b" " * (-len(raw) % 8)


def kraken_meta(header: dict) -> dict:
    return json.loads(header["__metadata__"]["kraken_meta"])


def with_legacy_flag(raw_header: bytes) -> bytes:
    """En-tête identique, sauf `legacy_polygons` passé de false à true dans `kraken_meta`."""
    header = json.loads(raw_header)
    if dump_header(header) != raw_header:
        raise ValueError("En-tête non reproduit à l'identique : sérialisation différente de safetensors")
    meta = kraken_meta(header)
    if len(meta) != 1:
        raise ValueError(f"{len(meta)} modèles dans le fichier, attendu 1")
    (model,) = meta.values()
    if model.get(FLAG) is not False:
        raise ValueError(f"{FLAG} = {model.get(FLAG)!r}, attendu false (décision 36)")
    model[FLAG] = True
    header["__metadata__"]["kraken_meta"] = json.dumps(meta)  # même sérialisation que kraken (models/writers.py)
    return dump_header(header)


def header_differences(old: bytes, new: bytes) -> dict:
    """Différences entre deux en-têtes : tenseurs, autres métadonnées, champs de `kraken_meta`."""
    a, b = json.loads(old), json.loads(new)
    ma, mb = kraken_meta(a), kraken_meta(b)
    fields = {(p, k) for p in ma.keys() | mb.keys() for k in ma.get(p, {}).keys() | mb.get(p, {}).keys()
              if ma.get(p, {}).get(k) != mb.get(p, {}).get(k)}
    return {
        "tenseurs": sorted(k for k in a.keys() | b.keys() if k != "__metadata__" and a.get(k) != b.get(k)),
        "autres_metadonnees": sorted(k for k in a["__metadata__"].keys() | b["__metadata__"].keys()
                                     if k != "kraken_meta" and a["__metadata__"].get(k) != b["__metadata__"].get(k)),
        "kraken_meta": sorted(k for _, k in fields),
    }


def write_copy() -> dict:
    """Écrit la copie corrigée et renvoie les contrôles."""
    before = sha256sum(PUBLISHED_SOURCE)
    if before != SOURCE_SHA256:
        raise ValueError(f"SHA-256 de {PUBLISHED_SOURCE.name} : {before}, attendu {SOURCE_SHA256}")
    content = PUBLISHED_SOURCE.read_bytes()
    raw_header, data = split_safetensors(content)
    new_header = with_legacy_flag(raw_header)
    PUBLISHED_MODEL.parent.mkdir(parents=True, exist_ok=True)
    PUBLISHED_MODEL.write_bytes(struct.pack("<Q", len(new_header)) + new_header + data)

    copy_header, copy_data = split_safetensors(PUBLISHED_MODEL.read_bytes())
    return {
        "sha256_original_avant": before,
        "sha256_original_apres": sha256sum(PUBLISHED_SOURCE),
        "sha256_copie": sha256sum(PUBLISHED_MODEL),
        "octets_original": len(content),
        "octets_copie": PUBLISHED_MODEL.stat().st_size,
        "bloc_tenseurs_identique": copy_data == data,
        "octets_bloc_tenseurs": len(data),
        "drapeau_copie": next(iter(kraken_meta(json.loads(copy_header)).values()))[FLAG],
        **header_differences(raw_header, copy_header),
    }


def main() -> None:
    result = write_copy()
    for k, v in result.items():
        print(f"  {k} : {v}")
    ok = (result["sha256_original_avant"] == result["sha256_original_apres"] == SOURCE_SHA256
          and result["bloc_tenseurs_identique"] and result["drapeau_copie"] is True
          and result["tenseurs"] == [] and result["autres_metadonnees"] == [] and result["kraken_meta"] == [FLAG])
    print(f"-> {PUBLISHED_MODEL.relative_to(ROOT)} : {'OK' if ok else 'ÉCART'}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
