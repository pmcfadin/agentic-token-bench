"""Layered v2 benchmark execution.

Runs deterministic-first tool tasks and optional downstream quality evaluation
without disturbing the legacy v1 agentic runner.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import shutil

from agents.base import AgentAdapter
from benchmarks.harness.artifacts import (
    copy_artifact,
    create_artifact_dir,
    write_json_artifact,
    write_run_record,
    write_text_artifact,
)
from benchmarks.harness.models import (
    BenchmarkTrack,
    EvaluatorModelClass,
    PhaseRecord,
    QualityRetentionMetrics,
    RunRecord,
    RunStatus,
    RunValidity,
    ToolEfficacyMetrics,
    V2TaskManifest,
    ValidationStatus,
    Variant,
)
from benchmarks.harness.prompts import render_quality_eval_prompt
from benchmarks.harness.validation import run_all_validations
from tools.ast_grep.wrapper import AstGrepWrapper
from tools.base import ToolWrapper
from tools.comby.wrapper import CombyWrapper
from tools.fastmod.wrapper import FastmodWrapper
from tools.qmd.wrapper import QmdWrapper
from tools.ripgrep.wrapper import RipgrepWrapper
from tools.rtk.wrapper import RtkWrapper

ProgressCallback = Callable[[str], None]


def _tool_wrapper(tool_id: str) -> ToolWrapper:
    wrappers: dict[str, type[ToolWrapper]] = {
        "ripgrep": RipgrepWrapper,
        "qmd": QmdWrapper,
        "rtk": RtkWrapper,
        "fastmod": FastmodWrapper,
        "ast-grep": AstGrepWrapper,
        "comby": CombyWrapper,
    }
    if tool_id not in wrappers:
        raise ValueError(f"Unsupported tool_id for v2 runner: {tool_id}")
    return wrappers[tool_id]()


def _primary_input(task: V2TaskManifest) -> tuple[Path, str]:
    for artifact in task.input_artifacts:
        if artifact.primary:
            return Path(artifact.source), artifact.target_name
    first = task.input_artifacts[0]
    return Path(first.source), first.target_name


def _snapshot_workspace_listing(workspace: Path, destination: Path) -> None:
    files = sorted(
        str(path.relative_to(workspace))
        for path in workspace.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(files) + ("\n" if files else ""), encoding="utf-8")


def _generate_run_id(task_id: str, variant: str, track: BenchmarkTrack, started_at: datetime) -> str:
    ts = started_at.strftime("%Y%m%d-%H%M%S")
    return f"{task_id}__{variant}__{track.value}__{ts}"


class LayeredBenchmarkRunner:
    def __init__(self, results_dir: Path = Path("benchmarks/results")) -> None:
        self._results_dir = results_dir

    def run_tool_task(
        self,
        task: V2TaskManifest,
        variant: str,
        workspace: Path,
        progress: ProgressCallback | None = None,
    ) -> RunRecord:
        def _emit(message: str) -> None:
            if progress is not None:
                progress(message)

        started_at = datetime.now(tz=timezone.utc)
        run_id = _generate_run_id(task.task_id, variant, BenchmarkTrack.tool_only, started_at)
        artifact_dir = create_artifact_dir(self._results_dir, run_id)
        _emit(f"run-tool-task: starting {task.task_id} [{variant}] as {run_id}")

        for artifact in task.input_artifacts:
            src = Path(artifact.source)
            dst = workspace / artifact.target_name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copy_artifact(src, artifact_dir / "inputs" / artifact.target_name)

        raw_artifact_path = artifact_dir / "raw_input.txt"
        if task.input_artifacts:
            _, raw_target_name = _primary_input(task)
            raw_workspace_path = workspace / raw_target_name
            copy_artifact(raw_workspace_path, raw_artifact_path)
        else:
            _snapshot_workspace_listing(workspace, raw_artifact_path)

        wrapper = _tool_wrapper(task.tool_invocation.tool_id)
        output_artifact_path = artifact_dir / task.tool_invocation.output_artifact
        status = RunStatus.passed
        notes: list[str] = []

        if variant == Variant.baseline.value and task.tool_invocation.baseline_strategy == "identity":
            copy_artifact(raw_artifact_path, output_artifact_path)
            tool_exit_status = 0
            _emit("run-tool-task: baseline identity strategy copied raw artifact")
        else:
            invoke_args = (
                task.tool_invocation.baseline_args
                if variant == Variant.baseline.value and task.tool_invocation.baseline_args
                else task.tool_invocation.args
            )
            _emit(
                f"run-tool-task: invoking {task.tool_invocation.tool_id}"
                f" with {len(invoke_args)} arg(s)"
            )
            result = wrapper.invoke(
                invoke_args,
                cwd=workspace,
                timeout=task.tool_invocation.timeout_seconds,
            )
            tool_exit_status = result.exit_status
            write_text_artifact(artifact_dir, task.tool_invocation.output_artifact, result.stdout)
            write_text_artifact(artifact_dir, "tool_stderr.txt", result.stderr)
            if result.exit_status != 0:
                status = RunStatus.failed
                notes.append(f"tool exited with status {result.exit_status}")

        env_overrides = {
            "ATB_RAW_ARTIFACT": str(raw_artifact_path),
            "ATB_REDUCED_ARTIFACT": str(output_artifact_path),
            "ATB_TASK_ID": task.task_id,
        }
        validation_results = run_all_validations(
            [check.command for check in task.deterministic_checks],
            cwd=artifact_dir,
            env_overrides=env_overrides,
        )
        write_json_artifact(
            artifact_dir,
            "deterministic_validation.json",
            [result.__dict__ | {"status": result.status.value} for result in validation_results],
        )
        if output_artifact_path.exists():
            write_text_artifact(
                artifact_dir,
                "final_answer.txt",
                output_artifact_path.read_text(encoding="utf-8"),
            )
        if validation_results and not all(r.status == ValidationStatus.passed for r in validation_results):
            status = RunStatus.failed
            validation_status = ValidationStatus.failed
        elif validation_results:
            validation_status = ValidationStatus.passed
        else:
            validation_status = ValidationStatus.skipped

        raw_bytes = raw_artifact_path.stat().st_size
        reduced_bytes = output_artifact_path.stat().st_size if output_artifact_path.exists() else None
        reduction_ratio = None
        if reduced_bytes is not None and raw_bytes > 0:
            reduction_ratio = reduced_bytes / raw_bytes

        finished_at = datetime.now(tz=timezone.utc)
        record = RunRecord(
            run_id=run_id,
            task_id=task.task_id,
            family=task.family,
            variant=Variant(variant),
            agent_id="tool-only",
            adapter_version="v2",
            repo_commit=task.pinned_commit,
            status=status,
            validity=RunValidity.valid if validation_status != ValidationStatus.failed else RunValidity.invalid,
            elapsed_seconds=(finished_at - started_at).total_seconds(),
            validation_status=validation_status,
            artifact_dir=str(artifact_dir),
            started_at=started_at,
            finished_at=finished_at,
            track=BenchmarkTrack.tool_only,
            task_version=task.version,
            phase_records=[
                PhaseRecord(
                    name="tool_only",
                    track=BenchmarkTrack.tool_only,
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    validation_status=validation_status,
                    notes=notes,
                )
            ],
            tool_metrics=ToolEfficacyMetrics(
                raw_bytes=raw_bytes,
                reduced_bytes=reduced_bytes,
                reduction_ratio=reduction_ratio,
                deterministic_valid=validation_status == ValidationStatus.passed,
                deterministic_check_count=len(validation_results),
            ),
        )
        write_run_record(artifact_dir, record)
        write_json_artifact(
            artifact_dir,
            "preservation_manifest.json",
            {
                "task_id": task.task_id,
                "tool_id": task.tool_invocation.tool_id,
                "raw_artifact": str(raw_artifact_path.name),
                "reduced_artifact": str(output_artifact_path.name),
                "deterministic_checks": [check.model_dump() for check in task.deterministic_checks],
                "tool_exit_status": tool_exit_status,
            },
        )
        return record

    def run_quality_eval(
        self,
        task: V2TaskManifest,
        variant: str,
        source_run_dir: Path,
        adapter: AgentAdapter,
        evaluator_model_class: EvaluatorModelClass = EvaluatorModelClass.small,
        progress: ProgressCallback | None = None,
    ) -> RunRecord:
        if task.quality_evaluation is None:
            raise ValueError(f"Task {task.task_id} does not define quality_evaluation")

        def _emit(message: str) -> None:
            if progress is not None:
                progress(message)

        started_at = datetime.now(tz=timezone.utc)
        run_id = _generate_run_id(task.task_id, variant, BenchmarkTrack.quality_eval, started_at)
        artifact_dir = create_artifact_dir(self._results_dir, run_id)
        raw_artifact_path = Path(source_run_dir) / "raw_input.txt"
        reduced_artifact_path = Path(source_run_dir) / task.tool_invocation.output_artifact
        if not raw_artifact_path.exists() or not reduced_artifact_path.exists():
            raise FileNotFoundError("quality-eval requires raw_input.txt and reduced output artifact")

        raw_content = raw_artifact_path.read_text(encoding="utf-8")
        reduced_content = reduced_artifact_path.read_text(encoding="utf-8")
        raw_prompt = render_quality_eval_prompt(
            task_id=task.task_id,
            family=task.family,
            question=task.quality_evaluation.question,
            artifact_kind="raw",
            artifact_content=raw_content,
        )
        reduced_prompt = render_quality_eval_prompt(
            task_id=task.task_id,
            family=task.family,
            question=task.quality_evaluation.question,
            artifact_kind="reduced",
            artifact_content=reduced_content,
        )
        write_text_artifact(artifact_dir, "raw_prompt.txt", raw_prompt)
        write_text_artifact(artifact_dir, "reduced_prompt.txt", reduced_prompt)

        _emit(f"run-quality-eval: invoking {type(adapter).__name__} on raw artifact")
        raw_result = adapter.run_step(
            prompt=raw_prompt,
            step_env={},
            workspace=Path(source_run_dir),
            timeout=180.0,
        )
        _emit(f"run-quality-eval: invoking {type(adapter).__name__} on reduced artifact")
        reduced_result = adapter.run_step(
            prompt=reduced_prompt,
            step_env={},
            workspace=Path(source_run_dir),
            timeout=180.0,
        )
        write_text_artifact(artifact_dir, "raw_answer.txt", raw_result.stdout)
        write_text_artifact(artifact_dir, "reduced_answer.txt", reduced_result.stdout)

        raw_validation_results = run_all_validations(
            task.quality_evaluation.raw_validation_commands,
            cwd=artifact_dir,
            env_overrides={
                "ATB_RAW_ANSWER": str(artifact_dir / "raw_answer.txt"),
                "ATB_RAW_ARTIFACT": str(raw_artifact_path),
            },
        )
        reduced_validation_results = run_all_validations(
            task.quality_evaluation.reduced_validation_commands,
            cwd=artifact_dir,
            env_overrides={
                "ATB_REDUCED_ANSWER": str(artifact_dir / "reduced_answer.txt"),
                "ATB_REDUCED_ARTIFACT": str(reduced_artifact_path),
            },
        )
        write_json_artifact(
            artifact_dir,
            "quality_validation.json",
            {
                "raw": [result.__dict__ | {"status": result.status.value} for result in raw_validation_results],
                "reduced": [result.__dict__ | {"status": result.status.value} for result in reduced_validation_results],
            },
        )

        raw_score = 1.0 if raw_validation_results and all(r.status == ValidationStatus.passed for r in raw_validation_results) else 0.0
        reduced_score = 1.0 if reduced_validation_results and all(r.status == ValidationStatus.passed for r in reduced_validation_results) else 0.0
        finished_at = datetime.now(tz=timezone.utc)
        quality_delta = reduced_score - raw_score
        status = RunStatus.passed if reduced_score >= 1.0 else RunStatus.failed
        validation_status = ValidationStatus.passed if reduced_score >= 1.0 else ValidationStatus.failed

        llm_counts = {
            EvaluatorModelClass.none: (0, 0),
            EvaluatorModelClass.small: (2, 0),
            EvaluatorModelClass.expensive: (0, 2),
        }
        small_calls, expensive_calls = llm_counts[evaluator_model_class]

        record = RunRecord(
            run_id=run_id,
            task_id=task.task_id,
            family=task.family,
            variant=Variant(variant),
            agent_id=type(adapter).__name__,
            adapter_version=getattr(adapter, "version", "unknown"),
            repo_commit=task.pinned_commit,
            status=status,
            validity=RunValidity.valid if validation_status == ValidationStatus.passed else RunValidity.invalid,
            elapsed_seconds=(finished_at - started_at).total_seconds(),
            validation_status=validation_status,
            artifact_dir=str(artifact_dir),
            started_at=started_at,
            finished_at=finished_at,
            track=BenchmarkTrack.quality_eval,
            task_version=task.version,
            phase_records=[
                PhaseRecord(
                    name="quality_eval",
                    track=BenchmarkTrack.quality_eval,
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    validation_status=validation_status,
                )
            ],
            quality_metrics=QualityRetentionMetrics(
                raw_quality_score=raw_score,
                reduced_quality_score=reduced_score,
                quality_delta=quality_delta,
                llm_call_count_small=small_calls,
                llm_call_count_expensive=expensive_calls,
                escalation_reason=task.quality_evaluation.escalation_note,
                evaluator_model_class=evaluator_model_class,
            ),
        )
        write_run_record(artifact_dir, record)
        return record
