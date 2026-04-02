from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from benchmarks.harness.layered_runner import LayeredBenchmarkRunner
from benchmarks.harness.models import (
    BenchmarkTrack,
    DeterministicCheckSpec,
    InputArtifactSpec,
    RunStatus,
    ToolInvocationSpec,
    V2TaskManifest,
    ValidationStatus,
)
from tools.base import InvocationResult, ToolManifest, ToolWrapper


class _FakeToolWrapper(ToolWrapper):
    def manifest(self) -> ToolManifest:
        return ToolManifest(
            id="fake",
            name="fake",
            version="1.0.0",
            category="test",
            description="fake",
        )

    def invoke(self, args: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: float = 120.0) -> InvocationResult:
        return InvocationResult(
            stdout="needle preserved\n",
            stderr="",
            exit_status=0,
            duration_ms=1.0,
        )

    def record_invocation(self, result: InvocationResult, args: list[str], step_id: str, run_id: str):  # pragma: no cover
        raise NotImplementedError


def test_v2_manifest_matches_schema() -> None:
    task_path = Path("benchmarks/tasks/cassandra/v2/cassandra-rtk-02.yaml")
    schema_path = Path("schemas/task.v2.schema.json")
    raw = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(raw, schema)


def test_layered_runner_tool_task_writes_phase_artifacts(monkeypatch, tmp_path: Path) -> None:
    fixture = tmp_path / "input.log"
    fixture.write_text("raw noise\n", encoding="utf-8")
    results_dir = tmp_path / "results"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    manifest = V2TaskManifest(
        task_id="demo-v2",
        title="demo",
        family="rtk",
        repo="cassandra",
        pinned_commit="deadbeef",
        objective="demo",
        task_description="demo",
        success_criteria=["needle preserved"],
        input_artifacts=[
            InputArtifactSpec(
                name="input",
                source=str(fixture),
                target_name="input.log",
                primary=True,
            )
        ],
        tool_invocation=ToolInvocationSpec(
            tool_id="rtk",
            args=["read", "input.log"],
            output_artifact="reduced_output.txt",
        ),
        deterministic_checks=[
            DeterministicCheckSpec(
                name="contains_needle",
                command=(
                    "python -c \"import os, pathlib, sys; "
                    "text = pathlib.Path(os.environ['ATB_REDUCED_ARTIFACT']).read_text(); "
                    "sys.exit(0 if 'needle' in text else 1)\""
                ),
            )
        ],
    )

    monkeypatch.setattr(
        "benchmarks.harness.layered_runner._tool_wrapper",
        lambda tool_id: _FakeToolWrapper(),
    )

    record = LayeredBenchmarkRunner(results_dir=results_dir).run_tool_task(
        task=manifest,
        variant="tool_variant",
        workspace=workspace,
    )

    artifact_dir = Path(record.artifact_dir)
    assert record.track == BenchmarkTrack.tool_only
    assert record.status == RunStatus.passed
    assert record.validation_status == ValidationStatus.passed
    assert record.tool_metrics is not None
    assert record.tool_metrics.raw_bytes == len("raw noise\n".encode("utf-8"))
    assert record.tool_metrics.reduced_bytes == len("needle preserved\n".encode("utf-8"))
    assert (artifact_dir / "raw_input.txt").exists()
    assert (artifact_dir / "reduced_output.txt").exists()
    assert (artifact_dir / "final_answer.txt").read_text(encoding="utf-8") == "needle preserved\n"
    assert len(record.phase_records) == 1

