"""Validation script for cassandra-qmd-01.

Checks that the agent's final answer addresses:
  - The gossip peer selection process in Cassandra
  - Key gossip protocol concepts and classes

Usage:
    python scripts/validate_cassandra_qmd_01.py --task cassandra-qmd-01
    python scripts/validate_cassandra_qmd_01.py --task cassandra-qmd-01 /path/to/artifacts

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
# Known-good hints that should appear in a correct answer.
# These relate to gossip peer selection and the gossip round mechanics in the
# Cassandra 5.0.x source tree.
# ---------------------------------------------------------------------------

_GOSSIP_CLASS_HINTS = [
    "Gossiper",
    "GossipDigestSyn",
    "GossipDigestAck",
]

_GOSSIP_CONCEPT_HINTS = [
    "gossip",
    "FailureDetector",
    "endpoint",
]

_PEER_SELECTION_HINTS = [
    "live",
    "seed",
    "unreachable",
    "fanout",
    "round",
    "max",
    "3",
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
    parser = argparse.ArgumentParser(description="Validate cassandra-qmd-01 answer")
    parser.add_argument("--task", required=True, help="Task ID (must be cassandra-qmd-01)")
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Path to artifact directory (overrides ATB_ARTIFACT_DIR env var)",
    )
    args = parser.parse_args()

    if args.task != "cassandra-qmd-01":
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

    gossip_class_ok, gossip_class_detail = _check_field(
        answer_text, _GOSSIP_CLASS_HINTS, "gossip_class"
    )
    gossip_concept_ok, gossip_concept_detail = _check_field(
        answer_text, _GOSSIP_CONCEPT_HINTS, "gossip_concept"
    )
    peer_selection_ok, peer_selection_detail = _check_field(
        answer_text, _PEER_SELECTION_HINTS, "peer_selection"
    )

    passed = [gossip_class_ok, gossip_concept_ok, peer_selection_ok]
    details = {
        "gossip_class": gossip_class_detail,
        "gossip_concept": gossip_concept_detail,
        "peer_selection": peer_selection_detail,
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
