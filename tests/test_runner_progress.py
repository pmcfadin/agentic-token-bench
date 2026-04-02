"""Tests for benchmark runner progress logging."""

from __future__ import annotations

from pathlib import Path

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from benchmarks.harness.models import (
    CompletionContract,
    TaskManifest,
    TaskStep,
)
from benchmarks.harness.models import ValidationStatus
from benchmarks.harness.runner import BenchmarkRunner, _classify_validity


class _FakeAdapter(AgentAdapter):
    def probe(self) -> QualificationResult:
        return QualificationResult(
            qualified=True,
            reported_token_support=True,
            forced_tool_support=True,
            trace_support=True,
            run_completion_support=True,
        )

    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        return StepResult(
            stdout='{"result":"done"}',
            stderr="",
            exit_status=0,
            step_metadata={"status": "success", "timeout": False},
            trace_metadata={"tool_invocations": []},
        )

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        return ReportedTokens(
            input_tokens=1,
            output_tokens=2,
            total_tokens=3,
            evidence_snippet="total_tokens=3",
        )

    def normalize_final_status(self, step_result: StepResult) -> str:
        return "completed"


def test_run_task_emits_progress_messages(tmp_path: Path) -> None:
    task = TaskManifest(
        task_id="sample-task-01",
        title="Sample task",
        family="sample",
        repo="cassandra",
        pinned_commit="abc123",
        objective="Do a sample thing.",
        task_description="A simple task used for logging coverage.",
        success_criteria=["Writes a result"],
        validation_commands=[],
        steps=[
            TaskStep(
                step_id="discover",
                name="discover",
                objective="Find the thing.",
                required_tool=None,
                allowed_tools=[],
                blocked_tools=[],
                completion_contract=CompletionContract(
                    kind="structured_answer",
                    fields=["answer"],
                ),
                artifact_requirements=["final_answer"],
            )
        ],
    )

    runner = BenchmarkRunner(results_dir=tmp_path / "results")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    messages: list[str] = []

    record = runner.run_task(
        task=task,
        adapter=_FakeAdapter(),
        variant="tool_variant",
        workspace=workspace,
        progress=messages.append,
    )

    assert record.status.value == "passed"
    assert record.validity.value == "valid"
    assert any(msg.startswith("run-task: starting sample-task-01 [tool_variant]") for msg in messages)
    assert any(msg.startswith("step 1/1: discover") for msg in messages)
    assert any("step discover: invoking _FakeAdapter" in msg for msg in messages)
    assert any("run-task: no validation commands defined" in msg for msg in messages)
    assert any("run-task: finished status=passed validity=valid tokens=3" in msg for msg in messages)


# ---------------------------------------------------------------------------
# _classify_validity unit tests
# ---------------------------------------------------------------------------


def test_classify_validity_valid_tokens_passed() -> None:
    """validation=passed with positive tokens → valid."""
    result = _classify_validity(True, ValidationStatus.passed, 1000)
    assert result.value == "valid"


def test_classify_validity_zero_tokens_is_invalid() -> None:
    """validation=passed but tokens=0 → invalid (token reporting required)."""
    result = _classify_validity(True, ValidationStatus.passed, 0)
    assert result.value == "invalid"


def test_classify_validity_none_tokens_is_invalid() -> None:
    """validation=passed but tokens=None → invalid (token reporting required)."""
    result = _classify_validity(True, ValidationStatus.passed, None)
    assert result.value == "invalid"


def test_classify_validity_failed_validation_is_invalid() -> None:
    """validation=failed → invalid even with positive tokens."""
    result = _classify_validity(True, ValidationStatus.failed, 500)
    assert result.value == "invalid"


def test_classify_validity_skipped_validation_with_tokens() -> None:
    """validation=skipped with positive tokens → valid."""
    result = _classify_validity(True, ValidationStatus.skipped, 200)
    assert result.value == "valid"


def test_classify_validity_skipped_validation_zero_tokens() -> None:
    """validation=skipped but tokens=0 → invalid."""
    result = _classify_validity(True, ValidationStatus.skipped, 0)
    assert result.value == "invalid"
