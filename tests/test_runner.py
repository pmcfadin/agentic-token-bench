"""Tests for benchmarks.harness.runner — BenchmarkRunner."""

from __future__ import annotations

import json
from pathlib import Path

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from benchmarks.harness.models import (
    CompletionContract,
    RunRecord,
    RunStatus,
    RunValidity,
    TaskManifest,
    TaskStep,
    ValidationStatus,
    Variant,
)
from benchmarks.harness.runner import BenchmarkRunner, _classify_validity, _generate_run_id


# ---------------------------------------------------------------------------
# Mock adapter
# ---------------------------------------------------------------------------


class MockAdapter(AgentAdapter):
    """Minimal AgentAdapter that returns canned StepResults."""

    version = "1.0.0-mock"

    def __init__(
        self,
        exit_status: int = 0,
        tool_invocations: list[dict] | None = None,
        reported_input: int = 50,
        reported_output: int = 100,
        reported_total: int = 150,
        raise_on_step: bool = False,
    ) -> None:
        self._exit_status = exit_status
        self._tool_invocations = tool_invocations or []
        self._reported_input = reported_input
        self._reported_output = reported_output
        self._reported_total = reported_total
        self._raise_on_step = raise_on_step

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
        if self._raise_on_step:
            raise RuntimeError("Simulated adapter failure")
        return StepResult(
            stdout="done",
            stderr="",
            exit_status=self._exit_status,
            step_metadata={"finish_reason": "stop"},
            trace_metadata={"tool_invocations": self._tool_invocations},
        )

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        return ReportedTokens(
            input_tokens=self._reported_input,
            output_tokens=self._reported_output,
            total_tokens=self._reported_total,
            evidence_snippet="mock evidence",
        )

    def normalize_final_status(self, step_result: StepResult) -> str:
        return "completed" if step_result.exit_status == 0 else "failed"


# ---------------------------------------------------------------------------
# Task manifest fixtures
# ---------------------------------------------------------------------------


def _make_task(
    task_id: str = "task-search-001",
    validation_commands: list[str] | None = None,
    steps: list[TaskStep] | None = None,
) -> TaskManifest:
    if steps is None:
        steps = [
            TaskStep(
                step_id="discover",
                name="Discover files",
                objective="Find relevant source files",
                required_tool="ripgrep",
                allowed_tools=["ripgrep"],
                blocked_tools=["fastmod"],
                completion_contract=CompletionContract(
                    kind="structured_answer", fields=["files"]
                ),
                artifact_requirements=["step_trace"],
            )
        ]
    return TaskManifest(
        task_id=task_id,
        title="Search benchmark task",
        family="search",
        repo="apache/cassandra",
        pinned_commit="deadbeef",
        objective="Search the codebase",
        task_description="Use ripgrep to search the codebase for a pattern.",
        success_criteria=["All files found"],
        validation_commands=validation_commands or [],
        steps=steps,
    )


# ---------------------------------------------------------------------------
# _generate_run_id
# ---------------------------------------------------------------------------


class TestGenerateRunId:
    def test_contains_task_id(self) -> None:
        from datetime import datetime, timezone

        ts = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        run_id = _generate_run_id("task-001", "baseline", ts)
        assert "task-001" in run_id

    def test_contains_variant(self) -> None:
        from datetime import datetime, timezone

        ts = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        run_id = _generate_run_id("task-001", "tool_variant", ts)
        assert "tool_variant" in run_id

    def test_contains_timestamp(self) -> None:
        from datetime import datetime, timezone

        ts = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        run_id = _generate_run_id("task-001", "baseline", ts)
        assert "20260331-120000" in run_id


# ---------------------------------------------------------------------------
# _classify_validity
# ---------------------------------------------------------------------------


