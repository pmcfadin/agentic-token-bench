"""scripts/run_pilot.py — Fixture-based pilot pipeline demonstration.

Creates mock RunRecord fixtures for the ripgrep task family (2 tasks x 2 variants),
generates a scorecard, and writes everything to tests/fixtures/pilot_results/.

Usage:
    uv run python scripts/run_pilot.py
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.harness.models import (
    RunRecord,
)
from benchmarks.harness.reporting import (
    generate_suite_scorecard,
    render_scorecard_json,
    render_scorecard_markdown,
)

PILOT_RESULTS_DIR = Path("tests/fixtures/pilot_results")
FIXTURES_DIR = Path("tests/fixtures/pilot_runs")
PINNED_COMMIT = "0269fd5665751e8a6d8eab852e0f66c142b10ee6"
AGENT_ID = "ClaudeAdapter"


def load_fixture_runs() -> list[RunRecord]:
    """Load the four pilot fixture RunRecords from JSON files."""
    fixture_files = [
        "cassandra-ripgrep-01-baseline.json",
        "cassandra-ripgrep-01-tool_variant.json",
        "cassandra-ripgrep-02-baseline.json",
        "cassandra-ripgrep-02-tool_variant.json",
    ]
    runs: list[RunRecord] = []
    for fname in fixture_files:
        path = FIXTURES_DIR / fname
        data = json.loads(path.read_text(encoding="utf-8"))
        runs.append(RunRecord.model_validate(data))
    return runs


def write_run_records(runs: list[RunRecord], results_dir: Path) -> None:
    """Write each RunRecord as run.json inside its artifact subdirectory."""
    for run in runs:
        artifact_dir = results_dir / run.run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        run_json = artifact_dir / "run.json"
        run_json.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        print(f"  wrote {run_json}")


def main() -> None:
    print("=== Pilot Pipeline: ripgrep family ===\n")

    # Load fixture run records
    print("Loading fixture run records from tests/fixtures/pilot_runs/ ...")
    runs = load_fixture_runs()
    print(f"  loaded {len(runs)} run records\n")

    # Write run records to results directory
    print(f"Writing run records to {PILOT_RESULTS_DIR}/ ...")
    PILOT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_run_records(runs, PILOT_RESULTS_DIR)
    print()

    # Generate scorecard
    print("Generating scorecard ...")
    scorecard = generate_suite_scorecard(
        runs,
        agent_id=AGENT_ID,
        repo_commit=PINNED_COMMIT,
    )

    md_path = PILOT_RESULTS_DIR / "scorecard.md"
    json_path = PILOT_RESULTS_DIR / "scorecard.json"

    md_path.write_text(render_scorecard_markdown(scorecard), encoding="utf-8")
    json_path.write_text(render_scorecard_json(scorecard), encoding="utf-8")

    print(f"  wrote {md_path}")
    print(f"  wrote {json_path}\n")

    # Print summary
    print("=== Scorecard Summary ===\n")
    for fc in scorecard.families:
        b = fc.baseline
        v = fc.tool_variant
        print(f"Family: {fc.family}")
        print(f"  Baseline  runs={b.run_count}  avg_tokens={b.avg_tokens:.0f}  avg_elapsed={b.avg_elapsed_seconds:.1f}s")
        print(f"  Variant   runs={v.run_count}  avg_tokens={v.avg_tokens:.0f}  avg_elapsed={v.avg_elapsed_seconds:.1f}s")
        if fc.token_reduction_pct is not None:
            print(f"  Token reduction: {fc.token_reduction_pct:.1f}%  (delta={fc.token_delta:.0f})")
        print()

    print("Done.")


if __name__ == "__main__":
    main()
