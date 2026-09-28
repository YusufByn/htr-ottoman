"""Tests du découpage (htr_ottoman.splits) : reproductibilité et étanchéité."""
import pytest

from htr_ottoman.config import MAKHZAN_METADATA, SPLITS
from htr_ottoman.data.makhzan import load_metadata, ottoman_pages
from htr_ottoman.splits import SPLIT_NAMES, assign, load_split, render, summary, validate

pytestmark = pytest.mark.skipif(not MAKHZAN_METADATA.exists(), reason="TSV MAKHZAN absent de data/raw/")


@pytest.fixture(scope="module")
def pages():
    return ottoman_pages(load_metadata())


@pytest.fixture(scope="module")
def assignment(pages):
    return assign(pages)


@pytest.mark.parametrize("name", SPLIT_NAMES)
def test_files_are_reproducible(assignment, name):
    # Les fichiers versionnés sont identiques octet pour octet à une régénération
    assert (SPLITS / f"{name}.csv").read_text(encoding="utf-8") == render(assignment, name)


def test_validate_passes(assignment, pages):
    validate(assignment, len(pages))


@pytest.mark.parametrize("group", ["work", "doc_id", "shelfmark"])
def test_no_group_shared_between_splits(assignment, group):
    assert (assignment.groupby(group)["split"].nunique() == 1).all()


def test_docs_86_and_89_together(assignment):
    assert assignment.loc[assignment["doc_id"].isin([86, 89]), "split"].nunique() == 1


def test_every_page_assigned_once(assignment, pages):
    assert len(assignment) == len(pages) == 248
    assert not assignment["part_id"].duplicated().any()


def test_split_sizes(assignment, pages):
    s = summary(assignment, pages)
    assert s.loc["train", ["manuscrits", "pages", "lignes_transcrites"]].tolist() == [11, 199, 2771]
    assert s.loc["val", ["manuscrits", "pages", "lignes_transcrites"]].tolist() == [2, 19, 436]
    assert s.loc["test_interne", ["manuscrits", "pages", "lignes_transcrites"]].tolist() == [17, 30, 555]


def test_multilingual_pages_only_in_internal_test(assignment):
    multi = assignment[assignment["is_multilingual"]]
    assert len(multi) == 7 and set(multi["split"]) == {"test_interne"}


def test_validate_detects_leak(assignment, pages):
    # Une copie de Dāsitān-i Kesik Baş déplacée en validation : l'œuvre serait partagée
    leaked = assignment.copy()
    leaked.loc[leaked["doc_id"] == 82, "split"] = "val"
    with pytest.raises(ValueError):
        validate(leaked, len(pages))


def test_validate_detects_separated_linked_docs(assignment, pages):
    separated = assignment.copy()
    separated.loc[separated["doc_id"] == 89, ["split", "work"]] = ["test_interne", "œuvre fictive"]
    with pytest.raises(ValueError):
        validate(separated, len(pages))


@pytest.mark.parametrize("name", SPLIT_NAMES)
def test_load_split_roundtrip(assignment, name):
    loaded = load_split(name)
    expected = assignment[assignment["split"] == name]
    assert loaded["part_id"].tolist() == expected["part_id"].tolist()
