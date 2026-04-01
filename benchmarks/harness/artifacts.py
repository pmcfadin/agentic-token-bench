"""benchmarks.harness.artifacts — artifact directory creation and file writing.

See docs/plans/2026-03-31-v1-build-plan-design.md for responsibilities.
"""

from __future__ import annotations

__all__ = [
    "create_artifact_dir",
    "write_run_record",
    "write_prompt",
    "write_diff",
    "write_final_answer",
]

from pathlib import Path

from benchmarks.harness.models import RunRecord


def create_artifact_dir(results_dir: Path, run_id: str) -> Path:
    """Create and return the artifact directory for a run.

    The directory is created at ``results_dir / run_id``.  Parent directories
    are created automatically if they do not exist.

    Args:
        results_dir: Root directory where all run artifacts are stored.
        run_id: Unique identifier for this run, used as the subdirectory name.

    Returns:
        Path to the newly created artifact directory.
    """
    artifact_dir = results_dir / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def write_run_record(artifact_dir: Path, record: RunRecord) -> Path:
    """Serialize a RunRecord to ``run.json`` inside *artifact_dir*.

    Args:
        artifact_dir: Directory in which to write ``run.json``.
        record: The :class:`RunRecord` to serialize.

    Returns:
        Path to the written ``run.json`` file.
    """
    run_json = artifact_dir / "run.json"
    run_json.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return run_json


def write_prompt(artifact_dir: Path, prompt: str) -> Path:
    """Write the rendered prompt to ``prompt.txt`` inside *artifact_dir*.

    Args:
        artifact_dir: Directory in which to write ``prompt.txt``.
        prompt: The fully rendered prompt string for the run.

    Returns:
        Path to the written ``prompt.txt`` file.
    """
    prompt_file = artifact_dir / "prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    return prompt_file


def write_diff(artifact_dir: Path, diff: str) -> Path:
    """Write a diff to ``diff.patch`` inside *artifact_dir*.

    Args:
        artifact_dir: Directory in which to write ``diff.patch``.
        diff: Unified diff string to write.

    Returns:
        Path to the written ``diff.patch`` file.
    """
    diff_file = artifact_dir / "diff.patch"
    diff_file.write_text(diff, encoding="utf-8")
    return diff_file


def write_final_answer(artifact_dir: Path, content: str) -> Path:
    """Write the agent's final answer to ``final_answer.txt`` inside *artifact_dir*.

    Args:
        artifact_dir: Directory in which to write ``final_answer.txt``.
        content: The agent's final answer text.

    Returns:
        Path to the written ``final_answer.txt`` file.
    """
    path = artifact_dir / "final_answer.txt"
    path.write_text(content, encoding="utf-8")
    return path
