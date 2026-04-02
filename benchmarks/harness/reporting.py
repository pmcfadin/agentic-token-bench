"""benchmarks.harness.reporting — see docs/plans/2026-03-31-v1-build-plan-design.md for responsibilities."""

from datetime import datetime, timezone
from statistics import stdev

from benchmarks.harness.models import (
    FamilyScorecard,
    QualityRetentionFamilyScorecard,
    QualityRetentionSuiteScorecard,
    QualityRetentionVariantMetrics,
    RunRecord,
    RunValidity,
    SuiteScorecard,
    ToolEfficacyFamilyScorecard,
    ToolEfficacySuiteScorecard,
    ToolEfficacyVariantMetrics,
    Variant,
    VariantMetrics,
    ValidationStatus,
)

# Display-friendly agent names. Run records store class names; scorecards show these.
AGENT_DISPLAY_NAMES: dict[str, str] = {
    "ClaudeAdapter": "claude",
    "CodexAdapter": "codex",
    "GeminiCliAdapter": "gemini-cli",
}


def normalize_agent_id(raw_id: str) -> str:
    """Return a display-friendly agent name, falling back to the raw ID."""
    return AGENT_DISPLAY_NAMES.get(raw_id, raw_id)


def _compute_variant_metrics(runs: list[RunRecord], variant: Variant) -> VariantMetrics:
    """Compute averaged metrics for a single variant from a list of valid runs."""
    valid_runs = [r for r in runs if r.validity == RunValidity.valid and r.variant == variant]
    run_count = len(valid_runs)

    if run_count == 0:
        return VariantMetrics(variant=variant, run_count=0)

    # avg_tokens — only include runs that have a reported_total_tokens value
    token_values = [r.reported_total_tokens for r in valid_runs if r.reported_total_tokens is not None]
    avg_tokens = sum(token_values) / len(token_values) if token_values else None
    std_dev_tokens = stdev(token_values) if len(token_values) >= 2 else None

    # validation_pass_rate
    validation_pass_rate = sum(
        1 for r in valid_runs if r.validation_status == ValidationStatus.passed
    ) / run_count

    # first_pass_success_rate: passed on first attempt without any repair iterations
    first_pass_success_rate = sum(
        1 for r in valid_runs if r.validation_status == ValidationStatus.passed and r.repair_iterations == 0
    ) / run_count

    # avg_repair_iterations
    avg_repair_iterations = sum(r.repair_iterations for r in valid_runs) / run_count

    # avg_elapsed_seconds — only include runs that have elapsed_seconds
    elapsed_values = [r.elapsed_seconds for r in valid_runs if r.elapsed_seconds is not None]
    avg_elapsed_seconds = sum(elapsed_values) / len(elapsed_values) if elapsed_values else None
    std_dev_elapsed = stdev(elapsed_values) if len(elapsed_values) >= 2 else None

    return VariantMetrics(
        variant=variant,
        run_count=run_count,
        avg_tokens=avg_tokens,
        std_dev_tokens=std_dev_tokens,
        validation_pass_rate=validation_pass_rate,
        first_pass_success_rate=first_pass_success_rate,
        avg_repair_iterations=avg_repair_iterations,
        avg_elapsed_seconds=avg_elapsed_seconds,
        std_dev_elapsed=std_dev_elapsed,
    )


def aggregate_family(runs: list[RunRecord], family: str) -> FamilyScorecard:
    """Aggregate valid runs for a single family into a FamilyScorecard.

    Only valid runs (validity == "valid") contribute to VariantMetrics averages.
    """
    family_runs = [r for r in runs if r.family == family]

    baseline_metrics = _compute_variant_metrics(family_runs, Variant.baseline)
    tool_variant_metrics = _compute_variant_metrics(family_runs, Variant.tool_variant)

    # Compute token_delta and token_reduction_pct only when both sides have avg_tokens
    token_delta: float | None = None
    token_reduction_pct: float | None = None
    if baseline_metrics.avg_tokens is not None and tool_variant_metrics.avg_tokens is not None:
        token_delta = tool_variant_metrics.avg_tokens - baseline_metrics.avg_tokens
        token_reduction_pct = token_delta / baseline_metrics.avg_tokens * 100

    return FamilyScorecard(
        family=family,
        baseline=baseline_metrics,
        tool_variant=tool_variant_metrics,
        token_delta=token_delta,
        token_reduction_pct=token_reduction_pct,
    )


def generate_suite_scorecard(
    runs: list[RunRecord],
    agent_id: str,
    repo_commit: str,
) -> SuiteScorecard:
    """Generate a SuiteScorecard from a list of RunRecords.

    Groups runs by family, calls aggregate_family for each, and returns a
    SuiteScorecard with one FamilyScorecard per family (sorted alphabetically).
    """
    family_names: list[str] = []
    seen: set[str] = set()
    for run in runs:
        if run.family not in seen:
            family_names.append(run.family)
            seen.add(run.family)

    families = [aggregate_family(runs, family) for family in sorted(family_names)]

    return SuiteScorecard(
        agent_id=agent_id,
        generated_at=datetime.now(tz=timezone.utc),
        repo_commit=repo_commit,
        families=families,
    )


