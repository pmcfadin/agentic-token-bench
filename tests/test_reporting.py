"""Tests for benchmarks.harness.reporting."""

import json
from datetime import datetime

import pytest

from benchmarks.harness.models import (
    RunRecord,
    RunStatus,
    RunValidity,
    SuiteScorecard,
    Variant,
    ValidationStatus,
)
from benchmarks.harness.reporting import (
    aggregate_family,
    generate_suite_scorecard,
    render_scorecard_json,
    render_scorecard_markdown,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
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
    agent_id: str = "claude",
    repo_commit: str = "abc1234",
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        task_id=f"task-{run_id}",
        family=family,
        variant=variant,
        agent_id=agent_id,
        adapter_version="1.0",
        repo_commit=repo_commit,
        status=RunStatus.passed,
        validity=validity,
        reported_total_tokens=reported_total_tokens,
        elapsed_seconds=elapsed_seconds,
        repair_iterations=repair_iterations,
        validation_status=validation_status,
    )


@pytest.fixture()
def ripgrep_runs() -> list[RunRecord]:
    """Three baseline + three tool_variant valid runs for the ripgrep family."""
    return [
        # baseline runs: 10000, 12000, 15000 tokens
        _make_run(run_id="rg-b1", family="ripgrep", variant=Variant.baseline,
                  reported_total_tokens=10000, elapsed_seconds=40.0, repair_iterations=1),
        _make_run(run_id="rg-b2", family="ripgrep", variant=Variant.baseline,
                  reported_total_tokens=12000, elapsed_seconds=42.0, repair_iterations=1),
        _make_run(run_id="rg-b3", family="ripgrep", variant=Variant.baseline,
                  reported_total_tokens=15000, elapsed_seconds=45.5, repair_iterations=1,
                  validation_status=ValidationStatus.failed),
        # tool_variant runs: 4000, 5000, 5400 tokens
        _make_run(run_id="rg-v1", family="ripgrep", variant=Variant.tool_variant,
                  reported_total_tokens=4000, elapsed_seconds=28.0, repair_iterations=0),
        _make_run(run_id="rg-v2", family="ripgrep", variant=Variant.tool_variant,
                  reported_total_tokens=5000, elapsed_seconds=30.0, repair_iterations=0),
        _make_run(run_id="rg-v3", family="ripgrep", variant=Variant.tool_variant,
                  reported_total_tokens=5400, elapsed_seconds=26.0, repair_iterations=0),
    ]


@pytest.fixture()
def rtk_runs() -> list[RunRecord]:
    """Two baseline + two tool_variant valid runs for the rtk family."""
    return [
        _make_run(run_id="rtk-b1", family="rtk", variant=Variant.baseline,
                  reported_total_tokens=9000, elapsed_seconds=35.0, repair_iterations=0),
        _make_run(run_id="rtk-b2", family="rtk", variant=Variant.baseline,
                  reported_total_tokens=11000, elapsed_seconds=40.0, repair_iterations=2),
        _make_run(run_id="rtk-v1", family="rtk", variant=Variant.tool_variant,
                  reported_total_tokens=3000, elapsed_seconds=20.0, repair_iterations=0),
        _make_run(run_id="rtk-v2", family="rtk", variant=Variant.tool_variant,
                  reported_total_tokens=3200, elapsed_seconds=22.0, repair_iterations=0),
    ]


@pytest.fixture()
def all_runs(ripgrep_runs: list[RunRecord], rtk_runs: list[RunRecord]) -> list[RunRecord]:
    return ripgrep_runs + rtk_runs


# ---------------------------------------------------------------------------
# aggregate_family tests
# ---------------------------------------------------------------------------


