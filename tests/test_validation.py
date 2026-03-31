"""Tests for benchmarks.harness.validation."""

from pathlib import Path

import pytest

from benchmarks.harness.models import ValidationStatus
from benchmarks.harness.validation import ValidationResult, run_all_validations, run_validation_command


@pytest.fixture()
def tmp_cwd(tmp_path: Path) -> Path:
    return tmp_path


class TestRunValidationCommand:
    def test_passing_command_returns_passed_status(self, tmp_cwd: Path) -> None:
        result = run_validation_command("echo ok", cwd=tmp_cwd)

        assert isinstance(result, ValidationResult)
        assert result.status == ValidationStatus.passed
        assert result.exit_code == 0
        assert "ok" in result.stdout
        assert result.command == "echo ok"
        assert result.duration_seconds >= 0.0

    def test_failing_command_returns_failed_status(self, tmp_cwd: Path) -> None:
        result = run_validation_command("false", cwd=tmp_cwd)

        assert result.status == ValidationStatus.failed
        assert result.exit_code != 0
        assert result.command == "false"

    def test_failing_command_nonzero_exit_code(self, tmp_cwd: Path) -> None:
        # Use a command that exits with a known non-zero code
        result = run_validation_command("sh -c 'exit 2'", cwd=tmp_cwd)

        assert result.status == ValidationStatus.failed
        assert result.exit_code == 2

    def test_stdout_and_stderr_captured(self, tmp_cwd: Path) -> None:
        result = run_validation_command(
            "sh -c 'echo out; echo err >&2'", cwd=tmp_cwd
        )

        assert "out" in result.stdout
        assert "err" in result.stderr

    def test_timeout_returns_failed_status(self, tmp_cwd: Path) -> None:
        result = run_validation_command("sleep 10", cwd=tmp_cwd, timeout=0.1)

        assert result.status == ValidationStatus.failed
        assert result.exit_code == -1
        assert result.duration_seconds >= 0.0

    def test_timeout_result_has_correct_command(self, tmp_cwd: Path) -> None:
        result = run_validation_command("sleep 10", cwd=tmp_cwd, timeout=0.1)

        assert result.command == "sleep 10"

    def test_duration_is_positive(self, tmp_cwd: Path) -> None:
        result = run_validation_command("echo hi", cwd=tmp_cwd)

        assert result.duration_seconds >= 0.0


class TestRunAllValidations:
    def test_returns_one_result_per_command(self, tmp_cwd: Path) -> None:
        commands = ["echo a", "echo b", "echo c"]
        results = run_all_validations(commands, cwd=tmp_cwd)

        assert len(results) == 3

    def test_mixed_results(self, tmp_cwd: Path) -> None:
        commands = ["echo ok", "false", "echo also_ok"]
        results = run_all_validations(commands, cwd=tmp_cwd)

        assert results[0].status == ValidationStatus.passed
        assert results[1].status == ValidationStatus.failed
        assert results[2].status == ValidationStatus.passed

    def test_empty_command_list_returns_empty(self, tmp_cwd: Path) -> None:
        results = run_all_validations([], cwd=tmp_cwd)

        assert results == []

    def test_results_preserve_command_order(self, tmp_cwd: Path) -> None:
        commands = ["echo first", "echo second"]
        results = run_all_validations(commands, cwd=tmp_cwd)

        assert results[0].command == "echo first"
        assert results[1].command == "echo second"

    def test_all_commands_run_even_after_failure(self, tmp_cwd: Path) -> None:
        # Ensure we do not short-circuit on failure
        commands = ["false", "echo still_ran"]
        results = run_all_validations(commands, cwd=tmp_cwd)

        assert len(results) == 2
        assert results[1].status == ValidationStatus.passed
        assert "still_ran" in results[1].stdout
