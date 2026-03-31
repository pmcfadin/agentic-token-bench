"""Validation script for cassandra-ripgrep-01.

Checks that the agent's final answer identifies:
  - A plausible Java source path for read repair implementation
  - A plausible cassandra.yaml config path or config key reference
  - A plausible test file path for read repair

Usage:
    python scripts/validate_cassandra_ripgrep_01.py --task cassandra-ripgrep-01
    python scripts/validate_cassandra_ripgrep_01.py --task cassandra-ripgrep-01 /path/to/artifacts

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
# Known-good path fragments that should appear in a correct answer.
# These are paths that exist in the cassandra-5.0.7 source tree and are
# directly related to read repair.
# ---------------------------------------------------------------------------

_SOURCE_HINTS = [
    "ReadRepair",
    "readrepair",
    "ReadRepairStrategy",
    "AbstractReadRepair",
    "BlockingReadRepair",
    "AsyncReadRepair",
]

_CONFIG_HINTS = [
    "cassandra.yaml",
    "read_repair",
    "ReadRepairStrategy",
]

_TEST_HINTS = [
    "ReadRepair",
    "readrepair",
    "Test",
    "test",
]

_TEST_PATH_HINTS = [
    "test/",
    "Test.java",
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
    parser = argparse.ArgumentParser(description="Validate cassandra-ripgrep-01 answer")
    parser.add_argument("--task", required=True, help="Task ID (must be cassandra-ripgrep-01)")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task != "cassandra-ripgrep-01":
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

    source_ok, source_detail = _check_field(answer_text, _SOURCE_HINTS, "source_path")
    config_ok, config_detail = _check_field(answer_text, _CONFIG_HINTS, "config_path")

    # Test path must satisfy both a test-name hint and a test-location hint.
    test_name_ok, test_name_detail = _check_field(answer_text, _TEST_HINTS, "test_path_name")
    test_loc_ok, test_loc_detail = _check_field(answer_text, _TEST_PATH_HINTS, "test_path_location")
    test_ok = test_name_ok and test_loc_ok
    test_detail = test_name_detail if not test_name_ok else test_loc_detail

    passed = [source_ok, config_ok, test_ok]
    details = {
        "source_path": source_detail,
        "config_path": config_detail,
        "test_path": test_detail,
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
