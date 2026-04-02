"""Tests for benchmark runner progress logging."""

from __future__ import annotations

from pathlib import Path

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from benchmarks.harness.models import (
    CompletionContract,
    TaskManifest,
    TaskStep,
)
from benchmarks.harness.runner import BenchmarkRunner


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