class TestClassifyValidity:
    def test_valid_when_all_steps_ok_and_validation_passed(self) -> None:
        result = _classify_validity(True, ValidationStatus.passed)
        assert result == RunValidity.valid

    def test_valid_when_all_steps_ok_and_validation_skipped(self) -> None:
        result = _classify_validity(True, ValidationStatus.skipped)
        assert result == RunValidity.valid

    def test_invalid_when_step_enforcement_failed(self) -> None:
        result = _classify_validity(False, ValidationStatus.passed)
        assert result == RunValidity.invalid

    def test_invalid_when_validation_failed(self) -> None:
        result = _classify_validity(True, ValidationStatus.failed)
        assert result == RunValidity.invalid

    def test_invalid_when_both_failed(self) -> None:
        result = _classify_validity(False, ValidationStatus.failed)
        assert result == RunValidity.invalid


# ---------------------------------------------------------------------------
# BenchmarkRunner.run_task — basic behaviour
# ---------------------------------------------------------------------------


class TestRunTaskBasic:
    def test_returns_run_record(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        adapter = MockAdapter()
        task = _make_task()
        record = runner.run_task(task, adapter, "tool_variant", tmp_path)
        assert isinstance(record, RunRecord)

    def test_run_id_in_record(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        adapter = MockAdapter()
        task = _make_task(task_id="my-task")
        record = runner.run_task(task, adapter, "baseline", tmp_path)
        assert "my-task" in record.run_id
        assert "baseline" in record.run_id

    def test_task_id_matches(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(task_id="abc-123"), MockAdapter(), "baseline", tmp_path)
        assert record.task_id == "abc-123"

    def test_family_matches(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "tool_variant", tmp_path)
        assert record.family == "search"

    def test_variant_set_correctly_baseline(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        assert record.variant == Variant.baseline

    def test_variant_set_correctly_tool_variant(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "tool_variant", tmp_path)
        assert record.variant == Variant.tool_variant

    def test_repo_commit_set(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        assert record.repo_commit == "deadbeef"

    def test_agent_id_from_adapter_class_name(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        assert record.agent_id == "MockAdapter"

    def test_adapter_version_used(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        assert record.adapter_version == "1.0.0-mock"

    def test_elapsed_seconds_positive(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        assert record.elapsed_seconds is not None
        assert record.elapsed_seconds >= 0.0

    def test_started_at_and_finished_at_set(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        assert record.started_at is not None
        assert record.finished_at is not None
        assert record.finished_at >= record.started_at


# ---------------------------------------------------------------------------
# Artifact directory creation
# ---------------------------------------------------------------------------


class TestRunTaskArtifacts:
    def test_creates_artifact_directory(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        assert Path(record.artifact_dir).is_dir()

    def test_artifact_dir_under_results_dir(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        assert Path(record.artifact_dir).parent == tmp_path

    def test_run_json_written(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        run_json = Path(record.artifact_dir) / "run.json"
        assert run_json.exists()

    def test_run_json_valid_json(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        run_json = Path(record.artifact_dir) / "run.json"
        obj = json.loads(run_json.read_text(encoding="utf-8"))
        assert obj["run_id"] == record.run_id

    def test_prompt_txt_written(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        prompt_file = Path(record.artifact_dir) / "prompt.txt"
        assert prompt_file.exists()

    def test_trace_jsonl_written(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(), "baseline", tmp_path)
        trace = Path(record.artifact_dir) / "trace.jsonl"
        assert trace.exists()
        assert trace.stat().st_size > 0


# ---------------------------------------------------------------------------
# Token extraction
# ---------------------------------------------------------------------------


class TestRunTaskTokens:
    def test_reported_tokens_populated(self, tmp_path: Path) -> None:
        adapter = MockAdapter(reported_input=10, reported_output=20, reported_total=30)
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), adapter, "baseline", tmp_path)
        assert record.reported_input_tokens == 10
        assert record.reported_output_tokens == 20
        assert record.reported_total_tokens == 30


# ---------------------------------------------------------------------------
# Status and validity classification
# ---------------------------------------------------------------------------


class TestRunTaskStatus:
    def test_status_passed_on_success(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(exit_status=0), "baseline", tmp_path)
        assert record.status == RunStatus.passed

    def test_status_failed_on_nonzero_exit(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(exit_status=1), "baseline", tmp_path)
        assert record.status == RunStatus.failed

    def test_status_error_on_adapter_exception(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(
            _make_task(), MockAdapter(raise_on_step=True), "baseline", tmp_path
        )
        assert record.status == RunStatus.error

    def test_validity_invalid_on_adapter_exception(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(
            _make_task(), MockAdapter(raise_on_step=True), "baseline", tmp_path
        )
        assert record.validity == RunValidity.invalid

    def test_valid_run_is_valid(self, tmp_path: Path) -> None:
        # Baseline run: required_tool not enforced, so enforcement always passes.
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(_make_task(), MockAdapter(exit_status=0), "baseline", tmp_path)
        assert record.validity == RunValidity.valid

    def test_invalid_when_required_tool_not_used_in_tool_variant(self, tmp_path: Path) -> None:
        # tool_variant requires ripgrep but mock returns no invocations.
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(
            _make_task(),
            MockAdapter(exit_status=0, tool_invocations=[]),
            "tool_variant",
            tmp_path,
        )
        # Required tool 'ripgrep' was not used → enforcement fails → invalid.
        assert record.validity == RunValidity.invalid

    def test_valid_when_required_tool_used_in_tool_variant(self, tmp_path: Path) -> None:
        runner = BenchmarkRunner(results_dir=tmp_path)
        invocations = [{"tool_id": "ripgrep", "exit_status": 0}]
        record = runner.run_task(
            _make_task(),
            MockAdapter(exit_status=0, tool_invocations=invocations),
            "tool_variant",
            tmp_path,
        )
        assert record.validity == RunValidity.valid

    def test_validation_status_skipped_when_no_commands(self, tmp_path: Path) -> None:
        task = _make_task(validation_commands=[])
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(task, MockAdapter(), "baseline", tmp_path)
        assert record.validation_status == ValidationStatus.skipped


# ---------------------------------------------------------------------------
# Multi-step task
# ---------------------------------------------------------------------------


class TestRunTaskMultiStep:
    def test_multi_step_task_completes(self, tmp_path: Path) -> None:
        steps = [
            TaskStep(
                step_id="step1",
                name="Step 1",
                objective="First step",
                required_tool=None,
                allowed_tools=[],
                blocked_tools=[],
                completion_contract=CompletionContract(kind="free_text", fields=[]),
            ),
            TaskStep(
                step_id="step2",
                name="Step 2",
                objective="Second step",
                required_tool=None,
                allowed_tools=[],
                blocked_tools=[],
                completion_contract=CompletionContract(kind="free_text", fields=[]),
            ),
        ]
        task = _make_task(steps=steps)
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(task, MockAdapter(), "baseline", tmp_path)
        assert isinstance(record, RunRecord)
        assert record.status == RunStatus.passed

    def test_multi_step_trace_has_events_for_each_step(self, tmp_path: Path) -> None:
        steps = [
            TaskStep(
                step_id="s1",
                name="S1",
                objective="obj",
                required_tool=None,
                allowed_tools=[],
                blocked_tools=[],
                completion_contract=CompletionContract(kind="free_text", fields=[]),
            ),
            TaskStep(
                step_id="s2",
                name="S2",
                objective="obj",
                required_tool=None,
                allowed_tools=[],
                blocked_tools=[],
                completion_contract=CompletionContract(kind="free_text", fields=[]),
            ),
        ]
        task = _make_task(steps=steps)
        runner = BenchmarkRunner(results_dir=tmp_path)
        record = runner.run_task(task, MockAdapter(), "baseline", tmp_path)

        trace = Path(record.artifact_dir) / "trace.jsonl"
        lines = [ln for ln in trace.read_text(encoding="utf-8").splitlines() if ln.strip()]
        # Each step has step_started + step_finished events, plus run_finished.
        assert len(lines) >= 5  # 2 started + 2 finished + 1 run_finished