def generate_per_agent_scorecards(
    runs: list[RunRecord],
    repo_commit: str,
) -> dict[str, SuiteScorecard]:
    """Generate one SuiteScorecard per agent found in the run data.

    Returns a dict keyed by normalized agent display name (e.g. "claude").
    """
    agents: dict[str, list[RunRecord]] = {}
    for run in runs:
        agents.setdefault(run.agent_id, []).append(run)

    scorecards: dict[str, SuiteScorecard] = {}
    for raw_agent_id, agent_runs in sorted(agents.items()):
        display_name = normalize_agent_id(raw_agent_id)
        scorecards[display_name] = generate_suite_scorecard(
            agent_runs,
            agent_id=display_name,
            repo_commit=repo_commit,
        )
    return scorecards


def render_scorecard_markdown(scorecard: SuiteScorecard) -> str:
    """Render a SuiteScorecard as a markdown table."""
    header = (
        "| Family"
        " | Baseline runs"
        " | Variant runs"
        " | Baseline avg tokens"
        " | Baseline std dev"
        " | Variant avg tokens"
        " | Variant std dev"
        " | Token delta"
        " | Reduction %"
        " | Baseline val pass"
        " | Variant val pass"
        " | Baseline avg elapsed (s)"
        " | Variant avg elapsed (s)"
        " |"
    )
    separator = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"

    def _fmt_tokens(value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:,.0f}"

    def _fmt_pct(value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.1f}%"

    def _fmt_float(value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.1f}"

    rows: list[str] = []
    for fc in scorecard.families:
        b = fc.baseline
        v = fc.tool_variant

        b_val_pass = _fmt_pct(b.validation_pass_rate * 100 if b.validation_pass_rate is not None else None)
        v_val_pass = _fmt_pct(v.validation_pass_rate * 100 if v.validation_pass_rate is not None else None)

        row = (
            f"| {fc.family}"
            f" | {b.run_count}"
            f" | {v.run_count}"
            f" | {_fmt_tokens(b.avg_tokens)}"
            f" | {_fmt_tokens(b.std_dev_tokens)}"
            f" | {_fmt_tokens(v.avg_tokens)}"
            f" | {_fmt_tokens(v.std_dev_tokens)}"
            f" | {_fmt_tokens(fc.token_delta)}"
            f" | {_fmt_pct(fc.token_reduction_pct)}"
            f" | {b_val_pass}"
            f" | {v_val_pass}"
            f" | {_fmt_float(b.avg_elapsed_seconds)}"
            f" | {_fmt_float(v.avg_elapsed_seconds)}"
            f" |"
        )
        rows.append(row)

    lines = [f"# Scorecard: {scorecard.agent_id}", "", header, separator] + rows
    return "\n".join(lines) + "\n"


def render_scorecard_json(scorecard: SuiteScorecard) -> str:
    """Return a JSON serialization of the SuiteScorecard."""
    return scorecard.model_dump_json(indent=2)


