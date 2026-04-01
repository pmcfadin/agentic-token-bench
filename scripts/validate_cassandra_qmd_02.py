"""Validation script for cassandra-qmd-02.

Checks that the agent's final answer addresses:
  - The compaction throughput configuration parameter in Cassandra
  - The relevant Java source file and field name
  - The current default value for the parameter

Usage:
    python scripts/validate_cassandra_qmd_02.py --task cassandra-qmd-02
    python scripts/validate_cassandra_qmd_02.py --task cassandra-qmd-02 /path/to/artifacts

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
# Known-good hints that should appear in a correct answer.
# These relate to compaction throughput configuration in the Cassandra 5.0.x
# source tree.
# ---------------------------------------------------------------------------

_COMPACTION_CONFIG_HINTS = [
    "compaction_throughput",
    "CompactionManager",
    "cassandra.yaml",
]

_COMPACTION_CONCEPT_HINTS = [
    "compaction",
    "throughput",
    "mb_per_sec",
]

_DEFAULT_VALUE_HINTS = [
    "default",
    "mb_per_sec",
    "MiB",
    "mebibyte",
    "megabyte",
    "0",
    "16",
    "64",
    "128",
    "256",
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


def _check_field(answer_text: str, hints: list[str], field_name: str) -> tuple[bool, str]:
    """Return (found, detail) indicating whether any hint appears in the answer."""
    lower = answer_text.lower()
    for hint in hints:
        if hint.lower() in lower:
            return True, f"{field_name}: found hint '{hint}'"
    return False, f"{field_name}: none of the expected hints found in answer"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate cassandra-qmd-02 answer")
    parser.add_argument("--task", required=True, help="Task ID (must be cassandra-qmd-02)")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task != "cassandra-qmd-02":
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

    compaction_config_ok, compaction_config_detail = _check_field(
        answer_text, _COMPACTION_CONFIG_HINTS, "compaction_config"
    )
    compaction_concept_ok, compaction_concept_detail = _check_field(
        answer_text, _COMPACTION_CONCEPT_HINTS, "compaction_concept"
    )
    default_value_ok, default_value_detail = _check_field(
        answer_text, _DEFAULT_VALUE_HINTS, "default_value"
    )

    passed = [compaction_config_ok, compaction_concept_ok, default_value_ok]
    details = {
        "compaction_config": compaction_config_detail,
        "compaction_concept": compaction_concept_detail,
        "default_value": default_value_detail,
    }

    pass_count = sum(passed)

    if pass_count == 3:
        print(json.dumps({"status": "pass", "details": details}))
        sys.exit(0)
    elif pass_count >= 1:
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)
    else:
        print(json.dumps({"status": "fail", "details": details}))
        sys.exit(1)


if __name__ == "__main__":
    main()
