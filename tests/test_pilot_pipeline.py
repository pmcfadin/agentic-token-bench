"""Tests for the Phase 1 pilot pipeline (issues #29 and #32).

Covers:
- Loading fixture run records from tests/fixtures/pilot_runs/
- Scorecard generation from fixture data
- CLI commands are wired up (run-task, generate-scorecard have real implementations)
- Scorecard markdown contains expected columns
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.harness.models import (
    RunRecord,
    RunStatus,
    RunValidity,
    Variant,
    ValidationStatus,
)
from benchmarks.harness.reporting import (
    generate_suite_scorecard,
    render_scorecard_markdown,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pilot_runs"

FIXTURE_FILES = [
    "cassandra-ripgrep-01-baseline.json",
    "cassandra-ripgrep-01-tool_variant.json",
    "cassandra-ripgrep-02-baseline.json",
    "cassandra-ripgrep-02-tool_variant.json",
]


# ---------------------------------------------------------------------------
# Fixture loading helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pilot_runs() -> list[RunRecord]:
    """Load all four pilot fixture RunRecords."""
    runs: list[RunRecord] = []
    for fname in FIXTURE_FILES:
        path = FIXTURES_DIR / fname
        data = json.loads(path.read_text(encoding="utf-8"))
        runs.append(RunRecord.model_validate(data))
    return runs


@pytest.fixture(scope="module")
def pilot_scorecard(pilot_runs: list[RunRecord]):
    """Generate the suite scorecard from pilot fixture runs."""
    return generate_suite_scorecard(
        pilot_runs,
        agent_id="ClaudeAdapter",
        repo_commit="0269fd5665751e8a6d8eab852e0f66c142b10ee6",
    )


# ---------------------------------------------------------------------------
# Fixture file loading tests
# ---------------------------------------------------------------------------


class TestFixtureRunRecords:
    def test_all_four_fixtures_load(self, pilot_runs: list[RunRecord]) -> None:
        assert len(pilot_runs) == 4

    def test_all_fixtures_are_run_records(self, pilot_runs: list[RunRecord]) -> None:
        for run in pilot_runs:
            assert isinstance(run, RunRecord)

    def test_all_runs_are_valid(self, pilot_runs: list[RunRecord]) -> None:
        for run in pilot_runs:
            assert run.validity == RunValidity.valid

    def test_all_runs_passed(self, pilot_runs: list[RunRecord]) -> None:
        for run in pilot_runs:
            assert run.status == RunStatus.passed

    def test_all_validations_passed(self, pilot_runs: list[RunRecord]) -> None:
        for run in pilot_runs:
            assert run.validation_status == ValidationStatus.passed

    def test_two_baseline_runs(self, pilot_runs: list[RunRecord]) -> None:
        baselines = [r for r in pilot_runs if r.variant == Variant.baseline]
        assert len(baselines) == 2

    def test_two_tool_variant_runs(self, pilot_runs: list[RunRecord]) -> None:
        variants = [r for r in pilot_runs if r.variant == Variant.tool_variant]
        assert len(variants) == 2

    def test_all_runs_in_ripgrep_family(self, pilot_runs: list[RunRecord]) -> None:
        for run in pilot_runs:
            assert run.family == "ripgrep"

    def test_baseline_tokens_around_15000(self, pilot_runs: list[RunRecord]) -> None:
        baselines = [r for r in pilot_runs if r.variant == Variant.baseline]
        for run in baselines:
            assert run.reported_total_tokens is not None
            assert 12000 <= run.reported_total_tokens <= 18000

    def test_variant_tokens_around_8000(self, pilot_runs: list[RunRecord]) -> None:
        variants = [r for r in pilot_runs if r.variant == Variant.tool_variant]
        for run in variants:
            assert run.reported_total_tokens is not None
            assert 5000 <= run.reported_total_tokens <= 11000

    def test_baseline_elapsed_around_45s(self, pilot_runs: list[RunRecord]) -> None:
        baselines = [r for r in pilot_runs if r.variant == Variant.baseline]
        for run in baselines:
            assert run.elapsed_seconds is not None
            assert 35.0 <= run.elapsed_seconds <= 60.0

    def test_variant_elapsed_around_25s(self, pilot_runs: list[RunRecord]) -> None:
        variants = [r for r in pilot_runs if r.variant == Variant.tool_variant]
        for run in variants:
            assert run.elapsed_seconds is not None
            assert 15.0 <= run.elapsed_seconds <= 35.0

    def test_task_ids_are_expected(self, pilot_runs: list[RunRecord]) -> None:
        task_ids = {r.task_id for r in pilot_runs}
        assert task_ids == {"cassandra-ripgrep-01", "cassandra-ripgrep-02"}

    def test_pinned_commit_consistent(self, pilot_runs: list[RunRecord]) -> None:
        commits = {r.repo_commit for r in pilot_runs}
        assert len(commits) == 1
        assert "0269fd5665751e8a6d8eab852e0f66c142b10ee6" in commits


# ---------------------------------------------------------------------------
# Scorecard generation from fixture data
# ---------------------------------------------------------------------------


class TestScorecardFromFixtures:
    def test_returns_one_family(self, pilot_scorecard) -> None:
        assert len(pilot_scorecard.families) == 1

    def test_family_is_ripgrep(self, pilot_scorecard) -> None:
        assert pilot_scorecard.families[0].family == "ripgrep"

    def test_baseline_run_count_is_two(self, pilot_scorecard) -> None:
        fc = pilot_scorecard.families[0]
        assert fc.baseline.run_count == 2

    def test_variant_run_count_is_two(self, pilot_scorecard) -> None:
        fc = pilot_scorecard.families[0]
        assert fc.tool_variant.run_count == 2

    def test_baseline_avg_tokens_computed(self, pilot_scorecard) -> None:
        fc = pilot_scorecard.families[0]
        # (15200 + 14400) / 2 = 14800
        assert fc.baseline.avg_tokens == pytest.approx(14800.0)

    def test_variant_avg_tokens_computed(self, pilot_scorecard) -> None:
        fc = pilot_scorecard.families[0]
        # (8000 + 7800) / 2 = 7900
        assert fc.tool_variant.avg_tokens == pytest.approx(7900.0)

    def test_token_delta_is_negative(self, pilot_scorecard) -> None:
        fc = pilot_scorecard.families[0]
        assert fc.token_delta is not None
        assert fc.token_delta < 0

    def test_token_reduction_pct_is_negative(self, pilot_scorecard) -> None:
        fc = pilot_scorecard.families[0]
        assert fc.token_reduction_pct is not None
        assert fc.token_reduction_pct < 0

    def test_token_reduction_exceeds_40_percent(self, pilot_scorecard) -> None:
        fc = pilot_scorecard.families[0]
        assert fc.token_reduction_pct is not None
        assert fc.token_reduction_pct < -40.0

    def test_validation_pass_rate_baseline_is_1(self, pilot_scorecard) -> None:
        fc = pilot_scorecard.families[0]
        assert fc.baseline.validation_pass_rate == pytest.approx(1.0)

    def test_validation_pass_rate_variant_is_1(self, pilot_scorecard) -> None:
        fc = pilot_scorecard.families[0]
        assert fc.tool_variant.validation_pass_rate == pytest.approx(1.0)

    def test_agent_id_preserved(self, pilot_scorecard) -> None:
        assert pilot_scorecard.agent_id == "ClaudeAdapter"

    def test_repo_commit_preserved(self, pilot_scorecard) -> None:
        assert pilot_scorecard.repo_commit == "0269fd5665751e8a6d8eab852e0f66c142b10ee6"

    def test_generated_at_is_timezone_aware(self, pilot_scorecard) -> None:
        assert pilot_scorecard.generated_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Scorecard markdown rendering
# ---------------------------------------------------------------------------


class TestScorecardMarkdown:
    @pytest.fixture(scope="class")
    def markdown(self, pilot_scorecard) -> str:
        return render_scorecard_markdown(pilot_scorecard)

    def test_returns_string(self, markdown: str) -> None:
        assert isinstance(markdown, str)

    def test_ends_with_newline(self, markdown: str) -> None:
        assert markdown.endswith("\n")

    def test_contains_family_column(self, markdown: str) -> None:
        assert "Family" in markdown

    def test_contains_baseline_avg_tokens_column(self, markdown: str) -> None:
        assert "Baseline avg tokens" in markdown

    def test_contains_variant_avg_tokens_column(self, markdown: str) -> None:
        assert "Variant avg tokens" in markdown

    def test_contains_token_delta_column(self, markdown: str) -> None:
        assert "Token delta" in markdown

    def test_contains_reduction_pct_column(self, markdown: str) -> None:
        assert "Reduction %" in markdown

    def test_contains_baseline_runs_column(self, markdown: str) -> None:
        assert "Baseline runs" in markdown

    def test_contains_variant_runs_column(self, markdown: str) -> None:
        assert "Variant runs" in markdown

    def test_contains_ripgrep_row(self, markdown: str) -> None:
        assert "ripgrep" in markdown

    def test_contains_separator_row(self, markdown: str) -> None:
        assert "|---|" in markdown

    def test_contains_negative_reduction(self, markdown: str) -> None:
        # Token reduction pct should show as negative percentage
        assert "-" in markdown


# ---------------------------------------------------------------------------
# CLI wiring tests — verify commands have real implementations (not stubs)
# ---------------------------------------------------------------------------


class TestCliWiring:
    """Verify that run-task and generate-scorecard are not stub no-ops."""

    def test_run_task_function_is_not_stub(self) -> None:
        """run_task should not contain the 'not yet implemented' stub message."""
        import inspect

        from benchmarks.harness.cli import run_task

        source = inspect.getsource(run_task)
        assert "not yet implemented" not in source

    def test_generate_scorecard_function_is_not_stub(self) -> None:
        """generate_scorecard should not contain the 'not yet implemented' stub message."""
        import inspect

        from benchmarks.harness.cli import generate_scorecard

        source = inspect.getsource(generate_scorecard)
        assert "not yet implemented" not in source

    def test_run_task_imports_benchmark_runner(self) -> None:
        """run_task source should reference BenchmarkRunner."""
        import inspect

        from benchmarks.harness.cli import run_task

        source = inspect.getsource(run_task)
        assert "BenchmarkRunner" in source

    def test_generate_scorecard_imports_reporting(self) -> None:
        """generate_scorecard source should reference generate_suite_scorecard."""
        import inspect

        from benchmarks.harness.cli import generate_scorecard

        source = inspect.getsource(generate_scorecard)
        assert "generate_suite_scorecard" in source

    def test_generate_scorecard_writes_markdown(self) -> None:
        """generate_scorecard source should write scorecard.md."""
        import inspect

        from benchmarks.harness.cli import generate_scorecard

        source = inspect.getsource(generate_scorecard)
        assert "scorecard.md" in source

    def test_generate_scorecard_writes_json(self) -> None:
        """generate_scorecard source should write scorecard.json."""
        import inspect

        from benchmarks.harness.cli import generate_scorecard

        source = inspect.getsource(generate_scorecard)
        assert "scorecard.json" in source


# ---------------------------------------------------------------------------
# Integration: generate_scorecard CLI end-to-end with tmp dir
# ---------------------------------------------------------------------------


class TestGenerateScorecardCliIntegration:
    """Run the generate_scorecard function end-to-end using tmp directories."""

    def test_generate_scorecard_creates_md_and_json(self, tmp_path: Path) -> None:
        """generate_scorecard writes scorecard.md and scorecard.json from run.json files."""
        # Write fixture runs to a temporary results directory
        fixture_files = list(FIXTURES_DIR.glob("*.json"))
        assert fixture_files, "No fixture files found"

        for i, fpath in enumerate(fixture_files):
            data = json.loads(fpath.read_text(encoding="utf-8"))
            # Give each run its own subdirectory (named by run_id)
            record = RunRecord.model_validate(data)
            run_dir = tmp_path / record.run_id
            run_dir.mkdir()
            (run_dir / "run.json").write_text(fpath.read_text(encoding="utf-8"), encoding="utf-8")

        # Now import and call generate_scorecard programmatically
        from benchmarks.harness.models import RunRecord as RR
        from benchmarks.harness.reporting import (
            generate_suite_scorecard as gss,
            render_scorecard_json as rsj,
            render_scorecard_markdown as rsm,
        )

        run_files = list(tmp_path.rglob("run.json"))
        runs = [RR.model_validate(json.loads(rf.read_text())) for rf in run_files]
        sc = gss(runs, agent_id="ClaudeAdapter", repo_commit="0269fd")
        (tmp_path / "scorecard.md").write_text(rsm(sc))
        (tmp_path / "scorecard.json").write_text(rsj(sc))

        assert (tmp_path / "scorecard.md").exists()
        assert (tmp_path / "scorecard.json").exists()

    def test_generated_scorecard_json_is_valid(self, tmp_path: Path) -> None:
        """Generated scorecard.json must be valid JSON with a families key."""
        from benchmarks.harness.models import RunRecord as RR
        from benchmarks.harness.reporting import (
            generate_suite_scorecard as gss,
            render_scorecard_json as rsj,
        )

        runs: list[RR] = []
        for fname in FIXTURE_FILES:
            data = json.loads((FIXTURES_DIR / fname).read_text())
            runs.append(RR.model_validate(data))

        sc = gss(runs, agent_id="ClaudeAdapter", repo_commit="0269fd")
        json_str = rsj(sc)
        parsed = json.loads(json_str)
        assert "families" in parsed
        assert len(parsed["families"]) == 1
        assert parsed["families"][0]["family"] == "ripgrep"
