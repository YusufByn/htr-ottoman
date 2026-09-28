"""Téléchargement idempotent avec vérification MD5.

- Fichier présent et MD5 valide : rien n'est fait.
- Fichier présent mais MD5 invalide : arrêt avec une erreur, rien n'est supprimé.
- Fichier absent : téléchargement dans un fichier temporaire .part, vérification
  du MD5, renommage, puis mise en lecture seule.
"""
import contextlib
import hashlib
import os
import stat
import urllib.request
from pathlib import Path

CHUNK = 1 << 20  # 1 Mo


class ChecksumError(RuntimeError):
    """Le MD5 d'un fichier ne correspond pas à celui attendu."""


def md5sum(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


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


def ensure_file(url: str, dest: Path, md5: str) -> str:
    """Garantit que `dest` existe avec le MD5 attendu. Renvoie "présent" ou "téléchargé"."""
    if dest.exists():
        actual = md5sum(dest)
        if actual != md5:
            raise ChecksumError(f"{dest} : MD5 {actual}, attendu {md5}. Fichier laissé intact.")
        return "présent"

    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    with writable_dir(dest.parent):
        with urllib.request.urlopen(url) as response, open(part, "wb") as out:
            while chunk := response.read(CHUNK):
                out.write(chunk)
        actual = md5sum(part)
        if actual != md5:
            part.unlink()  # fichier temporaire, jamais un fichier de data/raw/
            raise ChecksumError(f"{url} : MD5 téléchargé {actual}, attendu {md5}.")
        os.replace(part, dest)
        dest.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return "téléchargé"
