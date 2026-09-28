"""Tests de htr_ottoman.data.download, sans réseau (URL file:// locale)."""
import hashlib
import stat

import pytest

from htr_ottoman.data import download
from htr_ottoman.data.download import ChecksumError, ensure_file

CONTENT = b"contenu de test"
MD5 = hashlib.md5(CONTENT).hexdigest()


@pytest.fixture
def source(tmp_path):
    src = tmp_path / "server" / "file.bin"
    src.parent.mkdir()
    src.write_bytes(CONTENT)
    return src.as_uri()


@pytest.fixture
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("téléchargement appelé alors que le fichier est présent")

    monkeypatch.setattr(download.urllib.request, "urlopen", fail)


def test_missing_file_is_downloaded_and_read_only(tmp_path, source):
    dest = tmp_path / "raw" / "file.bin"
    assert ensure_file(source, dest, MD5) == "téléchargé"
    assert dest.read_bytes() == CONTENT
    assert not dest.stat().st_mode & stat.S_IWUSR
    assert not (tmp_path / "raw" / "file.bin.part").exists()


def test_present_and_valid_is_not_downloaded_again(tmp_path, no_network):
    dest = tmp_path / "file.bin"
    dest.write_bytes(CONTENT)
    assert ensure_file("https://example.invalid/file.bin", dest, MD5) == "présent"


def test_present_but_invalid_raises_and_keeps_file(tmp_path, no_network):
    dest = tmp_path / "file.bin"
    dest.write_bytes(b"fichier corrompu")
    with pytest.raises(ChecksumError):
        ensure_file("https://example.invalid/file.bin", dest, MD5)
    assert dest.read_bytes() == b"fichier corrompu"  # rien n'est supprimé


def test_wrong_md5_after_download_leaves_nothing(tmp_path, source):
    dest = tmp_path / "raw" / "file.bin"
    with pytest.raises(ChecksumError):
        ensure_file(source, dest, "0" * 32)
    assert not dest.exists()
    assert not (tmp_path / "raw" / "file.bin.part").exists()


def test_read_only_directory_is_restored(tmp_path, source):
    raw = tmp_path / "raw"
    raw.mkdir()
    raw.chmod(0o555)
    try:
        ensure_file(source, raw / "file.bin", MD5)
        assert not raw.stat().st_mode & stat.S_IWUSR  # toujours en lecture seule
    finally:
        raw.chmod(0o755)
        (raw / "file.bin").chmod(0o644)


def test_sha256_for_lfs_files(tmp_path, source):
    dest = tmp_path / "raw" / "file.bin"
    sha256 = hashlib.sha256(CONTENT).hexdigest()
    with pytest.raises(ChecksumError, match="SHA256"):
        ensure_file(source, dest, MD5, algo="sha256")  # un MD5 n'est pas un SHA-256
    assert ensure_file(source, dest, sha256, algo="sha256") == "téléchargé"
    assert ensure_file(source, dest, sha256, algo="sha256") == "présent"
