"""benchmarks.harness.runner — top-level benchmark run orchestration.

See docs/plans/2026-03-31-v1-build-plan-design.md for module responsibilities.
"""

from __future__ import annotations

__all__ = ["BenchmarkRunner"]

import logging
from datetime import datetime, timezone
from pathlib import Path

from agents.base import AgentAdapter
from benchmarks.harness.artifacts import (
    create_artifact_dir,
    write_prompt,
    write_run_record,
)
from benchmarks.harness.models import (
    EventRecord,
    RunRecord,
    RunStatus,
    RunValidity,
    TaskManifest,
    ValidationStatus,
    Variant,
)
from benchmarks.harness.prompts import render_step_prompt
from benchmarks.harness.step_executor import StepExecutor
from benchmarks.harness.tracing import EventWriter, InvocationWriter
from benchmarks.harness.validation import run_all_validations

logger = logging.getLogger(__name__)


def _generate_run_id(task_id: str, variant: str, started_at: datetime) -> str:
    """Produce a deterministic run identifier from task, variant, and timestamp.

    Format: ``<task_id>__<variant>__<YYYYMMDD-HHMMSS>``.
    """
    ts = started_at.strftime("%Y%m%d-%H%M%S")
    return f"{task_id}__{variant}__{ts}"


def _classify_validity(
    all_steps_valid: bool,
    validation_status: ValidationStatus,
) -> RunValidity:
    """Return RunValidity based on step enforcement and validation results."""
    if all_steps_valid and validation_status != ValidationStatus.failed:
        return RunValidity.valid
    return RunValidity.invalid


