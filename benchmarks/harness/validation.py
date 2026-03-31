"""benchmarks.harness.validation — execution of validation commands and normalization of results.

See docs/plans/2026-03-31-v1-build-plan-design.md for module responsibilities.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from benchmarks.harness.models import ValidationStatus


@dataclass
class ValidationResult:
    """Result of a single validation command execution."""

    status: ValidationStatus
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float


def run_validation_command(
    command: str,
    cwd: Path,
    timeout: float = 120.0,
) -> ValidationResult:
    """Execute a validation command and return a normalized result.

    Args:
        command: Shell command string to execute.
        cwd: Working directory in which to run the command.
        timeout: Maximum seconds to wait before treating the run as failed.

    Returns:
        ValidationResult with status mapped from exit code (0 → passed, non-zero → failed)
        or status set to failed on timeout.
    """
    start = time.monotonic()
    try:
        completed = subprocess.run(
            shlex.split(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = time.monotonic() - start
        status = ValidationStatus.passed if completed.returncode == 0 else ValidationStatus.failed
        return ValidationResult(
            status=status,
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        return ValidationResult(
            status=ValidationStatus.failed,
            command=command,
            stdout=exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            exit_code=-1,
            duration_seconds=duration,
        )


def run_all_validations(
    commands: list[str],
    cwd: Path,
) -> list[ValidationResult]:
    """Run each validation command in sequence and return all results.

    Args:
        commands: Ordered list of shell command strings to execute.
        cwd: Working directory for every command.

    Returns:
        List of ValidationResult, one per command, in the same order.
    """
    return [run_validation_command(command, cwd) for command in commands]
