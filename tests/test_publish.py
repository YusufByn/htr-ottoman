"""Tests de htr_ottoman.publish (copie du modèle publié, drapeau corrigé dans l'en-tête, F14)."""
import json
import struct

import pytest
import torch
from safetensors.torch import load_file, save_file

from htr_ottoman.publish import dump_header, header_differences, split_safetensors, with_legacy_flag


def fake_model(tmp_path, flag=False):
    meta = {"uuid-1": {"_model": "TorchVGSLModel", "legacy_polygons": flag, "codec": {"ا": [1], " ": [2]}}}
    path = tmp_path / "best.safetensors"
    save_file({"uuid-1.nn.w": torch.arange(6.0).reshape(2, 3)}, path, metadata={"kraken_meta": json.dumps(meta)})
    return path


def test_only_the_flag_changes(tmp_path):
    raw, data = split_safetensors(fake_model(tmp_path).read_bytes())
    new = with_legacy_flag(raw)
    assert len(new) % 8 == 0
    assert header_differences(raw, new) == {"tenseurs": [], "autres_metadonnees": [], "kraken_meta": ["legacy_polygons"]}
    # la copie se relit, tenseurs inchangés
    copy = tmp_path / "copie.safetensors"
    copy.write_bytes(struct.pack("<Q", len(new)) + new + data)
    assert torch.equal(load_file(copy)["uuid-1.nn.w"], torch.arange(6.0).reshape(2, 3))
    assert json.loads(json.loads(new)["__metadata__"]["kraken_meta"])["uuid-1"]["legacy_polygons"] is True


def test_header_reproduced_like_safetensors(tmp_path):
    raw, _ = split_safetensors(fake_model(tmp_path).read_bytes())
    assert dump_header(json.loads(raw)) == raw


def test_refuses_a_flag_already_true(tmp_path):
    raw, _ = split_safetensors(fake_model(tmp_path, flag=True).read_bytes())
    with pytest.raises(ValueError, match="attendu false"):
        with_legacy_flag(raw)


def test_card_validation_rejects_an_unknown_licence():
    from htr_ottoman.publish import validate_card

    card = "---\nsummary: s\nauthors: [{name: a}]\nlicense: LIC\nsoftware_name: kraken\nlanguage: [ota]\nscript: [Arab]\nmodel_type: [recognition]\n---\ntext\n"
    assert validate_card(card.replace("LIC", "CC-BY-NC-SA-4.0"))["license"] == "CC-BY-NC-SA-4.0"
    with pytest.raises(Exception):
        validate_card(card.replace("LIC", "CC-BY-NC-SA-9.9"))


def test_model_card_is_valid():
    from htr_ottoman.config import MODEL_CARD
    from htr_ottoman.publish import validate_card

    header = validate_card(MODEL_CARD.read_text(encoding="utf-8"))
    assert header["license"] == "CC-BY-NC-SA-4.0" and header["language"] == ["ota"] and header["script"] == ["Arab"]
    assert header["summary"] == "Ottoman Turkish handwritten naskh, fine-tuned on MAKHZAN (v0.1.0)"


# --- dépôt Zenodo (htrmopo.publish_model), sans aucun appel réseau ---

import requests  # noqa: E402

from htr_ottoman import publish  # noqa: E402
from htr_ottoman.config import MODEL_CARD, PUBLISHED_MODEL  # noqa: E402

needs_model = pytest.mark.skipif(not PUBLISHED_MODEL.exists(), reason="modèle publié absent : uv run python -m htr_ottoman.publish")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("appel réseau interdit dans les tests")
    for name in ["request", "get", "post", "put"]:
        monkeypatch.setattr(requests, name, refuse)
    monkeypatch.setattr(requests.Session, "request", refuse)


def test_v0_metadata_uses_the_card_cer(tmp_path):
    card = {"summary": "s", "license": "CC-BY-NC-SA-4.0", "script": ["Arab"], "metrics": {"cer": 26.33}}
    model = fake_model(tmp_path, flag=True)
    data = publish.v0_metadata(card, "texte", model)
    assert data["accuracy"] == 73.67  # 100 − CER de la carte, pas de CER kraken
    assert data["graphemes"] == ["ا", " "] and data["name"] == "best.safetensors" and "authors" not in data


def test_prepare_refuses_another_model(tmp_path):
    with pytest.raises(ValueError, match="décision 45"):
        publish.prepare_deposit(True, False, model_path=fake_model(tmp_path, flag=True), deposit_dir=tmp_path / "depot")


