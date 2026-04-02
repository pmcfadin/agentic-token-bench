"""Generate official scorecards from real run records in benchmarks/results/.

Produces:
- benchmarks/results/scorecard.md
- benchmarks/results/scorecard.json
- benchmarks/results/<family>_scorecard.md  (per-family)
- benchmarks/results/<family>_scorecard.json (per-family)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to sys.path so the script works when invoked directly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from benchmarks.harness.models import RunRecord, SuiteScorecard  # noqa: E402
from benchmarks.harness.reporting import (  # noqa: E402
    aggregate_family,
    generate_suite_scorecard,
    render_scorecard_json,
    render_scorecard_markdown,
)

RESULTS_DIR = Path("benchmarks/results")
AGENT_ID = "claude"
REPO_COMMIT = "0269fd5665751e8a6d8eab852e0f66c142b10ee6"


def load_runs(results_dir: Path) -> list[RunRecord]:
    """Load all run.json files from results_dir tree."""
    runs: list[RunRecord] = []
    for json_path in sorted(results_dir.rglob("run.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            runs.append(RunRecord.model_validate(data))
        except Exception as exc:  # noqa: BLE001
            print(f"  WARNING: skipping {json_path}: {exc}", file=sys.stderr)
    return runs


def generate_per_family_scorecard(
    runs: list[RunRecord],
    family: str,
    output_dir: Path,
) -> None:
    """Generate markdown and JSON scorecards for a single family."""
    from datetime import datetime, timezone

    family_runs = [r for r in runs if r.family == family]
    fc = aggregate_family(family_runs, family)

    # Wrap in a SuiteScorecard for rendering
    suite = SuiteScorecard(
        agent_id=AGENT_ID,
        generated_at=datetime.now(tz=timezone.utc),
        repo_commit=REPO_COMMIT,
        families=[fc],
    )

    md_path = output_dir / f"{family}_scorecard.md"
    json_path = output_dir / f"{family}_scorecard.json"

    md_path.write_text(render_scorecard_markdown(suite), encoding="utf-8")
    json_path.write_text(render_scorecard_json(suite), encoding="utf-8")

    token_reduction = fc.token_reduction_pct
    reduction_str = f"{token_reduction:.1f}%" if token_reduction is not None else "N/A"
    print(
        f"  {family}: baseline_runs={fc.baseline.run_count}"
        f"  variant_runs={fc.tool_variant.run_count}"
        f"  token_reduction={reduction_str}"
    )
    print(f"    → {md_path}")
    print(f"    → {json_path}")


def main(results_dir: Path | None = None, output_dir: Path | None = None) -> None:
    if results_dir is None:
        results_dir = RESULTS_DIR
    if output_dir is None:
        output_dir = results_dir

    if not results_dir.exists():
        print(f"ERROR: results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading runs from {results_dir.resolve()} …")
    runs = load_runs(results_dir)

    if not runs:
        print("ERROR: no valid run records found", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(runs)} run records.")

    # --- Suite scorecard ---
    suite = generate_suite_scorecard(runs, agent_id=AGENT_ID, repo_commit=REPO_COMMIT)

    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "scorecard.md"
    json_path = output_dir / "scorecard.json"

    md_path.write_text(render_scorecard_markdown(suite), encoding="utf-8")
    json_path.write_text(render_scorecard_json(suite), encoding="utf-8")

    print(f"\nSuite scorecard ({len(suite.families)} families):")
    print(f"  → {md_path}")
    print(f"  → {json_path}")

    # --- Per-family scorecards ---
    print("\nPer-family scorecards:")
    for fc in suite.families:
        generate_per_family_scorecard(runs, fc.family, output_dir)

    print(f"\nDone. Generated scorecards for {len(suite.families)} families.")


if __name__ == "__main__":
    results_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    output_arg = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    main(results_dir=results_arg, output_dir=output_arg)
