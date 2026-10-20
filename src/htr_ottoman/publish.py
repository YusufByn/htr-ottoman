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

`validate_card` vérifie la carte du modèle (MODEL_CARD.md) comme le fait htrmopo avant
une publication (schéma v1, licences, codes de langue et d'écriture), sans réseau ; l'identifiant,
attribué par Zenodo au dépôt, est remplacé par une valeur provisoire.

`--zenodo` dépose le modèle publié sur Zenodo par `htrmopo.publish_model`, sans passer par
`ketos publish` : celui-ci plante avec ce modèle (`accuracy` vaut une liste vide dans ses
métadonnées) et remplacerait le CER de la carte par celui de kraken, calculé sans `normalize`.
Le dépôt contient le modèle publié (SHA-256 de la décision 45 vérifié), un `metadata.json`
(ancien format v0 de kraken) dont la précision vient du CER de la carte (après `normalize`),
et la carte, envoyée sous le nom README.md par htrmopo, identique à MODEL_CARD.md sauf les
auteurs, au format « Nom, Prénom » attendu par Zenodo (ZENODO_CREATOR_NAMES).
`--dry-run` prépare et affiche tout ce qui serait envoyé, sans aucun appel réseau.
Le jeton Zenodo est lu dans la variable d'environnement ZENODO_TOKEN, jamais affiché.
La publication est immédiate et le DOI définitif : sans `--sandbox`, une confirmation est demandée.

Usage : uv run python -m htr_ottoman.publish             (écrit la copie)
        uv run python -m htr_ottoman.publish --carte     (valide MODEL_CARD.md seulement)
        uv run python -m htr_ottoman.publish --zenodo --sandbox --dry-run
        ZENODO_TOKEN=... uv run python -m htr_ottoman.publish --zenodo --sandbox
        ZENODO_TOKEN=... uv run python -m htr_ottoman.publish --zenodo
"""
import argparse
import hashlib
import json
import os
import shutil
import struct

from htr_ottoman.config import DEPOSIT_DIR, MODEL_CARD, PUBLISHED_MODEL, PUBLISHED_SOURCE, ROOT

SOURCE_SHA256 = "3709c4f3b5600db2399ebd2260feba7c5fcf8999afaf71a9cb9a0bab9847f8dd"  # décision 37
FLAG = "legacy_polygons"
PLACEHOLDER_ID = "10.5281/zenodo.0"  # remplacé par le DOI réservé par Zenodo au dépôt (htrmopo.publish_model)
PUBLISHED_SHA256 = "4d96d85f2f93fd9008f4d48bbcfbfc87aefe0c698ce5cf1dd3310e761ecd022e"  # décision 45
ZENODO_API = "https://zenodo.org/api/"
SANDBOX_API = "https://sandbox.zenodo.org/api/"
TOKEN_ENV = "ZENODO_TOKEN"
# Zenodo attend « Nom, Prénom » ; MODEL_CARD.md et LICENSE gardent « Prénom Nom » (choix de l'utilisateur, F14)
ZENODO_CREATOR_NAMES = {"Yusuf Buyukaydin": "Buyukaydin, Yusuf"}


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


def validate_card(text: str) -> dict:
    """En-tête YAML de la carte, validé comme dans htrmopo.publish_model ; lève une erreur sinon."""
    import yaml
    from htrmopo.util import _v1_schema, _yaml_regex, format_checker
    from jsonschema import validate

    match = _yaml_regex.match(text)
    if match is None:
        raise ValueError("Carte sans en-tête YAML")
    header = yaml.safe_load(match.group(1))
    validate(dict(header, id=PLACEHOLDER_ID), _v1_schema, format_checker=format_checker)
    return header


def split_card(text: str) -> tuple[dict, str]:
    """En-tête YAML validé et texte de la carte, découpés comme dans htrmopo."""
    from htrmopo.util import _yaml_regex

    header = validate_card(text)
    return header, _yaml_regex.match(text).group(2)


def v0_metadata(card: dict, content: str, model_path) -> dict:
    """metadata.json au format v0 de kraken, mêmes champs que `ketos publish` (sans `authors`,
    que le schéma v0 veut avec une affiliation), sauf la précision : 100 − CER de la carte
    (après `normalize`), jamais un CER recalculé par kraken. Graphèmes lus dans l'en-tête du
    modèle, sans le charger. Validé contre le schéma v0, `authors` mis à part."""
    from htrmopo.util import _v0_schema, format_checker
    from jsonschema import validate

    raw, _ = split_safetensors(model_path.read_bytes())
    (model,) = kraken_meta(json.loads(raw)).values()
    data = {
        "summary": card["summary"],
        "description": content,
        "accuracy": round(100 - card["metrics"]["cer"], 2),
        "license": card["license"],
        "script": card["script"],
        "name": model_path.name,
        "graphemes": list("".join(model["codec"])),
    }
    schema = dict(_v0_schema, required=[k for k in _v0_schema["required"] if k != "authors"])
    validate(data, schema, format_checker=format_checker)
    return data


def zenodo_card(card: dict, content: str) -> tuple[dict, str]:
    """Carte envoyée à Zenodo : celle de MODEL_CARD.md, auteurs au format « Nom, Prénom »
    (htrmopo en tire les `creators` de Zenodo). Tout auteur absent de la table est refusé."""
    import yaml

    missing = [a["name"] for a in card["authors"] if a["name"] not in ZENODO_CREATOR_NAMES]
    if missing:
        raise ValueError(f"Auteurs sans nom au format Zenodo (ZENODO_CREATOR_NAMES) : {missing}")
    sent = dict(card, authors=[dict(a, name=ZENODO_CREATOR_NAMES[a["name"]]) for a in card["authors"]])
    text = f"---\n{yaml.dump(sent, allow_unicode=True, sort_keys=False)}---\n{content}"
    validate_card(text)
    return sent, text


def prepare_deposit(sandbox: bool, private: bool, model_path=None, card_path=None, deposit_dir=None) -> dict:
    """Prépare le dossier envoyé à Zenodo et décrit tout l'envoi. Aucun appel réseau."""
    from htrmopo.publish import _build_zenodo_metadata

    model_path, card_path = model_path or PUBLISHED_MODEL, card_path or MODEL_CARD
    deposit_dir = deposit_dir or DEPOSIT_DIR

    if (sha := sha256sum(model_path)) != PUBLISHED_SHA256:
        raise ValueError(f"SHA-256 de {model_path.name} : {sha}, attendu {PUBLISHED_SHA256} (décision 45)")
    raw, _ = split_safetensors(model_path.read_bytes())
    if next(iter(kraken_meta(json.loads(raw)).values())).get(FLAG) is not True:
        raise ValueError(f"{FLAG} n'est pas vrai dans {model_path.name} (décision 45)")
    card, content = split_card(card_path.read_text(encoding="utf-8"))
    sent_card, text = zenodo_card(card, content)
    private = private or sandbox  # pas de communauté ocr_models sur le bac à sable

    if deposit_dir.exists():
        shutil.rmtree(deposit_dir)
    deposit_dir.mkdir(parents=True)
    shutil.copyfile(model_path, deposit_dir / model_path.name)
    metadata = v0_metadata(card, content, model_path)
    with open(deposit_dir / "metadata.json", "w") as fo:
        json.dump(metadata, fo)  # comme ketos publish
    files = [{"fichier": f.name, "octets": f.stat().st_size, "sha256": sha256sum(f)}
             for f in sorted(deposit_dir.iterdir())]
    if next(f["sha256"] for f in files if f["fichier"] == model_path.name) != PUBLISHED_SHA256:
        raise ValueError("Copie du modèle dans le dossier de dépôt différente de l'original")
    return {
        "adresse": SANDBOX_API if sandbox else ZENODO_API,
        "bac_a_sable": sandbox,
        "prive": private,
        "dossier": deposit_dir,
        "fichiers": files,
        "carte": text,
        "metadata_v0": metadata,
        "zenodo": _build_zenodo_metadata(dict(sent_card, id="(DOI réservé par Zenodo)"), content, private),
    }


def describe(plan: dict) -> str:
    v0 = dict(plan["metadata_v0"], description=f"(texte de la carte, {len(plan['metadata_v0']['description'])} caractères)",
              graphemes=f"({len(plan['metadata_v0']['graphemes'])} graphèmes)")
    zen = json.loads(json.dumps(plan["zenodo"]))
    zen["metadata"]["description"] = f"(carte en HTML, {len(zen['metadata']['description'])} caractères)"
    lines = [
        f"Adresse : {plan['adresse']} ({'bac à sable' if plan['bac_a_sable'] else 'Zenodo réel, DOI définitif'})",
        f"Communauté ocr_models : {'non (dépôt privé de la liste kraken)' if plan['prive'] else 'demande d’inclusion envoyée'}",
        f"Dossier préparé : {plan['dossier']}",
        "Fichiers envoyés :",
        *[f"  {f['fichier']} : {f['octets']} octets, SHA-256 {f['sha256']}" for f in plan["fichiers"]],
        f"  README.md : carte {MODEL_CARD.name} ({len(plan['carte'])} caractères), auteurs au format Zenodo, id remplacé par le DOI réservé",
        "metadata.json :",
        json.dumps(v0, ensure_ascii=False, indent=1),
        "Métadonnées Zenodo :",
        json.dumps(zen, ensure_ascii=False, indent=1),
    ]
    return "\n".join(lines)


def deposit(plan: dict, token: str) -> str:
    """Dépôt réel par htrmopo (création, envoi des fichiers, publication immédiate). Renvoie le DOI."""
    os.environ["MODEL_REPO_URL"] = plan["adresse"]  # lue par htrmopo.util.get_repo_url à chaque appel
    from htrmopo import publish_model

    return publish_model(plan["dossier"], plan["carte"], token, private=plan["prive"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--carte", action="store_true", help="valide MODEL_CARD.md sans écrire la copie")
    parser.add_argument("--zenodo", action="store_true", help="dépose le modèle publié sur Zenodo")
    parser.add_argument("--sandbox", action="store_true", help="avec --zenodo : bac à sable (sandbox.zenodo.org)")
    parser.add_argument("--private", action="store_true", help="avec --zenodo : sans demande d'inclusion à ocr_models")
    parser.add_argument("--dry-run", action="store_true", help="avec --zenodo : prépare et affiche, sans réseau")
    args = parser.parse_args()
    if args.carte:
        header = validate_card(MODEL_CARD.read_text(encoding="utf-8"))
        print(f"{MODEL_CARD.relative_to(ROOT)} : valide (schéma v1 de htrmopo), champs {sorted(header)}")
        return
    if args.zenodo:
        plan = prepare_deposit(args.sandbox, args.private)
        print(describe(plan))
        if args.dry_run:
            print("\n--dry-run : aucun appel réseau, rien n'a été envoyé.")
            return
        token = os.environ.get(TOKEN_ENV)
        if not token:
            raise SystemExit(f"Jeton absent : définir la variable d'environnement {TOKEN_ENV}")
        if not args.sandbox and input("\nPublication réelle, immédiate, DOI définitif. Taper « publier » pour confirmer : ") != "publier":
            raise SystemExit("Annulé : rien n'a été envoyé.")
        print(f"DOI : {deposit(plan, token)}")
        return
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
