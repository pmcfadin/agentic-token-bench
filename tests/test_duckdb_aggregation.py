"""Tests for benchmarks.harness.aggregation (DuckDB-backed result aggregation)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from benchmarks.harness.aggregation import (
    compute_family_summary,
    export_csv,
    load_runs_to_duckdb,
    query_runs,
)
from benchmarks.harness.models import (
    RunRecord,
    RunStatus,
    RunValidity,
    Variant,
    ValidationStatus,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_run(
    *,
    run_id: str,
    family: str,
    variant: Variant,
    validity: RunValidity = RunValidity.valid,
    validation_status: ValidationStatus = ValidationStatus.passed,
    reported_total_tokens: int | None = None,
    repair_iterations: int = 0,
    elapsed_seconds: float | None = None,
    agent_id: str = "ClaudeAdapter",
    repo_commit: str = "abc1234",
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        task_id=f"task-{run_id}",
        family=family,
        variant=variant,
        agent_id=agent_id,
        adapter_version="0.1.0",
        repo_commit=repo_commit,
        status=RunStatus.passed,
        validity=validity,
        reported_total_tokens=reported_total_tokens,
        elapsed_seconds=elapsed_seconds,
        repair_iterations=repair_iterations,
        validation_status=validation_status,
    )


# Fixture pilot run directory
PILOT_RUNS_DIR = Path(__file__).parent / "fixtures" / "pilot_runs"


@pytest.fixture()
def pilot_runs() -> list[RunRecord]:
    """Load all four pilot run fixture JSON files as RunRecord objects."""
    records: list[RunRecord] = []
    for json_path in sorted(PILOT_RUNS_DIR.glob("*.json")):
        data = json.loads(json_path.read_text())
        records.append(RunRecord.model_validate(data))
    return records


@pytest.fixture()
def pilot_conn(pilot_runs: list[RunRecord]):
    """DuckDB connection loaded with all pilot fixture runs."""
    conn = load_runs_to_duckdb(runs=pilot_runs)
    yield conn
    conn.close()


@pytest.fixture()
def mixed_runs() -> list[RunRecord]:
    """Mixed set of runs across two families and two agents with one invalid run."""
    return [
        # ripgrep family — baseline
        _make_run(run_id="rg-b1", family="ripgrep", variant=Variant.baseline,
                  reported_total_tokens=10000, elapsed_seconds=40.0, repair_iterations=0),
        _make_run(run_id="rg-b2", family="ripgrep", variant=Variant.baseline,
                  reported_total_tokens=12000, elapsed_seconds=42.0, repair_iterations=1,
                  validation_status=ValidationStatus.failed),
        # ripgrep family — tool_variant
        _make_run(run_id="rg-v1", family="ripgrep", variant=Variant.tool_variant,
                  reported_total_tokens=5000, elapsed_seconds=25.0, repair_iterations=0),
        _make_run(run_id="rg-v2", family="ripgrep", variant=Variant.tool_variant,
                  reported_total_tokens=6000, elapsed_seconds=27.0, repair_iterations=0),
        # rtk family — baseline (different agent)
        _make_run(run_id="rtk-b1", family="rtk", variant=Variant.baseline,
                  reported_total_tokens=9000, elapsed_seconds=35.0, repair_iterations=0,
                  agent_id="OtherAdapter"),
        # invalid run — should be excluded from valid_only queries
        _make_run(run_id="rg-invalid", family="ripgrep", variant=Variant.baseline,
                  validity=RunValidity.invalid, reported_total_tokens=999999),
    ]


@pytest.fixture()
def mixed_conn(mixed_runs: list[RunRecord]):
    conn = load_runs_to_duckdb(runs=mixed_runs)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# load_runs_to_duckdb — loading from list
# ---------------------------------------------------------------------------


class TestLoadRunsFromList:
    def test_table_exists(self, pilot_conn) -> None:
        result = pilot_conn.execute("SELECT COUNT(*) FROM runs").fetchone()
        assert result is not None
        assert result[0] == 4

    def test_all_pilot_runs_loaded(self, pilot_runs: list[RunRecord]) -> None:
        conn = load_runs_to_duckdb(runs=pilot_runs)
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.close()
        assert count == len(pilot_runs)

    def test_empty_list_creates_empty_table(self) -> None:
        conn = load_runs_to_duckdb(runs=[])
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.close()
        assert count == 0

    def test_family_values_stored(self, pilot_conn) -> None:
        families = {row[0] for row in pilot_conn.execute("SELECT DISTINCT family FROM runs").fetchall()}
        assert families == {"ripgrep"}

    def test_variant_values_stored(self, pilot_conn) -> None:
        variants = {row[0] for row in pilot_conn.execute("SELECT DISTINCT variant FROM runs").fetchall()}
        assert variants == {"baseline", "tool_variant"}

    def test_raises_when_no_source_provided(self) -> None:
        with pytest.raises(ValueError, match="Either runs or results_dir must be provided"):
            load_runs_to_duckdb()


# ---------------------------------------------------------------------------
# load_runs_to_duckdb — loading from results_dir
# ---------------------------------------------------------------------------


class TestLoadRunsFromDir:
    def test_scans_run_json_files(self, tmp_path: Path) -> None:
        """Files named run.json inside sub-directories are picked up."""
        run_data = {
            "run_id": "test-run-01",
            "task_id": "test-task-01",
            "family": "ripgrep",
            "variant": "baseline",
            "agent_id": "ClaudeAdapter",
            "adapter_version": "0.1.0",
            "repo_commit": "deadbeef",
            "status": "passed",
            "validity": "valid",
            "repair_iterations": 0,
            "validation_status": "passed",
            "files_changed": 0,
            "diff_size": 0,
            "artifact_dir": "",
        }
        run_dir = tmp_path / "run-001"
        run_dir.mkdir()
        (run_dir / "run.json").write_text(json.dumps(run_data))

        conn = load_runs_to_duckdb(results_dir=tmp_path)
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.close()
        assert count == 1

    def test_ignores_invalid_json_files(self, tmp_path: Path) -> None:
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "run.json").write_text("not valid json")

        conn = load_runs_to_duckdb(results_dir=tmp_path)
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.close()
        assert count == 0

    def test_empty_directory_creates_empty_table(self, tmp_path: Path) -> None:
        conn = load_runs_to_duckdb(results_dir=tmp_path)
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.close()
        assert count == 0


# ---------------------------------------------------------------------------
# query_runs — filtering
# ---------------------------------------------------------------------------


class TestQueryRuns:
    def test_returns_list_of_dicts(self, pilot_conn) -> None:
        results = query_runs(pilot_conn)
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)

    def test_all_valid_runs_returned_by_default(self, pilot_conn) -> None:
        results = query_runs(pilot_conn)
        # All pilot runs are valid
        assert len(results) == 4

    def test_filter_by_family(self, mixed_conn) -> None:
        results = query_runs(mixed_conn, family="rtk")
        assert all(r["family"] == "rtk" for r in results)
        assert len(results) == 1

    def test_filter_by_variant_baseline(self, mixed_conn) -> None:
        results = query_runs(mixed_conn, variant="baseline")
        assert all(r["variant"] == "baseline" for r in results)

    def test_filter_by_variant_tool_variant(self, mixed_conn) -> None:
        results = query_runs(mixed_conn, variant="tool_variant")
        assert all(r["variant"] == "tool_variant" for r in results)

    def test_filter_by_agent(self, mixed_conn) -> None:
        results = query_runs(mixed_conn, agent="OtherAdapter")
        assert all(r["agent_id"] == "OtherAdapter" for r in results)
        assert len(results) == 1

    def test_valid_only_excludes_invalid_runs(self, mixed_conn) -> None:
        results = query_runs(mixed_conn, valid_only=True)
        assert all(r["validity"] == "valid" for r in results)

    def test_valid_only_false_includes_invalid_runs(self, mixed_conn) -> None:
        all_results = query_runs(mixed_conn, valid_only=False)
        invalid_results = [r for r in all_results if r["validity"] == "invalid"]
        assert len(invalid_results) == 1

    def test_combined_filters_family_and_variant(self, mixed_conn) -> None:
        results = query_runs(mixed_conn, family="ripgrep", variant="tool_variant")
        assert all(r["family"] == "ripgrep" and r["variant"] == "tool_variant" for r in results)
        assert len(results) == 2

    def test_empty_result_for_nonexistent_family(self, mixed_conn) -> None:
        results = query_runs(mixed_conn, family="does_not_exist")
        assert results == []

    def test_result_dicts_contain_expected_keys(self, pilot_conn) -> None:
        results = query_runs(pilot_conn)
        assert len(results) > 0
        expected_keys = {"run_id", "task_id", "family", "variant", "agent_id", "validity"}
        assert expected_keys.issubset(results[0].keys())


# ---------------------------------------------------------------------------
# compute_family_summary
# ---------------------------------------------------------------------------


class TestComputeFamilySummary:
    def test_returns_dict(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        assert isinstance(summary, dict)

    def test_family_name_in_summary(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        assert summary["family"] == "ripgrep"

    def test_summary_has_baseline_and_tool_variant(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        assert "baseline" in summary
        assert "tool_variant" in summary

    def test_baseline_run_count(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        assert summary["baseline"]["run_count"] == 2

    def test_tool_variant_run_count(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        assert summary["tool_variant"]["run_count"] == 2

    def test_baseline_avg_tokens(self, pilot_conn) -> None:
        # Pilot fixtures: 15200 and 14400 for baseline
        summary = compute_family_summary(pilot_conn, "ripgrep")
        expected = (15200 + 14400) / 2
        assert summary["baseline"]["avg_tokens"] == pytest.approx(expected)

    def test_tool_variant_avg_tokens(self, pilot_conn) -> None:
        # Pilot fixtures: 8000 and 7800 for tool_variant
        summary = compute_family_summary(pilot_conn, "ripgrep")
        expected = (8000 + 7800) / 2
        assert summary["tool_variant"]["avg_tokens"] == pytest.approx(expected)

    def test_token_delta_is_variant_minus_baseline(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        expected_delta = summary["tool_variant"]["avg_tokens"] - summary["baseline"]["avg_tokens"]
        assert summary["token_delta"] == pytest.approx(expected_delta)

    def test_token_delta_is_negative(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        assert summary["token_delta"] < 0

    def test_token_reduction_pct_formula(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        expected_pct = summary["token_delta"] / summary["baseline"]["avg_tokens"] * 100
        assert summary["token_reduction_pct"] == pytest.approx(expected_pct)

    def test_token_reduction_pct_is_negative(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        assert summary["token_reduction_pct"] < 0

    def test_pass_rate_all_passed(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        # All pilot runs have validation_status = "passed"
        assert summary["baseline"]["pass_rate"] == pytest.approx(1.0)
        assert summary["tool_variant"]["pass_rate"] == pytest.approx(1.0)

    def test_avg_elapsed_seconds_baseline(self, pilot_conn) -> None:
        # Pilot fixtures: 46.3 and 43.8 for baseline
        summary = compute_family_summary(pilot_conn, "ripgrep")
        expected = (46.3 + 43.8) / 2
        assert summary["baseline"]["avg_elapsed_seconds"] == pytest.approx(expected)

    def test_avg_repair_iterations_zero(self, pilot_conn) -> None:
        summary = compute_family_summary(pilot_conn, "ripgrep")
        assert summary["baseline"]["avg_repair_iterations"] == pytest.approx(0.0)
        assert summary["tool_variant"]["avg_repair_iterations"] == pytest.approx(0.0)

    def test_token_delta_none_when_no_tokens(self) -> None:
        runs = [
            _make_run(run_id="b1", family="no-tokens", variant=Variant.baseline,
                      reported_total_tokens=None),
            _make_run(run_id="v1", family="no-tokens", variant=Variant.tool_variant,
                      reported_total_tokens=None),
        ]
        conn = load_runs_to_duckdb(runs=runs)
        summary = compute_family_summary(conn, "no-tokens")
        conn.close()
        assert summary["token_delta"] is None
        assert summary["token_reduction_pct"] is None

    def test_nonexistent_family_returns_zero_run_counts(self) -> None:
        conn = load_runs_to_duckdb(runs=[])
        summary = compute_family_summary(conn, "ghost-family")
        conn.close()
        assert summary["baseline"]["run_count"] == 0
        assert summary["tool_variant"]["run_count"] == 0
        assert summary["token_delta"] is None


# ---------------------------------------------------------------------------
# export_csv
# ---------------------------------------------------------------------------


class TestExportCsv:
    def test_creates_file(self, pilot_conn, tmp_path: Path) -> None:
        out = tmp_path / "runs.csv"
        returned_path = export_csv(pilot_conn, out)
        assert returned_path.exists()

    def test_returns_resolved_path(self, pilot_conn, tmp_path: Path) -> None:
        out = tmp_path / "runs.csv"
        returned_path = export_csv(pilot_conn, out)
        assert returned_path.is_absolute()

    def test_csv_has_header_row(self, pilot_conn, tmp_path: Path) -> None:
        out = tmp_path / "runs.csv"
        export_csv(pilot_conn, out)
        with open(out, newline="") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
        assert headers is not None
        assert "run_id" in headers
        assert "family" in headers
        assert "variant" in headers

    def test_csv_row_count_matches_table(self, pilot_conn, tmp_path: Path) -> None:
        out = tmp_path / "runs.csv"
        export_csv(pilot_conn, out)
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 4  # all pilot fixture runs

    def test_csv_with_custom_query(self, pilot_conn, tmp_path: Path) -> None:
        out = tmp_path / "baseline.csv"
        export_csv(pilot_conn, out, query="SELECT * FROM runs WHERE variant = 'baseline'")
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert all(r["variant"] == "baseline" for r in rows)
        assert len(rows) == 2

    def test_csv_empty_table(self, tmp_path: Path) -> None:
        conn = load_runs_to_duckdb(runs=[])
        out = tmp_path / "empty.csv"
        export_csv(conn, out)
        conn.close()
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert rows == []
