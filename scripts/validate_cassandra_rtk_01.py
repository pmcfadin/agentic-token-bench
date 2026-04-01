"""Validation script for cassandra-rtk-01.

Checks that the agent's final answer identifies the actionable build failure
from noisy Cassandra build output compressed by rtk.  The script verifies:

  1. The answer references a specific build failure indicator (BUILD FAILED,
     error, failure, compile, javac, or a concrete class/file name).
  2. The answer provides actionable detail — not just a vague mention of
     failure but an identifiable component, file, or error message.

Usage:
    python scripts/validate_cassandra_rtk_01.py --task cassandra-rtk-01
    python scripts/validate_cassandra_rtk_01.py --task cassandra-rtk-01 /path/to/artifacts

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
# Hints that indicate a failure was surfaced at all.
# A correct answer must contain at least one of these.
# ---------------------------------------------------------------------------

_FAILURE_HINTS = [
    "BUILD FAILED",
    "build failed",
    "error",
    "Error",
    "failure",
    "Failure",
    "FAILED",
    "compile",
    "Compile",
    "javac",
]

# ---------------------------------------------------------------------------
# Hints that indicate the answer is specific and actionable, not just vague.
# At least one of these must appear alongside a failure hint for a full pass.
# These represent the kinds of concrete detail a correct answer should include:
# a Java class name, a file path, an exception type, or a specific error token.
# ---------------------------------------------------------------------------

_ACTIONABLE_HINTS = [
    # Java source / class signals
    ".java",
    ".class",
    "Exception",
    "exception",
    # Ant build targets and output patterns
    "BUILD FAILED",
    "build.xml",
    "[javac]",
    # Any mention of a specific component or package path
    "org.apache",
    "cassandra",
    "Cassandra",
    # Specific error tokens that appear in ant/javac output
    "cannot find symbol",
    "error:",
    "warning:",
    "incompatible types",
    "package does not exist",
    "symbol:",
    "location:",
    "compilation failed",
    "Compilation failed",
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
    for hint in hints:
        if hint in answer_text:
            return True, f"{field_name}: found hint '{hint}'"
    return False, f"{field_name}: none of the expected hints found in answer"


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate cassandra-rtk-01 answer")
    parser.add_argument("--task", required=True, help="Task ID (must be cassandra-rtk-01)")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task != "cassandra-rtk-01":
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

    failure_ok, failure_detail = _check_field(answer_text, _FAILURE_HINTS, "failure_identified")
    actionable_ok, actionable_detail = _check_field(
        answer_text, _ACTIONABLE_HINTS, "actionable_detail"
    )

    details = {
        "failure_identified": failure_detail,
        "actionable_detail": actionable_detail,
    }

    if failure_ok and actionable_ok:
        # Full pass: failure identified with specific, actionable detail.
        print(json.dumps({"status": "pass", "details": details}))
        sys.exit(0)
    elif failure_ok:
        # Partial pass: failure mentioned but answer lacks actionable specificity.
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)
    else:
        # Fail: no failure identified at all.
        print(json.dumps({"status": "fail", "details": details}))
        sys.exit(1)


if __name__ == "__main__":
    main()