class TestAggregateFamily:
    def test_baseline_run_count(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.baseline.run_count == 3

    def test_tool_variant_run_count(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.tool_variant.run_count == 3

    def test_baseline_avg_tokens(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        expected = (10000 + 12000 + 15000) / 3
        assert sc.baseline.avg_tokens == pytest.approx(expected)

    def test_tool_variant_avg_tokens(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        expected = (4000 + 5000 + 5400) / 3
        assert sc.tool_variant.avg_tokens == pytest.approx(expected)

    def test_token_delta_is_variant_minus_baseline(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.token_delta == pytest.approx(sc.tool_variant.avg_tokens - sc.baseline.avg_tokens)  # type: ignore[operator]

    def test_token_reduction_pct_formula(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        expected_pct = sc.token_delta / sc.baseline.avg_tokens * 100  # type: ignore[operator]
        assert sc.token_reduction_pct == pytest.approx(expected_pct)

    def test_token_reduction_is_negative(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.token_reduction_pct is not None
        assert sc.token_reduction_pct < 0

    def test_validation_pass_rate_baseline(self, ripgrep_runs: list[RunRecord]) -> None:
        # 2 of 3 baseline runs have ValidationStatus.passed
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.baseline.validation_pass_rate == pytest.approx(2 / 3)

    def test_validation_pass_rate_variant_all_pass(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.tool_variant.validation_pass_rate == pytest.approx(1.0)

    def test_first_pass_success_rate_baseline(self, ripgrep_runs: list[RunRecord]) -> None:
        # Baseline runs: all have repair_iterations=1, so none qualify as first-pass
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.baseline.first_pass_success_rate == pytest.approx(0.0)

    def test_first_pass_success_rate_variant(self, ripgrep_runs: list[RunRecord]) -> None:
        # Variant runs: all pass with repair_iterations=0
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.tool_variant.first_pass_success_rate == pytest.approx(1.0)

    def test_avg_repair_iterations_baseline(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.baseline.avg_repair_iterations == pytest.approx(1.0)

    def test_avg_elapsed_seconds_baseline(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        expected = (40.0 + 42.0 + 45.5) / 3
        assert sc.baseline.avg_elapsed_seconds == pytest.approx(expected)

    def test_invalid_runs_excluded(self, ripgrep_runs: list[RunRecord]) -> None:
        # Add an invalid run with large token count that should be excluded
        invalid_run = _make_run(
            run_id="rg-invalid",
            family="ripgrep",
            variant=Variant.baseline,
            validity=RunValidity.invalid,
            reported_total_tokens=999999,
        )
        sc = aggregate_family(ripgrep_runs + [invalid_run], "ripgrep")
        # run_count should still be 3, not 4
        assert sc.baseline.run_count == 3

    def test_no_valid_runs_returns_none_avg_tokens(self) -> None:
        invalid_run = _make_run(
            run_id="x1",
            family="empty-family",
            variant=Variant.baseline,
            validity=RunValidity.invalid,
            reported_total_tokens=5000,
        )
        sc = aggregate_family([invalid_run], "empty-family")
        assert sc.baseline.run_count == 0
        assert sc.baseline.avg_tokens is None

    def test_token_delta_none_when_no_tokens(self) -> None:
        # Runs without reported_total_tokens
        run_b = _make_run(run_id="b1", family="no-tokens", variant=Variant.baseline,
                          reported_total_tokens=None)
        run_v = _make_run(run_id="v1", family="no-tokens", variant=Variant.tool_variant,
                          reported_total_tokens=None)
        sc = aggregate_family([run_b, run_v], "no-tokens")
        assert sc.token_delta is None
        assert sc.token_reduction_pct is None

    def test_family_name_on_scorecard(self, ripgrep_runs: list[RunRecord]) -> None:
        sc = aggregate_family(ripgrep_runs, "ripgrep")
        assert sc.family == "ripgrep"


# ---------------------------------------------------------------------------
# generate_suite_scorecard tests
# ---------------------------------------------------------------------------


class TestGenerateSuiteScorecard:
    def test_returns_suite_scorecard_instance(self, all_runs: list[RunRecord]) -> None:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        assert isinstance(suite, SuiteScorecard)

    def test_agent_id_preserved(self, all_runs: list[RunRecord]) -> None:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        assert suite.agent_id == "claude"

    def test_repo_commit_preserved(self, all_runs: list[RunRecord]) -> None:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        assert suite.repo_commit == "abc1234"

    def test_two_families_present(self, all_runs: list[RunRecord]) -> None:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        assert len(suite.families) == 2

    def test_family_names_sorted(self, all_runs: list[RunRecord]) -> None:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        names = [f.family for f in suite.families]
        assert names == sorted(names)

    def test_family_names_correct(self, all_runs: list[RunRecord]) -> None:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        names = {f.family for f in suite.families}
        assert names == {"ripgrep", "rtk"}

    def test_generated_at_is_utc(self, all_runs: list[RunRecord]) -> None:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        assert suite.generated_at.tzinfo is not None

    def test_each_family_has_both_variants(self, all_runs: list[RunRecord]) -> None:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        for fc in suite.families:
            assert fc.baseline.variant == Variant.baseline
            assert fc.tool_variant.variant == Variant.tool_variant

    def test_empty_runs_returns_empty_families(self) -> None:
        suite = generate_suite_scorecard([], agent_id="claude", repo_commit="abc1234")
        assert suite.families == []


# ---------------------------------------------------------------------------
# render_scorecard_markdown tests
# ---------------------------------------------------------------------------


class TestRenderScorecardMarkdown:
    @pytest.fixture()
    def markdown(self, all_runs: list[RunRecord]) -> str:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        return render_scorecard_markdown(suite)

    def test_returns_string(self, markdown: str) -> None:
        assert isinstance(markdown, str)

    def test_contains_family_header(self, markdown: str) -> None:
        assert "Family" in markdown

    def test_contains_baseline_tokens_header(self, markdown: str) -> None:
        assert "Baseline avg tokens" in markdown

    def test_contains_variant_tokens_header(self, markdown: str) -> None:
        assert "Variant avg tokens" in markdown

    def test_contains_token_delta_header(self, markdown: str) -> None:
        assert "Token delta" in markdown

    def test_contains_reduction_pct_header(self, markdown: str) -> None:
        assert "Reduction %" in markdown

    def test_contains_ripgrep_family_row(self, markdown: str) -> None:
        assert "ripgrep" in markdown

    def test_contains_rtk_family_row(self, markdown: str) -> None:
        assert "rtk" in markdown

    def test_contains_separator_row(self, markdown: str) -> None:
        assert "|---|" in markdown

    def test_ends_with_newline(self, markdown: str) -> None:
        assert markdown.endswith("\n")

    def test_contains_baseline_runs_header(self, markdown: str) -> None:
        assert "Baseline runs" in markdown

    def test_contains_variant_runs_header(self, markdown: str) -> None:
        assert "Variant runs" in markdown


# ---------------------------------------------------------------------------
# render_scorecard_json tests
# ---------------------------------------------------------------------------


class TestRenderScorecardJson:
    @pytest.fixture()
    def json_str(self, all_runs: list[RunRecord]) -> str:
        suite = generate_suite_scorecard(all_runs, agent_id="claude", repo_commit="abc1234")
        return render_scorecard_json(suite)

    def test_returns_string(self, json_str: str) -> None:
        assert isinstance(json_str, str)

    def test_is_valid_json(self, json_str: str) -> None:
        data = json.loads(json_str)
        assert isinstance(data, dict)

    def test_agent_id_in_json(self, json_str: str) -> None:
        data = json.loads(json_str)
        assert data["agent_id"] == "claude"

    def test_repo_commit_in_json(self, json_str: str) -> None:
        data = json.loads(json_str)
        assert data["repo_commit"] == "abc1234"

    def test_families_in_json(self, json_str: str) -> None:
        data = json.loads(json_str)
        assert "families" in data
        assert len(data["families"]) == 2

    def test_family_has_baseline_and_variant(self, json_str: str) -> None:
        data = json.loads(json_str)
        family = data["families"][0]
        assert "baseline" in family
        assert "tool_variant" in family

    def test_token_delta_present(self, json_str: str) -> None:
        data = json.loads(json_str)
        family = data["families"][0]
        assert "token_delta" in family

    def test_token_reduction_pct_present(self, json_str: str) -> None:
        data = json.loads(json_str)
        family = data["families"][0]
        assert "token_reduction_pct" in family

    def test_generated_at_is_iso_string(self, json_str: str) -> None:
        data = json.loads(json_str)
        assert isinstance(data["generated_at"], str)
        # Should parse as an ISO datetime
        datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
