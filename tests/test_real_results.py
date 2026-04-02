"""Tests against the real committed benchmark results in benchmarks/results/.

These tests assert shape, schema, and plumbing — not specific token reduction
percentages. Token reduction claims belong in docs/findings.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.harness.aggregation import load_runs_to_duckdb
from benchmarks.harness.models import RunRecord, Variant
from benchmarks.harness.reporting import generate_suite_scorecard

_RESULTS_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "results"

# ---------------------------------------------------------------------------
# Module-scoped fixtures — load real runs once
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_run_jsons() -> list[dict]:
    """Raw dicts loaded from every run.json in benchmarks/results/."""
    records = []
    for run_json in sorted(_RESULTS_DIR.rglob("run.json")):
        records.append(json.loads(run_json.read_text()))
    return records


@pytest.fixture(scope="module")
def real_runs(real_run_jsons: list[dict]) -> list[RunRecord]:
    """Real RunRecord objects deserialized from committed benchmark results."""
    return [RunRecord.model_validate(d) for d in real_run_jsons]


# ---------------------------------------------------------------------------
# Results directory basics
# ---------------------------------------------------------------------------


def test_results_dir_exists() -> None:
    assert _RESULTS_DIR.is_dir(), f"benchmarks/results/ not found at {_RESULTS_DIR}"


def test_results_dir_has_runs() -> None:
    run_files = list(_RESULTS_DIR.rglob("run.json"))
    assert len(run_files) > 0, "No run.json files found in benchmarks/results/"


def test_results_dir_run_count(real_run_jsons: list[dict]) -> None:
    """At least 20 real runs are committed."""
    assert len(real_run_jsons) >= 20


# ---------------------------------------------------------------------------
# Schema validity
# ---------------------------------------------------------------------------


def test_all_runs_deserialize(real_run_jsons: list[dict]) -> None:
    """Every run.json deserializes to a valid RunRecord without error."""
    for data in real_run_jsons:
        RunRecord.model_validate(data)  # raises on schema violation


def test_all_runs_have_run_id(real_runs: list[RunRecord]) -> None:
    for run in real_runs:
        assert run.run_id, f"run_id is empty: {run}"


def test_all_runs_have_task_id(real_runs: list[RunRecord]) -> None:
    for run in real_runs:
        assert run.task_id, f"task_id is empty: {run.run_id}"


def test_all_runs_have_family(real_runs: list[RunRecord]) -> None:
    for run in real_runs:
        assert run.family, f"family is empty: {run.run_id}"


def test_all_runs_have_variant(real_runs: list[RunRecord]) -> None:
    for run in real_runs:
        assert run.variant in (Variant.baseline, Variant.tool_variant), (
            f"unexpected variant: {run.variant}"
        )


def test_all_runs_have_agent_id(real_runs: list[RunRecord]) -> None:
    for run in real_runs:
        assert run.agent_id, f"agent_id is empty: {run.run_id}"


def test_all_runs_have_elapsed_seconds(real_runs: list[RunRecord]) -> None:
    for run in real_runs:
        assert run.elapsed_seconds is not None, f"elapsed_seconds missing: {run.run_id}"
        assert run.elapsed_seconds > 0, f"elapsed_seconds not positive: {run.run_id}"


# ---------------------------------------------------------------------------
# Token counts
# ---------------------------------------------------------------------------


def test_all_runs_have_total_tokens(real_runs: list[RunRecord]) -> None:
    from benchmarks.harness.models import BenchmarkTrack
    legacy_runs = [r for r in real_runs if r.track == BenchmarkTrack.legacy_agent]
    for run in legacy_runs:
        assert run.reported_total_tokens is not None, (
            f"reported_total_tokens missing: {run.run_id}"
        )


def test_completed_runs_have_positive_tokens(real_runs: list[RunRecord]) -> None:
    from benchmarks.harness.models import BenchmarkTrack, RunStatus
    legacy_runs = [r for r in real_runs if r.track == BenchmarkTrack.legacy_agent]
    for run in legacy_runs:
        if run.status == RunStatus.passed:
            assert run.reported_total_tokens is not None and run.reported_total_tokens > 0, (
                f"passed run has zero tokens: {run.run_id}"
            )


# ---------------------------------------------------------------------------
# Coverage — both variants present
# ---------------------------------------------------------------------------


def test_baseline_runs_present(real_runs: list[RunRecord]) -> None:
    from benchmarks.harness.models import BenchmarkTrack
    legacy_runs = [r for r in real_runs if r.track == BenchmarkTrack.legacy_agent]
    if not legacy_runs:
        pytest.skip("no legacy_agent runs in results — skipping baseline check")
    baselines = [r for r in legacy_runs if r.variant == Variant.baseline]
    assert len(baselines) > 0


def test_tool_variant_runs_present(real_runs: list[RunRecord]) -> None:
    variants = [r for r in real_runs if r.variant == Variant.tool_variant]
    assert len(variants) > 0


def test_equal_baseline_and_variant_counts(real_runs: list[RunRecord]) -> None:
    from benchmarks.harness.models import BenchmarkTrack
    legacy_runs = [r for r in real_runs if r.track == BenchmarkTrack.legacy_agent]
    if not legacy_runs:
        pytest.skip("no legacy_agent runs in results — skipping equal-count check")
    baselines = [r for r in legacy_runs if r.variant == Variant.baseline]
    variants = [r for r in legacy_runs if r.variant == Variant.tool_variant]
    assert len(baselines) == len(variants)


# ---------------------------------------------------------------------------
# Scorecard generation works on real data
# ---------------------------------------------------------------------------


def test_scorecard_generation_succeeds(real_runs: list[RunRecord]) -> None:
    scorecard = generate_suite_scorecard(real_runs, agent_id="claude", repo_commit="real")
    assert scorecard is not None


def test_scorecard_has_families(real_runs: list[RunRecord]) -> None:
    scorecard = generate_suite_scorecard(real_runs, agent_id="claude", repo_commit="real")
    assert len(scorecard.families) > 0


def test_scorecard_family_is_ripgrep(real_runs: list[RunRecord]) -> None:
    scorecard = generate_suite_scorecard(real_runs, agent_id="claude", repo_commit="real")
    family_names = [f.family for f in scorecard.families]
    assert "ripgrep" in family_names


# ---------------------------------------------------------------------------
# DuckDB ingestion
# ---------------------------------------------------------------------------


def test_duckdb_loads_real_results() -> None:
    conn = load_runs_to_duckdb(results_dir=_RESULTS_DIR)
    count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    conn.close()
    assert count >= 20


def test_duckdb_real_results_tool_variant_present() -> None:
    conn = load_runs_to_duckdb(results_dir=_RESULTS_DIR)
    variants = {
        row[0]
        for row in conn.execute("SELECT DISTINCT variant FROM runs").fetchall()
    }
    conn.close()
    assert "tool_variant" in variants
