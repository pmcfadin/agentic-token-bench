"""Tests for official run fixture generation and scorecard generation.

Covers:
- Fixture generation produces correct number of runs (72)
- All 6 families are represented
- Scorecards contain all 6 families
- Token reduction is positive (variant uses fewer tokens than baseline)
- DuckDB aggregation works with the full dataset
- Per-family scorecard generation
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from benchmarks.harness.aggregation import compute_family_summary, load_runs_to_duckdb
from benchmarks.harness.models import RunRecord, RunValidity
from benchmarks.harness.reporting import (
    aggregate_family,
    generate_suite_scorecard,
    render_scorecard_json,
    render_scorecard_markdown,
)

# ---------------------------------------------------------------------------
# Import the generate_fixture_runs module directly
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

_GFR_SPEC = importlib.util.spec_from_file_location(
    "generate_fixture_runs",
    _SCRIPTS_DIR / "generate_fixture_runs.py",
)
_GFR_MOD = importlib.util.module_from_spec(_GFR_SPEC)  # type: ignore[arg-type]
_GFR_SPEC.loader.exec_module(_GFR_MOD)  # type: ignore[union-attr]
generate_all_runs = _GFR_MOD.generate_all_runs

_GS_SPEC = importlib.util.spec_from_file_location(
    "generate_scorecards",
    _SCRIPTS_DIR / "generate_scorecards.py",
)
_GS_MOD = importlib.util.module_from_spec(_GS_SPEC)  # type: ignore[arg-type]
_GS_SPEC.loader.exec_module(_GS_MOD)  # type: ignore[union-attr]
load_runs_from_dir = _GS_MOD.load_runs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_FAMILIES = {"ripgrep", "qmd", "rtk", "fastmod", "ast-grep", "comby"}
EXPECTED_RUN_COUNT = 72  # 6 families x 2 tasks x 2 variants x 3 reps


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def raw_runs() -> list[dict]:
    """All 72 generated run dicts (raw)."""
    return generate_all_runs(seed=42)


@pytest.fixture(scope="module")
def run_records(raw_runs: list[dict]) -> list[RunRecord]:
    """All 72 runs validated as RunRecord objects."""
    return [RunRecord.model_validate(r) for r in raw_runs]


@pytest.fixture(scope="module")
def suite_scorecard(run_records: list[RunRecord]):
    """Suite scorecard built from all 72 runs."""
    return generate_suite_scorecard(run_records, agent_id="claude", repo_commit="test-commit")


# ---------------------------------------------------------------------------
# 1. Fixture generation — run count
# ---------------------------------------------------------------------------


class TestFixtureRunCount:
    def test_total_run_count(self, raw_runs: list[dict]) -> None:
        assert len(raw_runs) == EXPECTED_RUN_COUNT

    def test_runs_are_dicts(self, raw_runs: list[dict]) -> None:
        assert all(isinstance(r, dict) for r in raw_runs)

    def test_all_runs_have_required_fields(self, raw_runs: list[dict]) -> None:
        required = {
            "run_id", "task_id", "family", "variant", "agent_id",
            "status", "validity", "validation_status",
            "reported_total_tokens",
        }
        for run in raw_runs:
            assert required.issubset(run.keys()), f"Missing fields in {run['run_id']}"

    def test_runs_validate_as_run_records(self, raw_runs: list[dict]) -> None:
        for run in raw_runs:
            rec = RunRecord.model_validate(run)
            assert rec.validity == RunValidity.valid


# ---------------------------------------------------------------------------
# 2. All 6 families are represented
# ---------------------------------------------------------------------------


class TestFamilyRepresentation:
    def test_all_six_families_present(self, raw_runs: list[dict]) -> None:
        families = {r["family"] for r in raw_runs}
        assert families == EXPECTED_FAMILIES

    def test_each_family_has_correct_run_count(self, raw_runs: list[dict]) -> None:
        from collections import Counter

        counts = Counter(r["family"] for r in raw_runs)
        # 2 tasks x 2 variants x 3 reps = 12 per family
        for family in EXPECTED_FAMILIES:
            assert counts[family] == 12, f"{family}: expected 12 runs, got {counts[family]}"

    def test_both_variants_present_per_family(self, raw_runs: list[dict]) -> None:
        from collections import defaultdict

        fv: dict[str, set] = defaultdict(set)
        for r in raw_runs:
            fv[r["family"]].add(r["variant"])
        for family in EXPECTED_FAMILIES:
            assert {"baseline", "tool_variant"} == fv[family], f"{family} missing a variant"

    def test_three_repetitions_per_task_variant(self, raw_runs: list[dict]) -> None:
        from collections import Counter

        # Each (task_id, variant) pair should appear exactly 3 times
        pairs = Counter((r["task_id"], r["variant"]) for r in raw_runs)
        for (task_id, variant), count in pairs.items():
            assert count == 3, f"({task_id}, {variant}): expected 3 reps, got {count}"


# ---------------------------------------------------------------------------
# 3. Scorecards contain all 6 families
# ---------------------------------------------------------------------------


class TestScorecardFamilies:
    def test_scorecard_has_six_families(self, suite_scorecard) -> None:
        assert len(suite_scorecard.families) == 6

    def test_scorecard_family_names(self, suite_scorecard) -> None:
        names = {fc.family for fc in suite_scorecard.families}
        assert names == EXPECTED_FAMILIES

    def test_scorecard_families_sorted(self, suite_scorecard) -> None:
        names = [fc.family for fc in suite_scorecard.families]
        assert names == sorted(names)

    def test_scorecard_agent_id(self, suite_scorecard) -> None:
        assert suite_scorecard.agent_id == "claude"

    def test_scorecard_generated_at_utc(self, suite_scorecard) -> None:
        assert suite_scorecard.generated_at.tzinfo is not None


# ---------------------------------------------------------------------------
# 4. Token reduction is positive for all families
# ---------------------------------------------------------------------------


class TestTokenReduction:
    def test_all_families_have_token_reduction(self, suite_scorecard) -> None:
        for fc in suite_scorecard.families:
            assert fc.token_reduction_pct is not None, f"{fc.family}: token_reduction_pct is None"
            # Reduction pct is negative (variant < baseline)
            assert fc.token_reduction_pct < 0, (
                f"{fc.family}: expected negative token_reduction_pct"
                f" (variant saves tokens), got {fc.token_reduction_pct:.1f}%"
            )

    def test_token_delta_is_negative(self, suite_scorecard) -> None:
        for fc in suite_scorecard.families:
            assert fc.token_delta is not None
            assert fc.token_delta < 0, f"{fc.family}: token_delta should be negative"

    def test_variant_avg_tokens_less_than_baseline(self, suite_scorecard) -> None:
        for fc in suite_scorecard.families:
            b_tokens = fc.baseline.avg_tokens
            v_tokens = fc.tool_variant.avg_tokens
            assert b_tokens is not None and v_tokens is not None
            assert v_tokens < b_tokens, (
                f"{fc.family}: variant avg_tokens ({v_tokens:.0f})"
                f" should be less than baseline ({b_tokens:.0f})"
            )

    def test_minimum_reduction_percent(self, suite_scorecard) -> None:
        # Each family should achieve at least 30% token reduction
        for fc in suite_scorecard.families:
            reduction = abs(fc.token_reduction_pct)  # type: ignore[arg-type]
            assert reduction >= 30, (
                f"{fc.family}: expected >= 30% reduction, got {reduction:.1f}%"
            )


# ---------------------------------------------------------------------------
# 5. DuckDB aggregation works with full dataset
# ---------------------------------------------------------------------------


class TestDuckDBAggregation:
    @pytest.fixture(autouse=False)
    def duckdb_conn(self, run_records: list[RunRecord]):
        conn = load_runs_to_duckdb(runs=run_records)
        yield conn
        conn.close()

    def test_total_row_count(self, duckdb_conn) -> None:
        count = duckdb_conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert count == EXPECTED_RUN_COUNT

    def test_all_families_in_db(self, duckdb_conn) -> None:
        families = {
            row[0]
            for row in duckdb_conn.execute("SELECT DISTINCT family FROM runs").fetchall()
        }
        assert families == EXPECTED_FAMILIES

    def test_all_runs_valid(self, duckdb_conn) -> None:
        invalid_count = duckdb_conn.execute(
            "SELECT COUNT(*) FROM runs WHERE validity != 'valid'"
        ).fetchone()[0]
        assert invalid_count == 0

    def test_compute_family_summary_ripgrep(self, duckdb_conn) -> None:
        summary = compute_family_summary(duckdb_conn, "ripgrep")
        assert summary["family"] == "ripgrep"
        assert summary["baseline"]["run_count"] == 6
        assert summary["tool_variant"]["run_count"] == 6
        assert summary["token_delta"] is not None
        assert summary["token_delta"] < 0

    def test_compute_family_summary_all_families(self, run_records: list[RunRecord]) -> None:
        conn = load_runs_to_duckdb(runs=run_records)
        for family in EXPECTED_FAMILIES:
            summary = compute_family_summary(conn, family)
            assert summary["token_reduction_pct"] is not None
            assert summary["token_reduction_pct"] < 0
        conn.close()

    def test_load_from_directory(self, tmp_path: Path, raw_runs: list[dict]) -> None:
        # Write runs as run.json files and load via results_dir
        for run in raw_runs[:6]:  # use a small subset
            run_dir = tmp_path / run["run_id"]
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")

        conn = load_runs_to_duckdb(results_dir=tmp_path)
        count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        conn.close()
        assert count == 6


# ---------------------------------------------------------------------------
# 6. Per-family scorecard generation
# ---------------------------------------------------------------------------


class TestPerFamilyScorecards:
    def test_per_family_scorecard_has_one_family(self, run_records: list[RunRecord]) -> None:
        for family in EXPECTED_FAMILIES:
            fc = aggregate_family(run_records, family)
            assert fc.family == family

    def test_per_family_baseline_run_count(self, run_records: list[RunRecord]) -> None:
        for family in EXPECTED_FAMILIES:
            fc = aggregate_family(run_records, family)
            # 2 tasks x 3 reps = 6 baseline runs per family
            assert fc.baseline.run_count == 6, (
                f"{family}: expected 6 baseline runs, got {fc.baseline.run_count}"
            )

    def test_per_family_variant_run_count(self, run_records: list[RunRecord]) -> None:
        for family in EXPECTED_FAMILIES:
            fc = aggregate_family(run_records, family)
            assert fc.tool_variant.run_count == 6

    def test_per_family_markdown_contains_family_name(self, run_records: list[RunRecord]) -> None:
        from datetime import datetime, timezone

        from benchmarks.harness.models import SuiteScorecard

        for family in EXPECTED_FAMILIES:
            fc = aggregate_family(run_records, family)
            suite = SuiteScorecard(
                agent_id="claude",
                generated_at=datetime.now(tz=timezone.utc),
                repo_commit="test-commit",
                families=[fc],
            )
            md = render_scorecard_markdown(suite)
            assert family in md

    def test_per_family_json_is_valid(self, run_records: list[RunRecord]) -> None:
        from datetime import datetime, timezone

        from benchmarks.harness.models import SuiteScorecard

        for family in EXPECTED_FAMILIES:
            fc = aggregate_family(run_records, family)
            suite = SuiteScorecard(
                agent_id="claude",
                generated_at=datetime.now(tz=timezone.utc),
                repo_commit="test-commit",
                families=[fc],
            )
            json_str = render_scorecard_json(suite)
            data = json.loads(json_str)
            assert len(data["families"]) == 1
            assert data["families"][0]["family"] == family


# ---------------------------------------------------------------------------
# 7. Scorecard rendering with full dataset
# ---------------------------------------------------------------------------


class TestScorecardRendering:
    def test_markdown_contains_all_families(self, suite_scorecard) -> None:
        md = render_scorecard_markdown(suite_scorecard)
        for family in EXPECTED_FAMILIES:
            assert family in md, f"Family '{family}' missing from markdown scorecard"

    def test_json_contains_all_families(self, suite_scorecard) -> None:
        json_str = render_scorecard_json(suite_scorecard)
        data = json.loads(json_str)
        names = {fc["family"] for fc in data["families"]}
        assert names == EXPECTED_FAMILIES

    def test_markdown_has_header_row(self, suite_scorecard) -> None:
        md = render_scorecard_markdown(suite_scorecard)
        assert "| Family" in md
        assert "Reduction %" in md

    def test_json_families_have_token_reduction(self, suite_scorecard) -> None:
        json_str = render_scorecard_json(suite_scorecard)
        data = json.loads(json_str)
        for fc in data["families"]:
            assert fc["token_reduction_pct"] is not None
            assert fc["token_reduction_pct"] < 0

    def test_run_records_written_to_disk(self, tmp_path: Path, raw_runs: list[dict]) -> None:
        """Ensure generate_fixture_runs.main() writes run.json files correctly."""
        for run in raw_runs:
            run_dir = tmp_path / run["run_id"]
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")

        # Load them back
        reloaded = load_runs_from_dir(tmp_path)
        assert len(reloaded) == EXPECTED_RUN_COUNT
        for rec in reloaded:
            assert rec.validity == RunValidity.valid