@needs_model
def test_sandbox_plan(tmp_path):
    plan = publish.prepare_deposit(sandbox=True, private=False, deposit_dir=tmp_path / "depot")
    assert plan["adresse"] == publish.SANDBOX_API and plan["prive"]  # pas de communauté sur le bac à sable
    files = {f["fichier"]: f for f in plan["fichiers"]}
    assert set(files) == {PUBLISHED_MODEL.name, "metadata.json"}
    assert files[PUBLISHED_MODEL.name]["sha256"] == publish.PUBLISHED_SHA256
    card, _ = publish.split_card(MODEL_CARD.read_text(encoding="utf-8"))
    assert plan["metadata_v0"]["accuracy"] == round(100 - card["metrics"]["cer"], 2)
    assert len(plan["metadata_v0"]["graphemes"]) == 196
    assert "communities" not in plan["zenodo"]["metadata"]
    assert plan["zenodo"]["metadata"]["license"] == "CC-BY-NC-SA-4.0"
    assert plan["zenodo"]["metadata"]["creators"] == [{"name": "Buyukaydin, Yusuf"}]
    assert "Adresse : https://sandbox.zenodo.org/api/" in publish.describe(plan)


@needs_model
def test_real_plan_requests_the_kraken_community(tmp_path):
    plan = publish.prepare_deposit(sandbox=False, private=False, deposit_dir=tmp_path / "depot")
    assert plan["adresse"] == publish.ZENODO_API and not plan["prive"]
    assert plan["zenodo"]["metadata"]["communities"] == [{"identifier": "ocr_models"}]


def run_main(monkeypatch, tmp_path, *argv):
    monkeypatch.setattr(publish, "DEPOSIT_DIR", tmp_path / "depot")
    monkeypatch.setattr("sys.argv", ["publish", *argv])
    publish.main()


@needs_model
def test_dry_run_needs_no_token(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(publish.TOKEN_ENV, raising=False)
    run_main(monkeypatch, tmp_path, "--zenodo", "--sandbox", "--dry-run")
    assert "aucun appel réseau" in capsys.readouterr().out


@needs_model
def test_missing_token_stops_before_any_upload(monkeypatch, tmp_path):
    monkeypatch.delenv(publish.TOKEN_ENV, raising=False)
    with pytest.raises(SystemExit, match="ZENODO_TOKEN"):
        run_main(monkeypatch, tmp_path, "--zenodo", "--sandbox")


@needs_model
def test_real_deposit_requires_confirmation(monkeypatch, tmp_path):
    monkeypatch.setenv(publish.TOKEN_ENV, "jeton_factice")
    monkeypatch.setattr("builtins.input", lambda prompt: "non")
    with pytest.raises(SystemExit, match="Annulé"):
        run_main(monkeypatch, tmp_path, "--zenodo")


@needs_model
def test_deposit_calls_htrmopo_with_the_sandbox_address(monkeypatch, tmp_path):
    import htrmopo

    seen = {}

    def fake_publish_model(model, model_card, access_token, private=False, **kwargs):
        from htrmopo.util import get_repo_url
        seen.update(model=model, card=model_card, token=access_token, private=private, url=get_repo_url())
        return "10.5072/zenodo.1"

    monkeypatch.setattr(htrmopo, "publish_model", fake_publish_model)
    monkeypatch.setenv("MODEL_REPO_URL", "http://127.0.0.1:9/api/")  # remis à l'état initial après le test
    plan = publish.prepare_deposit(sandbox=True, private=False, deposit_dir=tmp_path / "depot")
    assert publish.deposit(plan, "jeton_factice") == "10.5072/zenodo.1"
    assert seen["url"] == publish.SANDBOX_API and seen["private"] and seen["token"] == "jeton_factice"
    assert seen["model"] == tmp_path / "depot" and seen["card"] == plan["carte"]
    sent, content = publish.split_card(seen["card"])
    card, original_content = publish.split_card(MODEL_CARD.read_text(encoding="utf-8"))
    assert sent == dict(card, authors=[{"name": "Buyukaydin, Yusuf"}]) and content == original_content


def test_zenodo_creators_use_family_name_first(tmp_path):
    card = {"summary": "s", "authors": [{"name": "Yusuf Buyukaydin"}], "license": "CC-BY-NC-SA-4.0",
            "software_name": "kraken", "language": ["ota"], "script": ["Arab"], "model_type": ["recognition"]}
    sent, text = publish.zenodo_card(card, "texte")
    assert sent["authors"] == [{"name": "Buyukaydin, Yusuf"}] and card["authors"] == [{"name": "Yusuf Buyukaydin"}]
    with pytest.raises(ValueError, match="ZENODO_CREATOR_NAMES"):
        publish.zenodo_card(dict(card, authors=[{"name": "Autre Auteur"}]), "texte")
