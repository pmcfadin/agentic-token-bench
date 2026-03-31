"""Tests for load_manifest and the 6 existing tool manifests."""

from pathlib import Path

import pytest

from tools.base import ToolManifest, load_manifest

TOOLS_DIR = Path(__file__).parent.parent / "tools"

MANIFEST_PATHS = [
    TOOLS_DIR / "qmd" / "manifest.yaml",
    TOOLS_DIR / "rtk" / "manifest.yaml",
    TOOLS_DIR / "fastmod" / "manifest.yaml",
    TOOLS_DIR / "ast_grep" / "manifest.yaml",
    TOOLS_DIR / "comby" / "manifest.yaml",
    TOOLS_DIR / "ripgrep" / "manifest.yaml",
]

VALID_CATEGORIES = {"discovery", "retrieval", "output_compression", "transformation", "validation"}
VALID_WASTE_CLASSES = {
    "discovery_waste",
    "retrieval_waste",
    "execution_output_waste",
    "transformation_waste",
    "validation_waste",
}
VALID_RISK_LEVELS = {"low", "medium", "high"}


@pytest.mark.parametrize("manifest_path", MANIFEST_PATHS, ids=lambda p: p.parent.name)
def test_manifest_returns_tool_manifest(manifest_path: Path) -> None:
    """load_manifest returns a ToolManifest for each existing tool."""
    result = load_manifest(manifest_path)
    assert isinstance(result, ToolManifest)


@pytest.mark.parametrize("manifest_path", MANIFEST_PATHS, ids=lambda p: p.parent.name)
def test_manifest_required_fields_are_non_empty(manifest_path: Path) -> None:
    """All required string fields are non-empty strings."""
    m = load_manifest(manifest_path)
    assert m.id and isinstance(m.id, str)
    assert m.name and isinstance(m.name, str)
    assert m.version and isinstance(m.version, str)
    assert m.category and isinstance(m.category, str)
    assert m.description and isinstance(m.description, str)


@pytest.mark.parametrize("manifest_path", MANIFEST_PATHS, ids=lambda p: p.parent.name)
def test_manifest_category_is_valid(manifest_path: Path) -> None:
    """category must be one of the allowed values."""
    m = load_manifest(manifest_path)
    assert m.category in VALID_CATEGORIES, (
        f"{manifest_path}: category {m.category!r} not in {VALID_CATEGORIES}"
    )


@pytest.mark.parametrize("manifest_path", MANIFEST_PATHS, ids=lambda p: p.parent.name)
def test_manifest_waste_classes_are_valid(manifest_path: Path) -> None:
    """Every entry in waste_classes must be a known value."""
    m = load_manifest(manifest_path)
    for wc in m.waste_classes:
        assert wc in VALID_WASTE_CLASSES, (
            f"{manifest_path}: waste_class {wc!r} not in {VALID_WASTE_CLASSES}"
        )


@pytest.mark.parametrize("manifest_path", MANIFEST_PATHS, ids=lambda p: p.parent.name)
def test_manifest_risk_level_is_valid(manifest_path: Path) -> None:
    """risk_level must be low, medium, or high."""
    m = load_manifest(manifest_path)
    assert m.risk_level in VALID_RISK_LEVELS, (
        f"{manifest_path}: risk_level {m.risk_level!r} not in {VALID_RISK_LEVELS}"
    )


@pytest.mark.parametrize("manifest_path", MANIFEST_PATHS, ids=lambda p: p.parent.name)
def test_manifest_optional_list_fields_are_lists(manifest_path: Path) -> None:
    """supported_languages, waste_classes, and dependencies are lists."""
    m = load_manifest(manifest_path)
    assert isinstance(m.supported_languages, list)
    assert isinstance(m.waste_classes, list)
    assert isinstance(m.dependencies, list)


def test_load_manifest_missing_file_raises() -> None:
    """load_manifest raises FileNotFoundError for a non-existent path."""
    with pytest.raises(FileNotFoundError):
        load_manifest(Path("/does/not/exist/manifest.yaml"))


def test_load_manifest_missing_required_field(tmp_path: Path) -> None:
    """load_manifest raises KeyError when a required field is absent."""
    incomplete = tmp_path / "manifest.yaml"
    incomplete.write_text("id: test\nname: Test\n")  # missing version, category, description
    with pytest.raises(KeyError):
        load_manifest(incomplete)


# ---- spot-check individual tools ----


def test_qmd_manifest_values() -> None:
    m = load_manifest(TOOLS_DIR / "qmd" / "manifest.yaml")
    assert m.id == "qmd"
    assert m.category == "retrieval"
    assert "retrieval_waste" in m.waste_classes


def test_rtk_manifest_values() -> None:
    m = load_manifest(TOOLS_DIR / "rtk" / "manifest.yaml")
    assert m.id == "rtk"
    assert m.category == "output_compression"
    assert "execution_output_waste" in m.waste_classes


def test_fastmod_manifest_values() -> None:
    m = load_manifest(TOOLS_DIR / "fastmod" / "manifest.yaml")
    assert m.id == "fastmod"
    assert m.category == "transformation"
    assert m.risk_level == "medium"


def test_ast_grep_manifest_values() -> None:
    m = load_manifest(TOOLS_DIR / "ast_grep" / "manifest.yaml")
    assert m.id == "ast-grep"
    assert m.category == "transformation"
    assert "java" in m.supported_languages


def test_comby_manifest_values() -> None:
    m = load_manifest(TOOLS_DIR / "comby" / "manifest.yaml")
    assert m.id == "comby"
    assert m.category == "transformation"
    assert m.risk_level == "medium"


def test_ripgrep_manifest_values() -> None:
    m = load_manifest(TOOLS_DIR / "ripgrep" / "manifest.yaml")
    assert m.id == "ripgrep"
    assert m.category == "discovery"
    assert "discovery_waste" in m.waste_classes
