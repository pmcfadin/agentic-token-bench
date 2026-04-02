"""Validation script for the Cassandra v2 ripgrep tasks.

The v2 ripgrep tasks are exact-set retrieval tasks.  Validation checks that the
final answer returns the required path set for each task and does not invent
absolute paths.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


_TASKS: dict[str, dict[str, object]] = {
    "cassandra-ripgrep-01-v2": {
        "paths": {
            "src/java/org/apache/cassandra/service/ReadRepair.java",
            "conf/cassandra.yaml",
            "test/unit/org/apache/cassandra/service/ReadRepairTest.java",
        },
        "required_text": ["read_repair_chance"],
    },
    "cassandra-ripgrep-02-v2": {
        "paths": {
            "src/java/org/apache/cassandra/db/compaction/SizeTieredCompactionStrategy.java",
            "src/java/org/apache/cassandra/db/compaction/SizeTieredCompactionStrategyOptions.java",
            "src/java/org/apache/cassandra/db/compaction/CompactionManager.java",
            "src/java/org/apache/cassandra/schema/TableParams.java",
            "test/unit/org/apache/cassandra/db/compaction/SizeTieredCompactionStrategyTest.java",
            "src/java/org/apache/cassandra/cql3/statements/schema/AlterTableStatement.java",
        },
        "required_text": ["SizeTieredCompactionStrategy"],
    },
}

_PATH_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:java|yaml|yml|xml|cql)")
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


def _extract_paths(answer_text: str) -> set[str]:
    return {match.strip("`\"'(),.- ").lower() for match in _PATH_RE.findall(answer_text)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Cassandra v2 ripgrep answers")
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
    expected_paths = {path.lower() for path in _TASKS[args.task]["paths"]}  # type: ignore[arg-type]
    required_text = [text.lower() for text in _TASKS[args.task]["required_text"]]  # type: ignore[arg-type]

    extracted_paths = _extract_paths(answer_text)
    missing_paths = sorted(expected_paths - extracted_paths)
    extra_paths = sorted(extracted_paths - expected_paths)
    missing_text = [text for text in required_text if text not in lower]

    details = {
        "expected_paths": sorted(expected_paths),
        "extracted_paths": sorted(extracted_paths),
        "missing_paths": missing_paths,
        "extra_paths": extra_paths,
        "missing_text": missing_text,
        "disallowed_prefixes": disallowed,
        "source": source_label,
    }

    if disallowed or extra_paths:
        print(json.dumps({"status": "fail", "details": details}))
        sys.exit(1)

    if not missing_paths and not missing_text:
        print(json.dumps({"status": "pass", "details": details}))
        sys.exit(0)

    if extracted_paths or missing_text:
        print(json.dumps({"status": "partial", "details": details}))
        sys.exit(2)

    print(json.dumps({"status": "fail", "details": details}))
    sys.exit(1)


if __name__ == "__main__":
    main()
