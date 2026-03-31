#!/usr/bin/env python3
"""Run qualification probes for all three agent adapters.

Writes qualification records as JSON to benchmarks/qualification/{agent_id}.json
and prints a summary table showing which agents qualified.

Usage:
    uv run python scripts/run_qualification.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent
_QUAL_DIR = _REPO_ROOT / "benchmarks" / "qualification"

_ADAPTER_VERSION = "0.1.0"


def _write_record(agent_id: str, record_dict: dict) -> Path:
    """Write a qualification record dict to disk.

    Args:
        agent_id: Identifier for the agent (used as filename).
        record_dict: Serialisable qualification record.

    Returns:
        Path to the written file.
    """
    _QUAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _QUAL_DIR / f"{agent_id}.json"
    out_path.write_text(json.dumps(record_dict, indent=2))
    return out_path


def _qualify_agent(agent_id: str) -> dict:
    """Instantiate the adapter for *agent_id*, run qualification, and return the record dict.

    If the adapter's CLI is not installed (FileNotFoundError or a probe that
    indicates the binary is missing) the function returns a not_qualified record
    with a descriptive failure_reason.

    Args:
        agent_id: One of "claude", "codex", or "gemini-cli".

    Returns:
        Dict representation of a QualificationRecord.
    """
    from benchmarks.harness.qualification import run_qualification

    try:
        if agent_id == "claude":
            from agents.claude.adapter import ClaudeAdapter

            adapter = ClaudeAdapter()
        elif agent_id == "codex":
            from agents.codex.adapter import CodexAdapter

            adapter = CodexAdapter()
        elif agent_id == "gemini-cli":
            from agents.gemini_cli.adapter import GeminiCliAdapter

            adapter = GeminiCliAdapter()
        else:
            return {
                "agent_id": agent_id,
                "adapter_version": _ADAPTER_VERSION,
                "qualified": False,
                "reported_token_support": False,
                "forced_tool_support": False,
                "trace_support": False,
                "run_completion_support": False,
                "failure_reason": f"Unknown agent id: {agent_id!r}",
                "evidence_paths": [],
            }
    except ImportError as exc:
        return {
            "agent_id": agent_id,
            "adapter_version": _ADAPTER_VERSION,
            "qualified": False,
            "reported_token_support": False,
            "forced_tool_support": False,
            "trace_support": False,
            "run_completion_support": False,
            "failure_reason": f"Could not import adapter for {agent_id!r}: {exc}",
            "evidence_paths": [],
        }

    try:
        record = run_qualification(
            adapter=adapter,
            agent_id=agent_id,
            adapter_version=_ADAPTER_VERSION,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "agent_id": agent_id,
            "adapter_version": _ADAPTER_VERSION,
            "qualified": False,
            "reported_token_support": False,
            "forced_tool_support": False,
            "trace_support": False,
            "run_completion_support": False,
            "failure_reason": f"run_qualification raised an exception: {exc}",
            "evidence_paths": [],
        }

    return record.model_dump()


def _print_summary(results: list[dict]) -> None:
    """Print a plain-text summary table to stdout.

    Args:
        results: List of qualification record dicts.
    """
    col_agent = 14
    col_status = 10
    col_reason = 50

    header = (
        f"{'Agent':<{col_agent}} {'Status':<{col_status}} {'Failure reason':<{col_reason}}"
    )
    separator = "-" * len(header)
    print(separator)
    print(header)
    print(separator)

    all_qualified = True
    for r in results:
        status = "QUALIFIED" if r.get("qualified") else "NOT QUALIFIED"
        if not r.get("qualified"):
            all_qualified = False
        reason = r.get("failure_reason") or ""
        if len(reason) > col_reason:
            reason = reason[: col_reason - 3] + "..."
        print(f"{r['agent_id']:<{col_agent}} {status:<{col_status}} {reason:<{col_reason}}")

    print(separator)
    print(f"\nResult: {'all agents qualified' if all_qualified else 'one or more agents did not qualify'}")


def main() -> int:
    """Run qualification for all three agents and write results.

    Returns:
        Exit code: 0 if all agents qualified, 1 otherwise.
    """
    agent_ids = ["claude", "codex", "gemini-cli"]
    results: list[dict] = []

    for agent_id in agent_ids:
        print(f"Running qualification for {agent_id!r} ...", end=" ", flush=True)
        record_dict = _qualify_agent(agent_id)
        out_path = _write_record(agent_id, record_dict)
        status = "ok" if record_dict.get("qualified") else "FAILED"
        print(f"{status}  →  {out_path}")
        results.append(record_dict)

    print()
    _print_summary(results)

    return 0 if all(r.get("qualified") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
