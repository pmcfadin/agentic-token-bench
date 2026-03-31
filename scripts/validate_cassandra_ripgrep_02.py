"""Validation script for cassandra-ripgrep-02.

Checks that the agent's final answer lists source file paths referencing
SizeTieredCompactionStrategy.  The script verifies:

  1. At least a minimum expected number of paths are reported.
  2. The reported paths all plausibly belong to the Cassandra source tree
     (no made-up or obviously wrong paths).
  3. Key known files that reference STCS are present in the answer.

Usage:
    python scripts/validate_cassandra_ripgrep_02.py --task cassandra-ripgrep-02
    python scripts/validate_cassandra_ripgrep_02.py --task cassandra-ripgrep-02 /path/to/artifacts

Exit codes:
    0  full pass
    1  fail
    2  partial pass (triggers human review)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Known files in cassandra-5.0.7 that reference SizeTieredCompactionStrategy.
# A correct answer must include at least these paths (or path fragments that
# unambiguously identify them).
# ---------------------------------------------------------------------------

_REQUIRED_PATH_FRAGMENTS = [
    "SizeTieredCompactionStrategy.java",
    "SizeTieredCompactionStrategyOptions.java",
]

# A healthy answer should contain at least this many distinct path references.
_MIN_PATH_COUNT = 5

# Path fragments that are always wrong (sanity check for hallucinated paths).
_DISALLOWED_FRAGMENTS = [
    "/home/",
    "/Users/",
    "C:\\",
]


def _load_final_answer(artifact_dir: Path) -> str:
    answer_file = artifact_dir / "final_answer.txt"
    if not answer_file.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "details": {
                        "error": f"final_answer.txt not found in {artifact_dir}"
                    },
                }
            )
        )
        sys.exit(1)
    return answer_file.read_text()


def _count_path_references(answer_text: str) -> int:
    """Heuristic count of distinct path references in the answer.

    Counts lines that contain a forward slash and end with a Java or YAML
    file extension, which is a reliable signal for file paths in Cassandra.
    """
    count = 0
    for line in answer_text.splitlines():
        stripped = line.strip().strip(",-")
        if "/" in stripped and any(
            stripped.endswith(ext) for ext in (".java", ".yaml", ".yml", ".xml", ".cql")
        ):
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate cassandra-ripgrep-02 answer")
    parser.add_argument("--task", required=True, help="Task ID (must be cassandra-ripgrep-02)")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task != "cassandra-ripgrep-02":
        print(
            json.dumps(
                {
                    "status": "fail",
                    "details": {"error": f"unexpected task id: {args.task}"},
                }
            )
        )
        sys.exit(1)

    raw_dir = args.artifact_dir or os.environ.get("ATB_ARTIFACT_DIR", ".")
    artifact_dir = Path(raw_dir)

    answer_text = _load_final_answer(artifact_dir)
    lower_answer = answer_text.lower()

    # Check that required path fragments appear in the answer.
    missing_required: list[str] = []
    for fragment in _REQUIRED_PATH_FRAGMENTS:
        if fragment.lower() not in lower_answer:
            missing_required.append(fragment)

    # Check for disallowed (hallucinated absolute) path prefixes.
    false_positives: list[str] = []
    for fragment in _DISALLOWED_FRAGMENTS:
        if fragment in answer_text:
            false_positives.append(fragment)

    # Count path references as a completeness signal.
    path_count = _count_path_references(answer_text)
    count_ok = path_count >= _MIN_PATH_COUNT

    details = {
        "required_paths_missing": missing_required,
        "false_positive_fragments": false_positives,
        "path_count": path_count,
        "min_path_count": _MIN_PATH_COUNT,
        "count_ok": count_ok,
    }

    # Hard fail: false positives or all required paths missing.
    if false_positives or len(missing_required) == len(_REQUIRED_PATH_FRAGMENTS):
        print(json.dumps({"status": "fail", "details": details}))
        sys.exit(1)

    # Partial pass: some required paths missing or count too low.
    if missing_required or not count_ok:
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)

    # Full pass.
    print(json.dumps({"status": "pass", "details": details}))
    sys.exit(0)


if __name__ == "__main__":
    main()
