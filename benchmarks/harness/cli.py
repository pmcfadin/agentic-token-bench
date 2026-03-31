"""CLI for the agentic-token-bench benchmark harness."""

from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml

app = typer.Typer(
    name="atb",
    help="agentic-token-bench: benchmark token-saving tools in agentic coding workflows.",
)

_QUAL_DIR = Path("benchmarks/qualification")
_ADAPTER_VERSION = "0.1.0"
_RESULTS_DIR = Path("benchmarks/results")

_SUPPORTED_AGENTS = ("claude", "codex", "gemini-cli")


def _build_adapter(agent: str):  # type: ignore[return]
    """Instantiate and return the adapter for *agent*.

    Args:
        agent: One of "claude", "codex", or "gemini-cli".

    Returns:
        An AgentAdapter subclass instance.

    Raises:
        typer.BadParameter: When *agent* is not a supported name.
    """
    if agent == "claude":
        from agents.claude.adapter import ClaudeAdapter

        return ClaudeAdapter()
    if agent == "codex":
        from agents.codex.adapter import CodexAdapter

        return CodexAdapter()
    if agent == "gemini-cli":
        from agents.gemini_cli.adapter import GeminiCliAdapter

        return GeminiCliAdapter()
    raise typer.BadParameter(
        f"Unknown agent {agent!r}.  Supported agents: {', '.join(_SUPPORTED_AGENTS)}"
    )


@app.command()
def qualify_agent(agent: str = typer.Argument(help="Agent ID to qualify")) -> None:
    """Run qualification probes for an agent adapter.

    Writes results to benchmarks/qualification/{agent}.json and prints
    PASS or FAIL.

    Supported agents: claude, codex, gemini-cli.
    """
    from benchmarks.harness.qualification import run_qualification

    try:
        adapter = _build_adapter(agent)
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    try:
        record = run_qualification(
            adapter=adapter,
            agent_id=agent,
            adapter_version=_ADAPTER_VERSION,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"qualify-agent: run_qualification raised an exception: {exc}", err=True)
        raise typer.Exit(1) from exc

    _QUAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _QUAL_DIR / f"{agent}.json"
    out_path.write_text(json.dumps(record.model_dump(), indent=2))

    if record.qualified:
        typer.echo(f"PASS  {agent}  →  {out_path}")
    else:
        reason = record.failure_reason or "unknown failure"
        typer.echo(f"FAIL  {agent}  ({reason})  →  {out_path}")
        raise typer.Exit(1)


