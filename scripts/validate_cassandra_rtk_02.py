"""Validation script for cassandra-rtk-02.

Checks that the agent's final answer identifies the failing test and the
exception or assertion message from Cassandra test output compressed by rtk.
The script verifies:

  1. The answer references a test failure indicator (test, fail, assert,
     Exception, error, or a specific test class name).
  2. The answer provides a specific failing test method name or exception
     type — not just a vague mention that something failed.

Usage:
    python scripts/validate_cassandra_rtk_02.py --task cassandra-rtk-02
    python scripts/validate_cassandra_rtk_02.py --task cassandra-rtk-02 /path/to/artifacts

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
# Hints that indicate a test failure was surfaced at all.
# A correct answer must contain at least one of these.
# ---------------------------------------------------------------------------

_FAILURE_HINTS = [
    "test",
    "Test",
    "fail",
    "Fail",
    "FAIL",
    "assert",
    "Assert",
    "Exception",
    "exception",
    "error",
    "Error",
    "FAILED",
]

# ---------------------------------------------------------------------------
# Hints that indicate the answer is specific and actionable — names a real
# test class, method, or exception type rather than speaking only in
# generalities.  At least one must appear for a full pass.
# ---------------------------------------------------------------------------

_SPECIFIC_HINTS = [
    # The specific test class named in the task.
    "CompactionManagerTest",
    "compactionmanagertest",
    # Common JUnit / Cassandra test infrastructure signals.
    "testCompaction",
    "testStart",
    "testStop",
    "testShutdown",
    # Exception / assertion patterns that appear in test output.
    "AssertionError",
    "NullPointerException",
    "IllegalStateException",
    "IllegalArgumentException",
    "RuntimeException",
    "IOException",
    "java.lang",
    "java.io",
    "org.junit",
    "org.apache.cassandra",
    # Ant test output markers.
    "FAILED",
    "Tests run:",
    "Failures:",
    "Errors:",
    "BUILD FAILED",
    # Stack trace signals indicating depth of detail.
    "at org.",
    "at java.",
    "Expected:",
    "but was:",
    "expected:<",
    "but was:<",
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
    parser = argparse.ArgumentParser(description="Validate cassandra-rtk-02 answer")
    parser.add_argument("--task", required=True, help="Task ID (must be cassandra-rtk-02)")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task != "cassandra-rtk-02":
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
    specific_ok, specific_detail = _check_field(answer_text, _SPECIFIC_HINTS, "specific_detail")

    details = {
        "failure_identified": failure_detail,
        "specific_detail": specific_detail,
    }

    if failure_ok and specific_ok:
        # Full pass: test failure identified with specific, actionable detail.
        print(json.dumps({"status": "pass", "details": details}))
        sys.exit(0)
    elif failure_ok:
        # Partial pass: failure mentioned but answer lacks specific test/exception detail.
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)
    else:
        # Fail: no test failure identified at all.
        print(json.dumps({"status": "fail", "details": details}))
        sys.exit(1)


if __name__ == "__main__":
    main()
