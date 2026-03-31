"""benchmarks.harness.reporting — see docs/plans/2026-03-31-v1-build-plan-design.md for responsibilities."""

from datetime import datetime, timezone

from benchmarks.harness.models import (
    FamilyScorecard,
    RunRecord,
    RunValidity,
    SuiteScorecard,
    Variant,
    VariantMetrics,
    ValidationStatus,
)


def _compute_variant_metrics(runs: list[RunRecord], variant: Variant) -> VariantMetrics:
    """Compute averaged metrics for a single variant from a list of valid runs."""
    valid_runs = [r for r in runs if r.validity == RunValidity.valid and r.variant == variant]
    run_count = len(valid_runs)

    if run_count == 0:
        return VariantMetrics(variant=variant, run_count=0)

    # avg_tokens — only include runs that have a reported_total_tokens value
    token_values = [r.reported_total_tokens for r in valid_runs if r.reported_total_tokens is not None]
    avg_tokens = sum(token_values) / len(token_values) if token_values else None

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

    return VariantMetrics(
        variant=variant,
        run_count=run_count,
        avg_tokens=avg_tokens,
        validation_pass_rate=validation_pass_rate,
        first_pass_success_rate=first_pass_success_rate,
        avg_repair_iterations=avg_repair_iterations,
        avg_elapsed_seconds=avg_elapsed_seconds,
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


def render_scorecard_markdown(scorecard: SuiteScorecard) -> str:
    """Render a SuiteScorecard as a markdown table.

    Columns: Family, Baseline runs, Variant runs, Baseline avg tokens,
    Variant avg tokens, Token delta, Reduction %, Baseline val pass,
    Variant val pass, Baseline 1st-pass, Variant 1st-pass,
    Baseline avg repairs, Variant avg repairs,
    Baseline avg elapsed (s), Variant avg elapsed (s).
    """
    header = (
        "| Family"
        " | Baseline runs"
        " | Variant runs"
        " | Baseline avg tokens"
        " | Variant avg tokens"
        " | Token delta"
        " | Reduction %"
        " | Baseline val pass"
        " | Variant val pass"
        " | Baseline 1st-pass"
        " | Variant 1st-pass"
        " | Baseline avg repairs"
        " | Variant avg repairs"
        " | Baseline avg elapsed (s)"
        " | Variant avg elapsed (s)"
        " |"
    )
    separator = "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"

    def _fmt_tokens(value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.0f}"

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
        b_first_pass = _fmt_pct(b.first_pass_success_rate * 100 if b.first_pass_success_rate is not None else None)
        v_first_pass = _fmt_pct(v.first_pass_success_rate * 100 if v.first_pass_success_rate is not None else None)

        row = (
            f"| {fc.family}"
            f" | {b.run_count}"
            f" | {v.run_count}"
            f" | {_fmt_tokens(b.avg_tokens)}"
            f" | {_fmt_tokens(v.avg_tokens)}"
            f" | {_fmt_tokens(fc.token_delta)}"
            f" | {_fmt_pct(fc.token_reduction_pct)}"
            f" | {b_val_pass}"
            f" | {v_val_pass}"
            f" | {b_first_pass}"
            f" | {v_first_pass}"
            f" | {_fmt_float(b.avg_repair_iterations)}"
            f" | {_fmt_float(v.avg_repair_iterations)}"
            f" | {_fmt_float(b.avg_elapsed_seconds)}"
            f" | {_fmt_float(v.avg_elapsed_seconds)}"
            f" |"
        )
        rows.append(row)

    lines = [header, separator] + rows
    return "\n".join(lines) + "\n"


def render_scorecard_json(scorecard: SuiteScorecard) -> str:
    """Return a JSON serialization of the SuiteScorecard."""
    return scorecard.model_dump_json(indent=2)
