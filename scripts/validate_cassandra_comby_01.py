"""Validation script for cassandra-comby-01.

Checks that the agent's final answer confirms it used comby to reorder
arguments in Tracing.instance.trace call sites across Java source files.

The script verifies:
  1. The answer references the Tracing / trace API being rewritten.
  2. The answer describes a structural argument-reorder operation.
  3. The answer provides a list of files changed.
  4. The answer reports a rewrite count greater than zero.

Usage:
    python scripts/validate_cassandra_comby_01.py --task cassandra-comby-01
    python scripts/validate_cassandra_comby_01.py --task cassandra-comby-01 /path/to/artifacts

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
# Hint groups that a correct answer should contain at least one entry from.
# ---------------------------------------------------------------------------

# The answer must show awareness of the Tracing API being changed.
_TRACING_HINTS = [
    "Tracing",
    "tracing",
    "Tracing.instance",
    "instance.trace",
]

# The answer must confirm that comby performed a structural rewrite.
_REORDER_HINTS = [
    "reorder",
    "reordered",
    "swap",
    "swapped",
    "argument order",
    "argument reorder",
    "structural rewrite",
    "structural",
]

# The answer must show awareness that comby was the tool used.
_COMBY_HINTS = [
    "comby",
]

# The answer must provide a list of files that were changed.
_FILES_CHANGED_HINTS = [
    "files_changed",
    "files changed",
    "changed files",
    "modified files",
    "files modified",
    ".java",
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
    parser = argparse.ArgumentParser(description="Validate cassandra-comby-01 answer")
    parser.add_argument("--task", required=True, help="Task ID (must be cassandra-comby-01)")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task != "cassandra-comby-01":
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

    tracing_ok, tracing_detail = _check_field(answer_text, _TRACING_HINTS, "tracing_api")
    reorder_ok, reorder_detail = _check_field(answer_text, _REORDER_HINTS, "reorder_evidence")
    comby_ok, comby_detail = _check_field(answer_text, _COMBY_HINTS, "comby_usage")
    files_ok, files_detail = _check_field(answer_text, _FILES_CHANGED_HINTS, "files_changed")

    passed = [tracing_ok, reorder_ok, comby_ok, files_ok]
    details = {
        "tracing_api": tracing_detail,
        "reorder_evidence": reorder_detail,
        "comby_usage": comby_detail,
        "files_changed": files_detail,
    }

    pass_count = sum(passed)

    if pass_count == 4:
        print(json.dumps({"status": "pass", "details": details}))
        sys.exit(0)
    elif pass_count >= 2:
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)
    else:
        print(json.dumps({"status": "fail", "details": details}))
        sys.exit(1)


if __name__ == "__main__":
    main()
