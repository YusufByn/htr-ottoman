"""Tests de la table des lignes MAKHZAN (htr_ottoman.data.makhzan)."""
import pandas as pd
import pytest

from htr_ottoman.config import MAKHZAN_LINES, MAKHZAN_METADATA
from htr_ottoman.data.makhzan import check_lines, load_metadata, ottoman_pages

needs_table = pytest.mark.skipif(
    not (MAKHZAN_LINES.exists() and MAKHZAN_METADATA.exists()),
    reason="table des lignes absente : lancer uv run python -m htr_ottoman.data.makhzan",
)


@pytest.fixture(scope="module")
def data():
    return pd.read_parquet(MAKHZAN_LINES), ottoman_pages(load_metadata())


@needs_table
def test_table_matches_tsv(data):
    lines, pages = data
    assert lines["part_id"].nunique() == 248
    assert lines["doc_id"].nunique() == 30
    assert len(lines) == 3868 and (~lines["is_empty"]).sum() == 3762
    check_lines(lines, pages)  # effectifs par page identiques au TSV


@needs_table
def test_check_lines_detects_mismatch(data):
    lines, pages = data
    tampered = lines.drop(index=lines.index[0])  # une ligne en moins
    with pytest.raises(ValueError):
        check_lines(tampered, pages)


@needs_table
def test_model_layer_pages(data):
    lines, _ = data
    model = lines[lines["is_model_layer"]]
    assert set(model["doc_id"]) == {83, 6398}
    assert model["part_id"].nunique() == 18


@needs_table
def test_no_missing_metadata(data):
    lines, _ = data
    for col in ["work", "script", "category", "dataset_source", "language", "layer"]:
        assert lines[col].notna().all() and (lines[col].str.strip() != "").all(), col
