"""Tests for the export-data CLI command.

Verifies shape, correctness, and ordering of benchmark-data.json generated
from the committed tool-efficacy-scorecard.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from benchmarks.harness.cli import app

_RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "results"
_TASKS_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "tasks" / "cassandra" / "v2"
_SCORECARD = _RESULTS_DIR / "tool-efficacy-scorecard.json"


@pytest.fixture(scope="module")
def benchmark_data(tmp_path_factory) -> dict:
    """Run export-data against real scorecard and return parsed output."""
    out = tmp_path_factory.mktemp("export") / "benchmark-data.json"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "export-data",
            str(_RESULTS_DIR),
            "--tasks-dir", str(_TASKS_DIR),
            "--output-path", str(out),
        ],
    )
    assert result.exit_code == 0, f"export-data failed:\n{result.output}"
    return json.loads(out.read_text())


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------


def test_scorecard_exists() -> None:
    assert _SCORECARD.exists(), f"tool-efficacy-scorecard.json not found at {_SCORECARD}"


def test_tasks_dir_exists() -> None:
    assert _TASKS_DIR.is_dir(), f"v2 tasks directory not found at {_TASKS_DIR}"


# ---------------------------------------------------------------------------
# Top-level shape
# ---------------------------------------------------------------------------


def test_has_generated_at(benchmark_data: dict) -> None:
    assert "generated_at" in benchmark_data
    assert benchmark_data["generated_at"]


def test_has_repo_commit(benchmark_data: dict) -> None:
    assert "repo_commit" in benchmark_data
    assert benchmark_data["repo_commit"]


def test_has_tools_list(benchmark_data: dict) -> None:
    assert "tools" in benchmark_data
    assert isinstance(benchmark_data["tools"], list)
    assert len(benchmark_data["tools"]) > 0


# ---------------------------------------------------------------------------
# Per-tool shape
# ---------------------------------------------------------------------------


def test_all_tools_have_required_fields(benchmark_data: dict) -> None:
    required = {"family", "use_case", "sample_command", "avg_raw_tokens", "avg_reduced_tokens", "reduction_pct", "deterministic_pass_rate"}
    for tool in benchmark_data["tools"]:
        missing = required - tool.keys()
        assert not missing, f"tool {tool.get('family')} missing fields: {missing}"


def test_all_tools_have_nonempty_family(benchmark_data: dict) -> None:
    for tool in benchmark_data["tools"]:
        assert tool["family"], "tool has empty family"


def test_all_tools_have_nonempty_use_case(benchmark_data: dict) -> None:
    for tool in benchmark_data["tools"]:
        assert tool["use_case"], f"tool {tool['family']} has empty use_case"


def test_all_tools_have_nonempty_sample_command(benchmark_data: dict) -> None:
    for tool in benchmark_data["tools"]:
        assert tool["sample_command"], f"tool {tool['family']} has empty sample_command"


def test_reduction_pct_in_valid_range(benchmark_data: dict) -> None:
    for tool in benchmark_data["tools"]:
        pct = tool["reduction_pct"]
        assert 0 < pct < 100, f"tool {tool['family']} has out-of-range reduction_pct: {pct}"


def test_avg_reduced_tokens_less_than_raw(benchmark_data: dict) -> None:
    for tool in benchmark_data["tools"]:
        assert tool["avg_reduced_tokens"] < tool["avg_raw_tokens"], (
            f"tool {tool['family']}: reduced >= raw tokens"
        )


def test_deterministic_pass_rate_valid(benchmark_data: dict) -> None:
    for tool in benchmark_data["tools"]:
        rate = tool["deterministic_pass_rate"]
        assert rate is not None, f"tool {tool['family']} missing deterministic_pass_rate"
        assert 0.0 <= rate <= 1.0, f"tool {tool['family']} pass rate out of range: {rate}"


# ---------------------------------------------------------------------------
# Expected families present
# ---------------------------------------------------------------------------


def test_expected_families_present(benchmark_data: dict) -> None:
    families = {t["family"] for t in benchmark_data["tools"]}
    expected = {"rtk", "qmd", "ripgrep", "comby", "ast-grep", "fastmod"}
    assert expected == families, f"families mismatch: got {families}"


# ---------------------------------------------------------------------------
# Sorted by reduction_pct descending
# ---------------------------------------------------------------------------


def test_tools_sorted_by_reduction_pct_descending(benchmark_data: dict) -> None:
    pcts = [t["reduction_pct"] for t in benchmark_data["tools"]]
    assert pcts == sorted(pcts, reverse=True), f"tools not sorted descending: {pcts}"


def test_qmd_is_first(benchmark_data: dict) -> None:
    """qmd has the highest reduction percentage."""
    assert benchmark_data["tools"][0]["family"] == "qmd"


def test_fastmod_is_last(benchmark_data: dict) -> None:
    """fastmod has the lowest reduction percentage of the six tools."""
    assert benchmark_data["tools"][-1]["family"] == "fastmod"


# ---------------------------------------------------------------------------
# Missing scorecard exits cleanly
# ---------------------------------------------------------------------------


def test_missing_scorecard_exits_nonzero(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["export-data", str(tmp_path)])
    assert result.exit_code != 0
