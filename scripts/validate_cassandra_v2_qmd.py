"""Validation script for the Cassandra v2 qmd tasks.

The v2 qmd tasks are deterministic retrieval tasks.  Validation checks that the
final answer includes the expected source path, exact line range, and the key
passage anchors from the fixture text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


_TASKS: dict[str, dict[str, object]] = {
    "cassandra-qmd-01-v2": {
        "source": "Gossiper.java",
        "line_range": "361-384",
        "required": [
            "gossip to some random live member",
            "gossip to some unreachable member",
            "maybeGossipToSeed",
            "liveEndpoints.size() < seeds.size()",
        ],
    },
    "cassandra-qmd-02-v2": {
        "source": "cassandra.yaml",
        "line_range": "1244-1251",
        "required": [
            "throttles compaction",
            "compaction_throughput: 64mib/s",
            "0 disables throttling",
        ],
    },
}

_DISALLOWED_PREFIXES = ("/Users/", "/home/", "C:\\")


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


def _check_required(answer_text: str, required: list[str]) -> list[str]:
    lower = answer_text.lower()
    return [item for item in required if item.lower() not in lower]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Cassandra v2 qmd answers")
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
    lower = answer_text.lower()

    disallowed = [prefix for prefix in _DISALLOWED_PREFIXES if prefix in answer_text]
    source = str(_TASKS[args.task]["source"])
    line_range = str(_TASKS[args.task]["line_range"])
    required = list(_TASKS[args.task]["required"])  # type: ignore[arg-type]
    missing = _check_required(answer_text, required)

    source_ok = source.lower() in lower
    line_ok = line_range in answer_text

    details = {
        "source_ok": source_ok,
        "line_range_ok": line_ok,
        "missing": missing,
        "disallowed_prefixes": disallowed,
        "source": source_label,
    }

    if disallowed:
        print(json.dumps({"status": "fail", "details": details}))
        sys.exit(1)

    if source_ok and line_ok and not missing:
        print(json.dumps({"status": "pass", "details": details}))
        sys.exit(0)

    if source_ok or line_ok or len(missing) < len(required):
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)

    print(json.dumps({"status": "fail", "details": details}))
    sys.exit(1)


if __name__ == "__main__":
    main()
