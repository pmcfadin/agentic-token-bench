"""Validation script for the Cassandra v2 fastmod tasks.

Checks that the unified diff output produced by the harness diff-capture
contains the expected renamed identifiers as added lines and confirms
the old identifiers do not appear as new additions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


_TASKS: dict[str, dict[str, list[str]]] = {
    "cassandra-fastmod-01-v2": {
        "required": [
            "+read_repair_probability",
        ],
        "omit": [
            "+read_repair_chance",
        ],
    },
    "cassandra-fastmod-02-v2": {
        "required": [
            "+            if (bucket.size() >= sizeTieredOptions.minCompactionThreshold)",
        ],
        "omit": [
            "+            if (bucket.size() >= sizeTieredOptions.minThreshold)",
        ],
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
    missing = [item for item in required if item not in answer_text]
    return len(missing) == 0, missing


def _check_omit(answer_text: str, omit: list[str]) -> tuple[bool, list[str]]:
    violations = [item for item in omit if item in answer_text]
    return len(violations) == 0, violations


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Cassandra v2 fastmod answers")
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
    omit = _TASKS[args.task].get("omit", [])

    ok_required, missing = _check_required(answer_text, required)
    ok_omit, violations = _check_omit(answer_text, omit)

    details = {
        "required": required,
        "missing": missing,
        "omit": omit,
        "violations": violations,
        "source": source_label,
    }

    if ok_required and ok_omit:
        print(json.dumps({"status": "pass", "details": details}))
        sys.exit(0)

    if (missing and len(missing) < len(required)) or (not ok_omit and ok_required):
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)

    print(json.dumps({"status": "fail", "details": details}))
    sys.exit(1)


if __name__ == "__main__":
    main()
