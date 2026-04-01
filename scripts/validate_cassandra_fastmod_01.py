"""Validation script for cassandra-fastmod-01.

Checks that the agent's final answer confirms:
  - The replacement of `read_repair_chance` with `read_repair` was performed
  - A file count (number of files changed) is provided
  - Evidence that fastmod was the tool used

Usage:
    python scripts/validate_cassandra_fastmod_01.py --task cassandra-fastmod-01
    python scripts/validate_cassandra_fastmod_01.py --task cassandra-fastmod-01 /path/to/artifacts

Exit codes:
    0  full pass
    1  fail
    2  partial pass (triggers human review)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Hints indicating the agent confirmed the replacement was carried out.
# ---------------------------------------------------------------------------

_REPLACEMENT_HINTS = [
    "read_repair_chance",
    "read_repair",
    "replaced",
    "replacement",
    "files_changed",
    "fastmod",
]

# A file count is present when the answer contains a digit (files changed).
_FILE_COUNT_PATTERN = re.compile(r"\b\d+\s*(file|java)", re.IGNORECASE)


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


def _check_file_count(answer_text: str) -> tuple[bool, str]:
    """Return (found, detail) indicating whether a file count appears in the answer."""
    if _FILE_COUNT_PATTERN.search(answer_text):
        return True, "file_count: numeric file count found in answer"
    # Also accept standalone digits near relevant keywords
    lower = answer_text.lower()
    for keyword in ("changed", "modified", "updated"):
        idx = lower.find(keyword)
        if idx != -1:
            surrounding = answer_text[max(0, idx - 30) : idx + 30]
            if re.search(r"\d+", surrounding):
                return True, f"file_count: digit found near '{keyword}'"
    return False, "file_count: no numeric file count found in answer"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate cassandra-fastmod-01 answer")
    parser.add_argument("--task", required=True, help="Task ID (must be cassandra-fastmod-01)")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task != "cassandra-fastmod-01":
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

    replacement_ok, replacement_detail = _check_field(
        answer_text, _REPLACEMENT_HINTS, "replacement"
    )
    file_count_ok, file_count_detail = _check_file_count(answer_text)

    details = {
        "replacement": replacement_detail,
        "file_count": file_count_detail,
    }

    # Full pass: replacement confirmed AND file count provided.
    if replacement_ok and file_count_ok:
        print(json.dumps({"status": "pass", "details": details}))
        sys.exit(0)

    # Partial pass: replacement mentioned but no count, or count without context.
    if replacement_ok or file_count_ok:
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)

    # Fail: no evidence of replacement at all.
    print(json.dumps({"status": "fail", "details": details}))
    sys.exit(1)


if __name__ == "__main__":
    main()
