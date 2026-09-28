"""Vérifie que le package s'installe et que les chemins pointent au bon endroit."""
from htr_ottoman import config


def test_root_is_project_root():
    assert (config.ROOT / "pyproject.toml").is_file()


def test_paths_are_inside_project():
    for path in [config.DATA_RAW, config.SPLITS, config.REPORTS, config.MAKHZAN_METADATA]:
        assert config.ROOT in path.parents
