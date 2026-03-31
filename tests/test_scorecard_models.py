"""Tests for scorecard Pydantic models."""

import json
from datetime import datetime, timezone

from benchmarks.harness.models import (
    FamilyScorecard,
    SuiteScorecard,
    Variant,
    VariantMetrics,
)


def _make_baseline_metrics() -> VariantMetrics:
    return VariantMetrics(
        variant=Variant.baseline,
        run_count=3,
        avg_tokens=12500.0,
        validation_pass_rate=1.0,
        first_pass_success_rate=0.67,
        avg_repair_iterations=1.0,
        avg_elapsed_seconds=42.5,
    )


def _make_tool_variant_metrics() -> VariantMetrics:
    return VariantMetrics(
        variant=Variant.tool_variant,
        run_count=3,
        avg_tokens=4800.0,
        validation_pass_rate=1.0,
        first_pass_success_rate=1.0,
        avg_repair_iterations=0.0,
        avg_elapsed_seconds=28.1,
    )


def _make_family_scorecard(family: str = "ripgrep") -> FamilyScorecard:
    baseline = _make_baseline_metrics()
    variant = _make_tool_variant_metrics()
    delta = variant.avg_tokens - baseline.avg_tokens  # type: ignore[operator]
    pct = delta / baseline.avg_tokens * 100  # type: ignore[operator]
    return FamilyScorecard(
        family=family,
        baseline=baseline,
        tool_variant=variant,
        token_delta=delta,
        token_reduction_pct=pct,
    )


def _make_suite_scorecard() -> SuiteScorecard:
    return SuiteScorecard(
        agent_id="claude",
        generated_at=datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        repo_commit="abc1234",
        families=[
            _make_family_scorecard("ripgrep"),
            _make_family_scorecard("rtk"),
        ],
    )


class TestVariantMetrics:
    def test_baseline_round_trip(self) -> None:
        m = _make_baseline_metrics()
        assert m.variant == Variant.baseline
        assert m.run_count == 3
        assert m.avg_tokens == 12500.0
        assert m.validation_pass_rate == 1.0
        assert m.first_pass_success_rate == 0.67
        assert m.avg_repair_iterations == 1.0
        assert m.avg_elapsed_seconds == 42.5

    def test_tool_variant_round_trip(self) -> None:
        m = _make_tool_variant_metrics()
        assert m.variant == Variant.tool_variant
        assert m.run_count == 3
        assert m.avg_tokens == 4800.0

    def test_optional_fields_default_none(self) -> None:
        m = VariantMetrics(variant=Variant.baseline, run_count=0)
        assert m.avg_tokens is None
        assert m.validation_pass_rate is None
        assert m.first_pass_success_rate is None
        assert m.avg_repair_iterations is None
        assert m.avg_elapsed_seconds is None

    def test_serializes_to_json(self) -> None:
        m = _make_baseline_metrics()
        data = json.loads(m.model_dump_json())
        assert data["variant"] == "baseline"
        assert data["run_count"] == 3
        assert data["avg_tokens"] == 12500.0


class TestFamilyScorecard:
    def test_token_delta_computed_correctly(self) -> None:
        sc = _make_family_scorecard()
        assert sc.token_delta is not None
        assert sc.token_delta == 4800.0 - 12500.0

    def test_token_reduction_pct(self) -> None:
        sc = _make_family_scorecard()
        assert sc.token_reduction_pct is not None
        # reduction is negative when variant uses fewer tokens
        expected_pct = (4800.0 - 12500.0) / 12500.0 * 100
        assert abs(sc.token_reduction_pct - expected_pct) < 1e-9

    def test_family_name_preserved(self) -> None:
        sc = _make_family_scorecard("fastmod")
        assert sc.family == "fastmod"

    def test_optional_delta_fields_default_none(self) -> None:
        sc = FamilyScorecard(
            family="comby",
            baseline=_make_baseline_metrics(),
            tool_variant=_make_tool_variant_metrics(),
        )
        assert sc.token_delta is None
        assert sc.token_reduction_pct is None

    def test_serializes_to_json(self) -> None:
        sc = _make_family_scorecard()
        data = json.loads(sc.model_dump_json())
        assert data["family"] == "ripgrep"
        assert data["baseline"]["variant"] == "baseline"
        assert data["tool_variant"]["variant"] == "tool_variant"
        assert data["token_delta"] == 4800.0 - 12500.0


class TestSuiteScorecard:
    def test_suite_fields(self) -> None:
        suite = _make_suite_scorecard()
        assert suite.agent_id == "claude"
        assert suite.repo_commit == "abc1234"
        assert len(suite.families) == 2

    def test_family_names_in_suite(self) -> None:
        suite = _make_suite_scorecard()
        names = [f.family for f in suite.families]
        assert names == ["ripgrep", "rtk"]

    def test_empty_families_default(self) -> None:
        suite = SuiteScorecard(
            agent_id="codex",
            generated_at=datetime(2026, 3, 31, tzinfo=timezone.utc),
            repo_commit="deadbeef",
        )
        assert suite.families == []

    def test_serializes_to_json(self) -> None:
        suite = _make_suite_scorecard()
        data = json.loads(suite.model_dump_json())
        assert data["agent_id"] == "claude"
        assert data["repo_commit"] == "abc1234"
        assert len(data["families"]) == 2
        assert data["families"][0]["family"] == "ripgrep"

    def test_full_json_structure(self) -> None:
        """Verify the full nested JSON shape is correct end-to-end."""
        suite = _make_suite_scorecard()
        raw = suite.model_dump_json()
        data = json.loads(raw)

        family = data["families"][0]
        assert "baseline" in family
        assert "tool_variant" in family
        assert family["baseline"]["run_count"] == 3
        assert family["tool_variant"]["avg_tokens"] == 4800.0
        assert family["token_delta"] == 4800.0 - 12500.0
