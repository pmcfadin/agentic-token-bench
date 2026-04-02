"""benchmarks.harness.runner — top-level benchmark run orchestration.

See docs/plans/2026-03-31-v1-build-plan-design.md for module responsibilities.
"""

from __future__ import annotations

__all__ = ["BenchmarkRunner"]

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from agents.base import AgentAdapter
from benchmarks.harness.artifacts import (
    create_artifact_dir,
    write_final_answer,
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
from benchmarks.harness.validation import run_validation_command

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[str], None]


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
    """Return RunValidity based on validation results.

    In v1, tool enforcement via stdout scanning is best-effort because agent
    CLIs don't expose structured tool-call traces.  PATH control is the real
    enforcement mechanism (the tool is either on PATH or not).  Validity is
    therefore driven by validation outcome, not stdout-based enforcement.
    """
    if validation_status != ValidationStatus.failed:
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
        progress: ProgressCallback | None = None,
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
        def _emit(message: str) -> None:
            if progress is not None:
                progress(message)

        started_at = datetime.now(tz=timezone.utc)
        run_id = _generate_run_id(task.task_id, variant, started_at)
        _emit(f"run-task: starting {task.task_id} [{variant}] as {run_id}")

        # --- artifact directory ---
        artifact_dir = create_artifact_dir(self._results_dir, run_id)
        _emit(f"run-task: artifacts at {artifact_dir}")

        # --- tracing writers ---
        event_writer = EventWriter(artifact_dir / "trace.jsonl")
        # InvocationWriter is created but invocations are delivered through
        # the adapter's trace_metadata; the writer is available for subclasses
        # or future use.
        _invocation_writer = InvocationWriter(artifact_dir / "invocations.jsonl")

        # --- step executor ---
        wrappers: dict[str, Path] = tool_wrappers or {}
        executor = StepExecutor(wrappers)

        # Copy fixture files into workspace before running any steps.
        if task.fixture_files:
            import shutil
            project_root = Path(__file__).resolve().parent.parent.parent
            for rel_path in task.fixture_files:
                src = project_root / rel_path
                dst = workspace / Path(rel_path).name
                if src.exists():
                    shutil.copy2(src, dst)
                else:
                    logger.warning("Fixture file not found, skipping: %s", src)
        _emit(f"run-task: workspace ready at {workspace}")

        # Accumulated state across steps.
        all_steps_enforcement_valid = True
        last_step_result = None
        run_status = RunStatus.passed

        for step_index, step in enumerate(task.steps):
            _emit(
                f"step {step_index + 1}/{len(task.steps)}: {step.step_id}"
                f" ({step.name})"
            )
            if step.required_tool:
                _emit(
                    f"step {step.step_id}: required tool={step.required_tool}"
                    f", allowed={','.join(step.allowed_tools) if step.allowed_tools else '[]'}"
                    f", blocked={','.join(step.blocked_tools) if step.blocked_tools else '[]'}"
                )

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
            _emit(f"step {step.step_id}: prompt written to {artifact_dir / 'prompt.txt'}")

            # Execute step via the adapter.
            _emit(f"step {step.step_id}: invoking {type(adapter).__name__} (timeout=300s)")
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
                _emit(f"step {step.step_id}: adapter error: {exc}")
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
                _emit(f"run-task: wrote {artifact_dir / 'run.json'}")
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
            _emit(
                f"step {step.step_id}: finished exit={step_result.exit_status}"
                f" status={step_result.step_metadata.get('status', 'unknown')}"
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
            # Map tool family names to binary names and common references.
            _TOOL_ALIASES: dict[str, list[str]] = {
                "ripgrep": ["ripgrep", "rg ", '"rg"', "rg\n", "Grep"],
                "qmd": ["qmd"],
                "rtk": ["rtk"],
                "fastmod": ["fastmod"],
                "ast-grep": ["ast-grep", "ast_grep", "sg "],
                "comby": ["comby"],
            }
            if not tool_invocations and step.required_tool and variant == "tool_variant":
                tool_name = step.required_tool
                aliases = _TOOL_ALIASES.get(tool_name, [tool_name])
                combined = step_result.stdout + step_result.stderr
                if any(alias in combined for alias in aliases):
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
                _emit(f"step {step.step_id}: enforcement failed: {enforcement_reason}")
            else:
                _emit(f"step {step.step_id}: enforcement passed")

            # Determine per-step run_status (worst wins).
            if step_result.exit_status != 0 and run_status == RunStatus.passed:
                run_status = RunStatus.failed

        # --- post-step: extract and write final answer ---
        if last_step_result is not None:
            stdout = last_step_result.stdout or ""
            answer_text: str
            try:
                import json as _json

                parsed = _json.loads(stdout)
                answer_text = parsed.get("result", stdout)
                if not isinstance(answer_text, str):
                    answer_text = stdout
            except Exception:  # noqa: BLE001
                answer_text = stdout
            write_final_answer(artifact_dir, answer_text)
            _emit(f"run-task: wrote {artifact_dir / 'final_answer.txt'}")

        # --- post-step: run validation commands ---
        validation_results = []
        if task.validation_commands:
            _emit(
                f"run-task: running {len(task.validation_commands)} validation command(s)"
            )
        else:
            _emit("run-task: no validation commands defined")

        for validation_index, command in enumerate(task.validation_commands, start=1):
            _emit(f"validation {validation_index}/{len(task.validation_commands)}: {command}")
            result = run_validation_command(command, artifact_dir)
            validation_results.append(result)
            _emit(
                f"validation {validation_index}/{len(task.validation_commands)}:"
                f" exit={result.exit_code} status={result.status.value}"
                f" duration={result.duration_seconds:.1f}s"
            )

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
                _emit(
                    "run-task: reported tokens "
                    f"input={reported_input} output={reported_output} total={reported_total}"
                )
            except Exception:  # noqa: BLE001
                logger.debug("Could not extract reported tokens for run %s", run_id)
                _emit("run-task: could not extract reported tokens")

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
        _emit(f"run-task: wrote {artifact_dir / 'run.json'}")
        _emit(
            f"run-task: finished status={run_status.value}"
            f" validity={validity.value} tokens={reported_total}"
            f" elapsed={elapsed:.1f}s"
        )

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
