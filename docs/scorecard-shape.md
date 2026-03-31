# Scorecard Shape

This document describes the scorecard data model used to compare baseline and tool-variant runs for each official tool family.

## Overview

A scorecard summarises the results of a completed benchmark suite run for one agent. The top-level object is a `SuiteScorecard`. It contains one `FamilyScorecard` per tool family. Each `FamilyScorecard` holds two `VariantMetrics` objects — one for the `baseline` variant and one for the `tool_variant`.

## Data Model

### `VariantMetrics`

Averaged metrics for one variant (baseline or tool_variant) across all valid runs in a family.

| Field | Type | Description |
|---|---|---|
| `variant` | `"baseline"` or `"tool_variant"` | Which variant these metrics describe |
| `run_count` | `int` | Number of valid runs included in the averages |
| `avg_tokens` | `float \| null` | Average reported total tokens across runs |
| `validation_pass_rate` | `float \| null` | Fraction of runs where validation passed (0.0–1.0) |
| `first_pass_success_rate` | `float \| null` | Fraction of runs that passed on the first attempt without repair (0.0–1.0) |
| `avg_repair_iterations` | `float \| null` | Average number of repair iterations across runs |
| `avg_elapsed_seconds` | `float \| null` | Average wall-clock elapsed time in seconds |

Optional fields are `null` when no valid runs contributed data.

### `FamilyScorecard`

Per-family comparison between baseline and tool_variant.

| Field | Type | Description |
|---|---|---|
| `family` | `str` | Tool family name (e.g. `"ripgrep"`, `"rtk"`) |
| `baseline` | `VariantMetrics` | Averaged metrics for the baseline variant |
| `tool_variant` | `VariantMetrics` | Averaged metrics for the tool_variant |
| `token_delta` | `float \| null` | `tool_variant.avg_tokens - baseline.avg_tokens` (negative means reduction) |
| `token_reduction_pct` | `float \| null` | `token_delta / baseline.avg_tokens * 100` (negative means reduction) |

`token_delta` and `token_reduction_pct` are `null` when either variant has no `avg_tokens` value.

### `SuiteScorecard`

Top-level scorecard for a complete suite run.

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | Identifier of the agent that produced the runs (e.g. `"claude"`) |
| `generated_at` | `datetime` | ISO 8601 timestamp when the scorecard was generated |
| `repo_commit` | `str` | Pinned repository commit SHA used for all runs in the suite |
| `families` | `list[FamilyScorecard]` | One entry per official tool family |

## Example JSON Output

```json
{
  "agent_id": "claude",
  "generated_at": "2026-03-31T12:00:00Z",
  "repo_commit": "abc1234",
  "families": [
    {
      "family": "ripgrep",
      "baseline": {
        "variant": "baseline",
        "run_count": 3,
        "avg_tokens": 12500.0,
        "validation_pass_rate": 1.0,
        "first_pass_success_rate": 0.67,
        "avg_repair_iterations": 1.0,
        "avg_elapsed_seconds": 42.5
      },
      "tool_variant": {
        "variant": "tool_variant",
        "run_count": 3,
        "avg_tokens": 4800.0,
        "validation_pass_rate": 1.0,
        "first_pass_success_rate": 1.0,
        "avg_repair_iterations": 0.0,
        "avg_elapsed_seconds": 28.1
      },
      "token_delta": -7700.0,
      "token_reduction_pct": -61.6
    },
    {
      "family": "rtk",
      "baseline": {
        "variant": "baseline",
        "run_count": 3,
        "avg_tokens": 9800.0,
        "validation_pass_rate": 1.0,
        "first_pass_success_rate": 0.67,
        "avg_repair_iterations": 1.0,
        "avg_elapsed_seconds": 38.2
      },
      "tool_variant": {
        "variant": "tool_variant",
        "run_count": 3,
        "avg_tokens": 3100.0,
        "validation_pass_rate": 1.0,
        "first_pass_success_rate": 1.0,
        "avg_repair_iterations": 0.0,
        "avg_elapsed_seconds": 22.9
      },
      "token_delta": -6700.0,
      "token_reduction_pct": -68.37
    }
  ]
}
```

## Example Markdown Table Format

The table below shows the per-family summary view suitable for reports and findings documents.

| Family | Baseline runs | Variant runs | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % | Baseline val pass | Variant val pass | Baseline 1st-pass | Variant 1st-pass | Baseline avg repairs | Variant avg repairs | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ripgrep | 3 | 3 | 12500 | 4800 | -7700 | -61.6% | 100% | 100% | 67% | 100% | 1.0 | 0.0 | 42.5 | 28.1 |
| rtk | 3 | 3 | 9800 | 3100 | -6700 | -68.4% | 100% | 100% | 67% | 100% | 1.0 | 0.0 | 38.2 | 22.9 |

Reduction percentage is computed as `(variant_avg_tokens - baseline_avg_tokens) / baseline_avg_tokens * 100`. A negative value indicates the tool variant used fewer tokens than the baseline.

## Notes

- Only valid runs (as classified by `RunValidity.valid`) contribute to `VariantMetrics` averages.
- Invalid runs are excluded from scorecards per the official run validity rules.
- `token_delta` and `token_reduction_pct` are derived fields. They are stored on `FamilyScorecard` rather than recomputed each time to keep the serialised scorecard self-contained.
- All token counts use reported values only. Estimated token counts are not allowed in official scorecards.
