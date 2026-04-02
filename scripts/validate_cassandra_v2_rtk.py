"""Validation script for the Cassandra v2 rtk tasks.

This validator checks for the exact failure anchors that the deterministic-first
v2 rtk tasks are designed to preserve.  It is strict about the expected
source/test identifiers and the failure text, but still emits the familiar
pass/partial/fail JSON contract used by the rest of the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


_TASKS: dict[str, dict[str, list[str]]] = {
    "cassandra-rtk-01-v2": {
        "required": [
            "DatabaseDescriptor.java",
            "847",
            "cannot find symbol",
            "compaction_throughput_mb_per_sec",
        ]
    },
    "cassandra-rtk-02-v2": {
        "required": [
            "CompactionManagerTest",
            "testSetCompactionThroughput",
            "AssertionFailedError",
            "expected:<64> but was:<0>",
        ]
    },
}


def _resolve_text_source(artifact_dir: Path) -> tuple[str, str]:
    candidate_envs = (
        ("ATB_REDUCED_ANSWER", "reduced_answer"),
        ("ATB_RAW_ANSWER", "raw_answer"),
        ("ATB_REDUCED_ARTIFACT", "reduced_artifact"),
        ("ATB_RAW_ARTIFACT", "raw_artifact"),
    )
    for env_name, label in candidate_envs:
        raw = os.environ.get(env_name)
        if raw:
            path = Path(raw)
            if path.exists():
                return path.read_text(encoding="utf-8"), label

    for candidate, label in (
        (artifact_dir / "reduced_output.txt", "reduced_output"),
        (artifact_dir / "final_answer.txt", "final_answer"),
    ):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8"), label

    print(
        json.dumps(
            {
                "status": "fail",
                "details": {
                    "error": f"no readable artifact found in {artifact_dir}"
                },
            }
        )
    )
    sys.exit(1)


def _check_required(answer_text: str, required: list[str]) -> tuple[bool, list[str]]:
    lower = answer_text.lower()
    missing = [item for item in required if item.lower() not in lower]
    return len(missing) == 0, missing


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Cassandra v2 rtk answers")
    parser.add_argument("--task", required=True, help="Task ID")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task not in _TASKS:
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
    answer_text, source_label = _resolve_text_source(artifact_dir)

    required = _TASKS[args.task]["required"]
    ok, missing = _check_required(answer_text, required)
    details = {"required": required, "missing": missing, "source": source_label}

    if ok:
        print(json.dumps({"status": "pass", "details": details}))
        sys.exit(0)

    if missing and len(missing) < len(required):
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)

    print(json.dumps({"status": "fail", "details": details}))
    sys.exit(1)


if __name__ == "__main__":
    main()