def _fmt_metric(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def _fmt_rate(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _compute_tool_variant_metrics(
    runs: list[RunRecord],
    variant: Variant,
) -> ToolEfficacyVariantMetrics:
    relevant = [
        run
        for run in runs
        if run.variant == variant and run.track.value == "tool_only" and run.tool_metrics is not None
    ]
    if not relevant:
        return ToolEfficacyVariantMetrics(variant=variant, run_count=0)

    raw_bytes = [run.tool_metrics.raw_bytes for run in relevant if run.tool_metrics.raw_bytes is not None]
    reduced_bytes = [
        run.tool_metrics.reduced_bytes for run in relevant if run.tool_metrics.reduced_bytes is not None
    ]
    reduction_ratios = [
        run.tool_metrics.reduction_ratio
        for run in relevant
        if run.tool_metrics.reduction_ratio is not None
    ]
    elapsed = [run.elapsed_seconds for run in relevant if run.elapsed_seconds is not None]
    deterministic_passes = [
        run.tool_metrics.deterministic_valid for run in relevant if run.tool_metrics.deterministic_valid is not None
    ]

    return ToolEfficacyVariantMetrics(
        variant=variant,
        run_count=len(relevant),
        avg_raw_bytes=sum(raw_bytes) / len(raw_bytes) if raw_bytes else None,
        avg_reduced_bytes=sum(reduced_bytes) / len(reduced_bytes) if reduced_bytes else None,
        avg_reduction_ratio=sum(reduction_ratios) / len(reduction_ratios) if reduction_ratios else None,
        deterministic_pass_rate=(
            sum(1 for passed in deterministic_passes if passed) / len(deterministic_passes)
            if deterministic_passes
            else None
        ),
        avg_elapsed_seconds=sum(elapsed) / len(elapsed) if elapsed else None,
    )


def generate_tool_efficacy_scorecard(
    runs: list[RunRecord],
    repo_commit: str,
) -> ToolEfficacySuiteScorecard:
    families = sorted({run.family for run in runs if run.track.value == "tool_only"})
    return ToolEfficacySuiteScorecard(
        generated_at=datetime.now(tz=timezone.utc),
        repo_commit=repo_commit,
        families=[
            ToolEfficacyFamilyScorecard(
                family=family,
                baseline=_compute_tool_variant_metrics(
                    [run for run in runs if run.family == family],
                    Variant.baseline,
                ),
                tool_variant=_compute_tool_variant_metrics(
                    [run for run in runs if run.family == family],
                    Variant.tool_variant,
                ),
            )
            for family in families
        ],
    )


def _compute_quality_variant_metrics(
    runs: list[RunRecord],
    variant: Variant,
) -> QualityRetentionVariantMetrics:
    relevant = [
        run
        for run in runs
        if run.variant == variant and run.track.value == "quality_eval" and run.quality_metrics is not None
    ]
    if not relevant:
        return QualityRetentionVariantMetrics(variant=variant, run_count=0)

    raw_scores = [
        run.quality_metrics.raw_quality_score
        for run in relevant
        if run.quality_metrics.raw_quality_score is not None
    ]
    reduced_scores = [
        run.quality_metrics.reduced_quality_score
        for run in relevant
        if run.quality_metrics.reduced_quality_score is not None
    ]
    deltas = [
        run.quality_metrics.quality_delta
        for run in relevant
        if run.quality_metrics.quality_delta is not None
    ]
    return QualityRetentionVariantMetrics(
        variant=variant,
        run_count=len(relevant),
        avg_raw_quality_score=sum(raw_scores) / len(raw_scores) if raw_scores else None,
        avg_reduced_quality_score=sum(reduced_scores) / len(reduced_scores) if reduced_scores else None,
        avg_quality_delta=sum(deltas) / len(deltas) if deltas else None,
        llm_call_count_small=sum(run.quality_metrics.llm_call_count_small for run in relevant),
        llm_call_count_expensive=sum(run.quality_metrics.llm_call_count_expensive for run in relevant),
    )


def generate_quality_retention_scorecard(
    runs: list[RunRecord],
    repo_commit: str,
) -> QualityRetentionSuiteScorecard:
    families = sorted({run.family for run in runs if run.track.value == "quality_eval"})
    return QualityRetentionSuiteScorecard(
        generated_at=datetime.now(tz=timezone.utc),
        repo_commit=repo_commit,
        families=[
            QualityRetentionFamilyScorecard(
                family=family,
                baseline=_compute_quality_variant_metrics(
                    [run for run in runs if run.family == family],
                    Variant.baseline,
                ),
                tool_variant=_compute_quality_variant_metrics(
                    [run for run in runs if run.family == family],
                    Variant.tool_variant,
                ),
            )
            for family in families
        ],
    )


def render_tool_efficacy_markdown(scorecard: ToolEfficacySuiteScorecard) -> str:
    lines = [
        "# Tool Efficacy Scorecard",
        "",
        "| Family | Variant | Runs | Avg raw bytes | Avg reduced bytes | Avg reduction ratio | Deterministic pass | Avg elapsed (s) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for family in scorecard.families:
        for metrics in (family.baseline, family.tool_variant):
            lines.append(
                f"| {family.family} | {metrics.variant.value} | {metrics.run_count} | "
                f"{_fmt_metric(metrics.avg_raw_bytes)} | "
                f"{_fmt_metric(metrics.avg_reduced_bytes)} | "
                f"{_fmt_metric(metrics.avg_reduction_ratio, 3)} | "
                f"{_fmt_rate(metrics.deterministic_pass_rate)} | "
                f"{_fmt_metric(metrics.avg_elapsed_seconds)} |"
            )
    return "\n".join(lines) + "\n"


def render_quality_retention_markdown(scorecard: QualityRetentionSuiteScorecard) -> str:
    lines = [
        "# Quality Retention Scorecard",
        "",
        "| Family | Variant | Runs | Avg raw quality | Avg reduced quality | Avg quality delta | Small LLM calls | Expensive LLM calls |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for family in scorecard.families:
        for metrics in (family.baseline, family.tool_variant):
            lines.append(
                f"| {family.family} | {metrics.variant.value} | {metrics.run_count} | "
                f"{_fmt_metric(metrics.avg_raw_quality_score, 2)} | "
                f"{_fmt_metric(metrics.avg_reduced_quality_score, 2)} | "
                f"{_fmt_metric(metrics.avg_quality_delta, 2)} | "
                f"{metrics.llm_call_count_small} | {metrics.llm_call_count_expensive} |"
            )
    return "\n".join(lines) + "\n"


def render_tool_efficacy_json(scorecard: ToolEfficacySuiteScorecard) -> str:
    return scorecard.model_dump_json(indent=2)


def render_quality_retention_json(scorecard: QualityRetentionSuiteScorecard) -> str:
    return scorecard.model_dump_json(indent=2)