@app.command()
def run_task(
    task_file: str = typer.Argument(help="Path to the task YAML manifest"),
    agent: str = typer.Option(help="Agent ID"),
    variant: str = typer.Option(default="tool_variant", help="baseline or tool_variant"),
    workspace: str = typer.Option(default="", help="Path to workspace directory (default: temp dir)"),
    results_dir: str = typer.Option(default="benchmarks/results", help="Results directory"),
) -> None:
    """Run a single benchmark task from a YAML manifest file."""
    import tempfile

    from benchmarks.harness.models import TaskManifest
    from benchmarks.harness.runner import BenchmarkRunner

    task_path = Path(task_file)
    if not task_path.exists():
        typer.echo(f"run-task: task file not found: {task_path}", err=True)
        raise typer.Exit(1)

    try:
        raw = yaml.safe_load(task_path.read_text(encoding="utf-8"))
        manifest = TaskManifest.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-task: failed to load task manifest: {exc}", err=True)
        raise typer.Exit(1) from exc

    try:
        adapter = _build_adapter(agent)
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    ws_path = Path(workspace) if workspace else Path(tempfile.mkdtemp())
    runner = BenchmarkRunner(results_dir=Path(results_dir))

    try:
        record = runner.run_task(
            task=manifest,
            adapter=adapter,
            variant=variant,
            workspace=ws_path,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-task: runner raised an exception: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(
        f"run-task: {record.run_id}"
        f"  status={record.status.value}"
        f"  validity={record.validity.value}"
        f"  tokens={record.reported_total_tokens}"
        f"  elapsed={record.elapsed_seconds:.1f}s"
    )


@app.command()
def run_family(
    family: str = typer.Argument(help="Tool family to run"),
    agent: str = typer.Option(help="Agent ID"),
) -> None:
    """Run all tasks for a tool family."""
    typer.echo(f"run-family: not yet implemented (family={family}, agent={agent})")
    raise typer.Exit(1)


@app.command()
def run_suite(
    agent: str = typer.Option(help="Agent ID"),
    tasks_dir: str = typer.Option(
        default="benchmarks/tasks/cassandra/official",
        help="Directory containing task YAML manifests",
    ),
    list_only: bool = typer.Option(
        default=False,
        help="List available tasks without running them",
    ),
) -> None:
    """Run the full official benchmark suite.

    When --list-only is set, loads and displays all available task manifests
    from the tasks directory without executing any runs.
    """
    import yaml

    from benchmarks.harness.models import TaskManifest

    tasks_path = Path(tasks_dir)
    if not tasks_path.exists():
        typer.echo(f"run-suite: tasks directory not found: {tasks_path}", err=True)
        raise typer.Exit(1)

    task_files = sorted(tasks_path.glob("*.yaml"))
    if not task_files:
        typer.echo(f"run-suite: no YAML task files found under {tasks_path}", err=True)
        raise typer.Exit(1)

    manifests: list[TaskManifest] = []
    for task_file in task_files:
        try:
            raw = yaml.safe_load(task_file.read_text(encoding="utf-8"))
            manifests.append(TaskManifest.model_validate(raw))
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"run-suite: skipping {task_file} ({exc})", err=True)

    if not manifests:
        typer.echo("run-suite: no valid task manifests loaded", err=True)
        raise typer.Exit(1)

    families = sorted({m.family for m in manifests})
    typer.echo(
        f"run-suite: loaded {len(manifests)} tasks across {len(families)} families"
        f"  agent={agent}"
    )
    typer.echo(f"  families: {', '.join(families)}")
    for manifest in manifests:
        typer.echo(f"  • {manifest.task_id}  [{manifest.family}]  {manifest.title}")

    if list_only:
        return

    typer.echo(
        "run-suite: full execution not yet implemented."
        "  Use 'atb run-task' for individual runs or"
        " 'uv run scripts/generate_fixture_runs.py' for fixture generation.",
        err=True,
    )
    raise typer.Exit(1)


@app.command()
def generate_scorecard(
    results_dir: str = typer.Argument(default="benchmarks/results", help="Results directory"),
    agent_id: str = typer.Option(default="unknown", help="Agent ID for the scorecard"),
    repo_commit: str = typer.Option(default="unknown", help="Repo commit for the scorecard"),
    output_dir: str = typer.Option(default="", help="Output directory (defaults to results_dir)"),
) -> None:
    """Generate scorecards from run.json files found in the results directory tree."""
    from benchmarks.harness.models import RunRecord
    from benchmarks.harness.reporting import (
        generate_suite_scorecard,
        render_scorecard_json,
        render_scorecard_markdown,
    )

    results_path = Path(results_dir)
    if not results_path.exists():
        typer.echo(f"generate-scorecard: results directory not found: {results_path}", err=True)
        raise typer.Exit(1)

    run_files = list(results_path.rglob("run.json"))
    if not run_files:
        typer.echo(f"generate-scorecard: no run.json files found under {results_path}", err=True)
        raise typer.Exit(1)

    runs: list[RunRecord] = []
    for run_file in run_files:
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))
            runs.append(RunRecord.model_validate(data))
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"generate-scorecard: skipping {run_file} ({exc})", err=True)

    if not runs:
        typer.echo("generate-scorecard: no valid run records loaded", err=True)
        raise typer.Exit(1)

    scorecard = generate_suite_scorecard(runs, agent_id=agent_id, repo_commit=repo_commit)

    out_path = Path(output_dir) if output_dir else results_path
    out_path.mkdir(parents=True, exist_ok=True)

    md_path = out_path / "scorecard.md"
    json_path = out_path / "scorecard.json"

    md_path.write_text(render_scorecard_markdown(scorecard), encoding="utf-8")
    json_path.write_text(render_scorecard_json(scorecard), encoding="utf-8")

    typer.echo(f"generate-scorecard: loaded {len(runs)} runs, {len(scorecard.families)} families")
    typer.echo(f"generate-scorecard: wrote {md_path}")
    typer.echo(f"generate-scorecard: wrote {json_path}")


@app.command()
def validate_schemas() -> None:
    """Validate all task and run manifests against JSON schemas."""
    typer.echo("validate-schemas: not yet implemented")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
