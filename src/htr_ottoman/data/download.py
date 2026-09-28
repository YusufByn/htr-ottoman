"""Téléchargement idempotent avec vérification de l'empreinte (MD5 par défaut,
SHA-256 pour les fichiers git LFS).

- Fichier présent et empreinte valide : rien n'est fait.
- Fichier présent mais empreinte invalide : arrêt avec une erreur, rien n'est supprimé.
- Fichier absent : téléchargement dans un fichier temporaire .part, vérification
  de l'empreinte, renommage, puis mise en lecture seule.
"""
import contextlib
import hashlib
import os
import stat
import urllib.request
from pathlib import Path

CHUNK = 1 << 20  # 1 Mo


class ChecksumError(RuntimeError):
    """L'empreinte d'un fichier ne correspond pas à celle attendue."""


def file_hash(path: Path, algo: str = "md5") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def md5sum(path: Path) -> str:
    return file_hash(path, "md5")


@contextlib.contextmanager
def writable_dir(directory: Path):
    """Rend un dossier temporairement modifiable (data/raw/ est en lecture seule)."""
    mode = directory.stat().st_mode
    if not mode & stat.S_IWUSR:
        directory.chmod(mode | stat.S_IWUSR)
    try:
        yield
    finally:
        directory.chmod(mode)


def ensure_file(url: str, dest: Path, md5: str, algo: str = "md5") -> str:
    """Garantit que `dest` existe avec l'empreinte attendue (`md5`, calculée avec
    `algo`). Renvoie "présent" ou "téléchargé"."""
    name = algo.upper()
    if dest.exists():
        actual = file_hash(dest, algo)
        if actual != md5:
            raise ChecksumError(f"{dest} : {name} {actual}, attendu {md5}. Fichier laissé intact.")
        return "présent"

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with writable_dir(dest.parent):
        with urllib.request.urlopen(url) as response, open(part, "wb") as out:
            while chunk := response.read(CHUNK):
                out.write(chunk)
        actual = file_hash(part, algo)
        if actual != md5:
            part.unlink()  # fichier temporaire, jamais un fichier de data/raw/
            raise ChecksumError(f"{url} : {name} téléchargé {actual}, attendu {md5}.")
        os.replace(part, dest)
        dest.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return "téléchargé"
