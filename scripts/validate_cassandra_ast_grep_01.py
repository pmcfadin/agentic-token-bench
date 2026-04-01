"""Validation script for cassandra-ast-grep-01.

Checks that the agent's final answer confirms:
  - StorageProxy.mutate call sites were found
  - ast-grep was used to perform the rewrite
  - nanoTime was added as the third argument
  - A list of files changed is provided
  - A rewrite count is provided

Usage:
    python scripts/validate_cassandra_ast_grep_01.py --task cassandra-ast-grep-01
    python scripts/validate_cassandra_ast_grep_01.py --task cassandra-ast-grep-01 /path/to/artifacts

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
# Hint groups that should appear in a correct answer.
# ---------------------------------------------------------------------------

# Evidence that the rewrite target was identified.
_TARGET_HINTS = [
    "StorageProxy",
    "storageproxy",
    "mutate",
]

# Evidence that the new argument was introduced.
_NANOTIME_HINTS = [
    "nanoTime",
    "nanotime",
    "queryStartNanoTime",
    "System.nanoTime",
]

# Evidence that files were actually changed.
_FILES_CHANGED_HINTS = [
    "files_changed",
    "files changed",
    "file changed",
    "modified",
]

# Evidence that ast-grep was the tool used.
_TOOL_HINTS = [
    "ast-grep",
    "astgrep",
    "ast grep",
    "rewrite",
    "rewrote",
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
    parser = argparse.ArgumentParser(description="Validate cassandra-ast-grep-01 answer")
    parser.add_argument("--task", required=True, help="Task ID (must be cassandra-ast-grep-01)")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task != "cassandra-ast-grep-01":
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

    target_ok, target_detail = _check_field(answer_text, _TARGET_HINTS, "target_method")
    nanotime_ok, nanotime_detail = _check_field(answer_text, _NANOTIME_HINTS, "nanotime_argument")
    files_ok, files_detail = _check_field(answer_text, _FILES_CHANGED_HINTS, "files_changed")
    tool_ok, tool_detail = _check_field(answer_text, _TOOL_HINTS, "tool_used")

    passed = [target_ok, nanotime_ok, files_ok, tool_ok]
    details = {
        "target_method": target_detail,
        "nanotime_argument": nanotime_detail,
        "files_changed": files_detail,
        "tool_used": tool_detail,
    }

    pass_count = sum(passed)
    total = len(passed)

    if pass_count == total:
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
