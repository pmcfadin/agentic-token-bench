from __future__ import annotations

from datetime import datetime, timezone

from benchmarks.harness.models import (
    BenchmarkTrack,
    PhaseRecord,
    QualityRetentionMetrics,
    RunRecord,
    RunStatus,
    RunValidity,
    ToolEfficacyMetrics,
    ValidationStatus,
    Variant,
)
from benchmarks.harness.reporting import (
    generate_quality_retention_scorecard,
    generate_tool_efficacy_scorecard,
)


def _run_record(
    *,
    run_id: str,
    family: str,
    variant: Variant,
    track: BenchmarkTrack,
    tool_metrics: ToolEfficacyMetrics | None = None,
    quality_metrics: QualityRetentionMetrics | None = None,
) -> RunRecord:
    now = datetime.now(tz=timezone.utc)
    return RunRecord(
        run_id=run_id,
        task_id=f"{family}-{variant.value}",
        family=family,
        variant=variant,
        agent_id="tester",
        adapter_version="1.0.0",
        repo_commit="deadbeef",
        status=RunStatus.passed,
        validity=RunValidity.valid,
        validation_status=ValidationStatus.passed,
        started_at=now,
        finished_at=now,
        track=track,
        phase_records=[
            PhaseRecord(
                name=track.value,
                track=track,
                status=RunStatus.passed,
                started_at=now,
                finished_at=now,
                validation_status=ValidationStatus.passed,
            )
        ],
        tool_metrics=tool_metrics,
        quality_metrics=quality_metrics,
    )


def test_layered_scorecards_aggregate_by_track() -> None:
    runs = [
        _run_record(
            run_id="tool-baseline",
            family="rtk",
            variant=Variant.baseline,
            track=BenchmarkTrack.tool_only,
            tool_metrics=ToolEfficacyMetrics(
                raw_bytes=100,
                reduced_bytes=100,
                reduction_ratio=1.0,
                deterministic_valid=True,
            ),
        ),
        _run_record(
            run_id="tool-variant",
            family="rtk",
            variant=Variant.tool_variant,
            track=BenchmarkTrack.tool_only,
            tool_metrics=ToolEfficacyMetrics(
                raw_bytes=100,
                reduced_bytes=25,
                reduction_ratio=0.25,
                deterministic_valid=True,
            ),
        ),
        _run_record(
            run_id="quality-variant",
            family="rtk",
            variant=Variant.tool_variant,
            track=BenchmarkTrack.quality_eval,
            quality_metrics=QualityRetentionMetrics(
                raw_quality_score=1.0,
                reduced_quality_score=1.0,
                quality_delta=0.0,
                llm_call_count_small=2,
            ),
        ),
    ]

    tool_scorecard = generate_tool_efficacy_scorecard(runs, repo_commit="deadbeef")
    quality_scorecard = generate_quality_retention_scorecard(runs, repo_commit="deadbeef")

    assert len(tool_scorecard.families) == 1
    assert tool_scorecard.families[0].tool_variant.avg_reduced_bytes == 25
    assert tool_scorecard.families[0].tool_variant.deterministic_pass_rate == 1.0
    assert len(quality_scorecard.families) == 1
    assert quality_scorecard.families[0].tool_variant.avg_quality_delta == 0.0
    assert quality_scorecard.families[0].tool_variant.llm_call_count_small == 2