class BenchmarkRunner:
    """Orchestrates end-to-end benchmark runs for a single task.

    Args:
        results_dir: Root directory where artifact subdirectories are written.
            Defaults to ``benchmarks/results`` relative to the working directory.
    """

    def __init__(self, results_dir: Path = Path("benchmarks/results")) -> None:
        self._results_dir = results_dir

    def run_task(
        self,
        task: TaskManifest,
        adapter: AgentAdapter,
        variant: str,
        workspace: Path,
        tool_wrappers: dict[str, Path] | None = None,
    ) -> RunRecord:
        """Execute all steps in *task* and return a populated RunRecord.

        Args:
            task: The :class:`TaskManifest` describing the benchmark task.
            adapter: An :class:`AgentAdapter` that can execute steps.
            variant: Either ``"baseline"`` or ``"tool_variant"``.
            workspace: Path to the isolated workspace directory.
            tool_wrappers: Optional mapping of tool name to wrapper binary/dir.
                Pass ``None`` when no tool wrappers are needed (e.g. baseline
                runs that never expose any wrappers).

        Returns:
            A fully populated :class:`RunRecord` with status, validity, and
            artifact paths set.
        """
        started_at = datetime.now(tz=timezone.utc)
        run_id = _generate_run_id(task.task_id, variant, started_at)

        # --- artifact directory ---
        artifact_dir = create_artifact_dir(self._results_dir, run_id)

        # --- tracing writers ---
        event_writer = EventWriter(artifact_dir / "trace.jsonl")
        # InvocationWriter is created but invocations are delivered through
        # the adapter's trace_metadata; the writer is available for subclasses
        # or future use.
        _invocation_writer = InvocationWriter(artifact_dir / "invocations.jsonl")

        # --- step executor ---
        wrappers: dict[str, Path] = tool_wrappers or {}
        executor = StepExecutor(wrappers)

        # Accumulated state across steps.
        all_steps_enforcement_valid = True
        last_step_result = None
        run_status = RunStatus.passed

        for step_index, step in enumerate(task.steps):
            # Write step_started event.
            event_writer.write_event(
                EventRecord(
                    timestamp=datetime.now(tz=timezone.utc),
                    run_id=run_id,
                    step_id=step.step_id,
                    event_type="step_started",
                    actor="harness",
                    payload={"step_index": step_index, "step_name": step.name},
                )
            )

            # Build step environment.
            step_env = executor.prepare_step(step, variant)

            # Render prompt using canonical prompts module.
            prompt = render_step_prompt(task, step, variant)
            write_prompt(artifact_dir, prompt)

            # Execute step via the adapter.
            try:
                step_result = adapter.run_step(
                    prompt=prompt,
                    step_env=step_env,
                    workspace=workspace,
                    timeout=300.0,
                )
                last_step_result = step_result
            except Exception as exc:  # noqa: BLE001
                logger.exception("Adapter raised during step %s", step.step_id)
                event_writer.write_event(
                    EventRecord(
                        timestamp=datetime.now(tz=timezone.utc),
                        run_id=run_id,
                        step_id=step.step_id,
                        event_type="step_error",
                        actor="harness",
                        payload={"error": str(exc)},
                    )
                )
                finished_at = datetime.now(tz=timezone.utc)
                elapsed = (finished_at - started_at).total_seconds()
                record = RunRecord(
                    run_id=run_id,
                    task_id=task.task_id,
                    family=task.family,
                    variant=Variant(variant),
                    agent_id=type(adapter).__name__,
                    adapter_version=getattr(adapter, "version", "unknown"),
                    repo_commit=task.pinned_commit,
                    status=RunStatus.error,
                    validity=RunValidity.invalid,
                    elapsed_seconds=elapsed,
                    validation_status=ValidationStatus.skipped,
                    artifact_dir=str(artifact_dir),
                    started_at=started_at,
                    finished_at=finished_at,
                )
                write_run_record(artifact_dir, record)
                return record

            # Write step_finished event.
            event_writer.write_event(
                EventRecord(
                    timestamp=datetime.now(tz=timezone.utc),
                    run_id=run_id,
                    step_id=step.step_id,
                    event_type="step_finished",
                    actor="harness",
                    payload={
                        "exit_status": step_result.exit_status,
                        "step_metadata": step_result.step_metadata,
                    },
                )
            )

            # Extract tool invocations from trace_metadata if available.
            # Agent CLIs may not populate this field — in v1, PATH control is
            # the primary enforcement mechanism.  We also scan stdout for
            # evidence of tool usage as a secondary check.
            tool_invocations: list[dict] = step_result.trace_metadata.get(
                "tool_invocations", []
            )

            # If no structured invocations, scan stdout for tool name mentions
            # as a best-effort detection.  This is weaker than wrapper-based
            # tracing but works with unmodified agent CLIs.
            if not tool_invocations and step.required_tool and variant == "tool_variant":
                tool_name = step.required_tool
                if tool_name in step_result.stdout or tool_name in step_result.stderr:
                    tool_invocations = [{"tool_id": tool_name, "source": "stdout_scan"}]

            # Record each invocation as a trace event.
            for inv_dict in tool_invocations:
                event_writer.write_event(
                    EventRecord(
                        timestamp=datetime.now(tz=timezone.utc),
                        run_id=run_id,
                        step_id=step.step_id,
                        event_type="tool_called",
                        actor="agent",
                        payload=inv_dict,
                    )
                )

            # Validate enforcement rules for this step.
            step_valid, enforcement_reason = executor.validate_step(
                step, tool_invocations, variant
            )
            if not step_valid:
                logger.warning(
                    "Step enforcement failed for %s/%s: %s",
                    run_id,
                    step.step_id,
                    enforcement_reason,
                )
                all_steps_enforcement_valid = False

            # Determine per-step run_status (worst wins).
            if step_result.exit_status != 0 and run_status == RunStatus.passed:
                run_status = RunStatus.failed

        # --- post-step: run validation commands ---
        validation_results = run_all_validations(task.validation_commands, workspace)

        if not validation_results:
            validation_status = ValidationStatus.skipped
        elif all(r.status == ValidationStatus.passed for r in validation_results):
            validation_status = ValidationStatus.passed
        else:
            validation_status = ValidationStatus.failed
            if run_status == RunStatus.passed:
                run_status = RunStatus.failed

        # --- extract reported tokens from the final step ---
        reported_input: int | None = None
        reported_output: int | None = None
        reported_total: int | None = None

        if last_step_result is not None:
            try:
                reported_tokens = adapter.extract_reported_tokens(last_step_result)
                reported_input = reported_tokens.input_tokens
                reported_output = reported_tokens.output_tokens
                reported_total = reported_tokens.total_tokens
            except Exception:  # noqa: BLE001
                logger.debug("Could not extract reported tokens for run %s", run_id)

        # --- classify run validity ---
        validity = _classify_validity(all_steps_enforcement_valid, validation_status)

        finished_at = datetime.now(tz=timezone.utc)
        elapsed = (finished_at - started_at).total_seconds()

        record = RunRecord(
            run_id=run_id,
            task_id=task.task_id,
            family=task.family,
            variant=Variant(variant),
            agent_id=type(adapter).__name__,
            adapter_version=getattr(adapter, "version", "unknown"),
            repo_commit=task.pinned_commit,
            status=run_status,
            validity=validity,
            reported_input_tokens=reported_input,
            reported_output_tokens=reported_output,
            reported_total_tokens=reported_total,
            elapsed_seconds=elapsed,
            validation_status=validation_status,
            artifact_dir=str(artifact_dir),
            started_at=started_at,
            finished_at=finished_at,
        )

        write_run_record(artifact_dir, record)

        event_writer.write_event(
            EventRecord(
                timestamp=finished_at,
                run_id=run_id,
                step_id="__run__",
                event_type="run_finished",
                actor="harness",
                payload={
                    "status": run_status.value,
                    "validity": validity.value,
                    "validation_status": validation_status.value,
                },
            )
        )
        event_writer.flush()

        return record
