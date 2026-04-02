"""CLI for the agentic-token-bench benchmark harness."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

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


def _progress_printer(message: str) -> None:
    print(message, flush=True)


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


def _load_yaml_manifest(task_path: Path) -> dict:
    raw = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"task manifest must deserialize to a mapping: {task_path}")
    return raw


def _prepare_workspace(
    *,
    repo_commit: str,
    run_id: str,
    workspace: str,
    skip_checkout: bool,
) -> Path:
    from benchmarks.harness.workspace import WorkspaceManager

    ws_mgr = WorkspaceManager(cache_dir=Path(".cache/repos"))
    if workspace:
        ws_path = Path(workspace)
        if not ws_path.exists():
            raise FileNotFoundError(f"workspace not found: {ws_path}")
        return ws_path

    if skip_checkout:
        return Path(tempfile.mkdtemp())

    repo_yaml = Path("benchmarks/repos/cassandra/repo.yaml")
    if not repo_yaml.exists():
        raise FileNotFoundError("benchmarks/repos/cassandra/repo.yaml not found")
    repo_config = ws_mgr.load_repo_config(repo_yaml)
    typer.echo(f"workspace: cloning {repo_config['name']} at {repo_commit[:12]}...")
    ws_path = ws_mgr.prepare(
        repo_url=repo_config["url"],
        commit=repo_commit,
        run_id=run_id,
    )
    typer.echo(f"workspace: ready at {ws_path}")
    return ws_path


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
    workspace: str = typer.Option(default="", help="Path to pre-existing workspace (default: clone from repo.yaml)"),
    results_dir: str = typer.Option(default="benchmarks/results", help="Results directory"),
    skip_checkout: bool = typer.Option(default=False, help="Skip Cassandra checkout (use existing workspace)"),
) -> None:
    """Run a single benchmark task from a YAML manifest file.

    By default, clones Apache Cassandra at the pinned commit into a temp
    workspace. Pass --workspace to use a pre-existing checkout.
    """
    from benchmarks.harness.models import TaskManifest
    from benchmarks.harness.runner import BenchmarkRunner

    task_path = Path(task_file)
    if not task_path.exists():
        typer.echo(f"run-task: task file not found: {task_path}", err=True)
        raise typer.Exit(1)

    try:
        raw = _load_yaml_manifest(task_path)
        manifest = TaskManifest.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-task: failed to load task manifest: {exc}", err=True)
        raise typer.Exit(1) from exc

    try:
        adapter = _build_adapter(agent)
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    try:
        ws_path = _prepare_workspace(
            repo_commit=manifest.pinned_commit,
            run_id=f"{manifest.task_id}-{variant}",
            workspace=workspace,
            skip_checkout=skip_checkout,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-task: failed to prepare workspace: {exc}", err=True)
        raise typer.Exit(1) from exc

    runner = BenchmarkRunner(results_dir=Path(results_dir))

    try:
        record = runner.run_task(
            task=manifest,
            adapter=adapter,
            variant=variant,
            workspace=ws_path,
            progress=_progress_printer,
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
    tasks_dir: str = typer.Option(
        default="benchmarks/tasks/cassandra/official",
        help="Directory containing task YAML manifests",
    ),
    results_dir: str = typer.Option(default="benchmarks/results", help="Results directory"),
) -> None:
    """Run all tasks for a tool family (both baseline and tool_variant)."""
    from benchmarks.harness.models import TaskManifest
    from benchmarks.harness.runner import BenchmarkRunner

    try:
        adapter = _build_adapter(agent)
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    tasks_path = Path(tasks_dir)
    task_files = sorted(tasks_path.glob("*.yaml"))
    manifests = []
    for tf in task_files:
        try:
            raw = yaml.safe_load(tf.read_text(encoding="utf-8"))
            m = TaskManifest.model_validate(raw)
            if m.family == family:
                manifests.append(m)
        except Exception:  # noqa: BLE001
            pass

    if not manifests:
        typer.echo(f"run-family: no tasks found for family '{family}'", err=True)
        raise typer.Exit(1)

    runner = BenchmarkRunner(results_dir=Path(results_dir))
    typer.echo(f"run-family: {len(manifests)} tasks for {family}, agent={agent}")

    for manifest in manifests:
        for variant in ("baseline", "tool_variant"):
            ws = Path(tempfile.mkdtemp())
            try:
                record = runner.run_task(
                    task=manifest,
                    adapter=adapter,
                    variant=variant,
                    workspace=ws,
                    progress=_progress_printer,
                )
                typer.echo(
                    f"  {record.run_id}  {variant}  tokens={record.reported_total_tokens}"
                    f"  status={record.status.value}"
                )
            except Exception as exc:  # noqa: BLE001
                typer.echo(f"  FAILED {manifest.task_id} {variant}: {exc}", err=True)


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

    from benchmarks.harness.runner import BenchmarkRunner

    try:
        adapter = _build_adapter(agent)
    except typer.BadParameter as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    runner = BenchmarkRunner(results_dir=_RESULTS_DIR)
    total = len(manifests) * 2  # baseline + tool_variant per task
    completed = 0

    for manifest in manifests:
        for variant in ("baseline", "tool_variant"):
            ws = Path(tempfile.mkdtemp())
            try:
                record = runner.run_task(
                    task=manifest,
                    adapter=adapter,
                    variant=variant,
                    workspace=ws,
                    progress=_progress_printer,
                )
                completed += 1
                typer.echo(
                    f"  [{completed}/{total}] {record.run_id}"
                    f"  {variant}  tokens={record.reported_total_tokens}"
                    f"  status={record.status.value}"
                )
            except Exception as exc:  # noqa: BLE001
                completed += 1
                typer.echo(f"  [{completed}/{total}] FAILED {manifest.task_id} {variant}: {exc}", err=True)

    typer.echo(f"run-suite: completed {completed}/{total} runs")


@app.command("run-tool-task")
def run_tool_task(
    task_file: str = typer.Argument(help="Path to the v2 task YAML manifest"),
    variant: str = typer.Option(default="tool_variant", help="baseline or tool_variant"),
    workspace: str = typer.Option(default="", help="Path to pre-existing workspace"),
    results_dir: str = typer.Option(default="benchmarks/results", help="Results directory"),
    skip_checkout: bool = typer.Option(default=False, help="Skip Cassandra checkout when possible"),
) -> None:
    """Run a deterministic-first v2 task in tool-only mode."""
    from benchmarks.harness.layered_runner import LayeredBenchmarkRunner
    from benchmarks.harness.models import V2TaskManifest

    task_path = Path(task_file)
    if not task_path.exists():
        typer.echo(f"run-tool-task: task file not found: {task_path}", err=True)
        raise typer.Exit(1)

    try:
        manifest = V2TaskManifest.model_validate(_load_yaml_manifest(task_path))
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-tool-task: failed to load v2 manifest: {exc}", err=True)
        raise typer.Exit(1) from exc

    try:
        ws_path = _prepare_workspace(
            repo_commit=manifest.pinned_commit,
            run_id=f"{manifest.task_id}-{variant}-tool-only",
            workspace=workspace,
            skip_checkout=skip_checkout,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-tool-task: failed to prepare workspace: {exc}", err=True)
        raise typer.Exit(1) from exc

    runner = LayeredBenchmarkRunner(results_dir=Path(results_dir))
    try:
        record = runner.run_tool_task(
            task=manifest,
            variant=variant,
            workspace=ws_path,
            progress=_progress_printer,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-tool-task: runner raised an exception: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(
        f"run-tool-task: {record.run_id}"
        f" status={record.status.value}"
        f" validity={record.validity.value}"
        f" raw_bytes={record.tool_metrics.raw_bytes if record.tool_metrics else 'N/A'}"
        f" reduced_bytes={record.tool_metrics.reduced_bytes if record.tool_metrics else 'N/A'}"
    )


@app.command("run-quality-eval")
def run_quality_eval(
    task_file: str = typer.Argument(help="Path to the v2 task YAML manifest"),
    source_run_dir: str = typer.Argument(default="", help="Path to a prior tool-only run artifact directory (or use --latest-run)"),
    agent: str = typer.Option(help="Agent ID used as downstream evaluator"),
    variant: str = typer.Option(default="tool_variant", help="baseline or tool_variant"),
    results_dir: str = typer.Option(default="benchmarks/results", help="Results directory"),
    evaluator_model_class: str = typer.Option(default="small", help="none, small, or expensive"),
    latest_run: bool = typer.Option(default=False, help="Auto-discover the latest tool-only run directory for this task"),
) -> None:
    """Run the downstream quality-evaluation phase for a v2 task."""
    from benchmarks.harness.layered_runner import LayeredBenchmarkRunner
    from benchmarks.harness.models import EvaluatorModelClass, V2TaskManifest

    task_path = Path(task_file)
    if not task_path.exists():
        typer.echo(f"run-quality-eval: task file not found: {task_path}", err=True)
        raise typer.Exit(1)

    try:
        manifest = V2TaskManifest.model_validate(_load_yaml_manifest(task_path))
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-quality-eval: failed to load v2 manifest: {exc}", err=True)
        raise typer.Exit(1) from exc

    if not source_run_dir and not latest_run:
        typer.echo("run-quality-eval: provide source_run_dir or --latest-run", err=True)
        raise typer.Exit(1)

    if latest_run:
        results_path = Path(results_dir)
        candidates = sorted(results_path.glob(f"{manifest.task_id}__*__tool_only__*"))
        if not candidates:
            typer.echo(
                f"run-quality-eval: no tool_only run found for {manifest.task_id} in {results_dir}",
                err=True,
            )
            raise typer.Exit(1)
        source_run_dir = str(candidates[-1])
        typer.echo(f"run-quality-eval: using source run {source_run_dir}")

    try:
        adapter = _build_adapter(agent)
        model_class = EvaluatorModelClass(evaluator_model_class)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-quality-eval: invalid evaluator configuration: {exc}", err=True)
        raise typer.Exit(1) from exc

    runner = LayeredBenchmarkRunner(results_dir=Path(results_dir))
    try:
        record = runner.run_quality_eval(
            task=manifest,
            variant=variant,
            source_run_dir=Path(source_run_dir),
            adapter=adapter,
            evaluator_model_class=model_class,
            progress=_progress_printer,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"run-quality-eval: runner raised an exception: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(
        f"run-quality-eval: {record.run_id}"
        f" status={record.status.value}"
        f" quality_delta={record.quality_metrics.quality_delta if record.quality_metrics else 'N/A'}"
        f" small_calls={record.quality_metrics.llm_call_count_small if record.quality_metrics else 'N/A'}"
        f" expensive_calls={record.quality_metrics.llm_call_count_expensive if record.quality_metrics else 'N/A'}"
    )


@app.command()
def generate_scorecard(
    results_dir: str = typer.Argument(default="benchmarks/results", help="Results directory"),
    repo_commit: str = typer.Option(default="unknown", help="Repo commit for the scorecard"),
    output_dir: str = typer.Option(default="", help="Output directory (defaults to results_dir)"),
) -> None:
    """Generate per-agent scorecards from run.json files found in the results directory tree.

    Auto-detects agents from the run data and writes one scorecard per agent
    (e.g. scorecard-claude.json, scorecard-codex.json) plus a combined scorecard.
    """
    from benchmarks.harness.models import RunRecord
    from benchmarks.harness.reporting import (
        generate_per_agent_scorecards,
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

    out_path = Path(output_dir) if output_dir else results_path
    out_path.mkdir(parents=True, exist_ok=True)

    # Auto-detect repo_commit from run data if not provided
    if repo_commit == "unknown":
        commits = {r.repo_commit for r in runs if r.repo_commit}
        if len(commits) == 1:
            repo_commit = commits.pop()

    # Generate per-agent scorecards
    per_agent = generate_per_agent_scorecards(runs, repo_commit=repo_commit)
    for agent_name, scorecard in per_agent.items():
        md_path = out_path / f"scorecard-{agent_name}.md"
        json_path = out_path / f"scorecard-{agent_name}.json"
        md_path.write_text(render_scorecard_markdown(scorecard), encoding="utf-8")
        json_path.write_text(render_scorecard_json(scorecard), encoding="utf-8")
        typer.echo(f"generate-scorecard: wrote {json_path} ({scorecard.families[0].baseline.run_count + scorecard.families[0].tool_variant.run_count if scorecard.families else 0} runs)")

    # Generate combined scorecard (clearly labeled)
    combined = generate_suite_scorecard(runs, agent_id="all-agents-combined", repo_commit=repo_commit)
    combined_md = out_path / "scorecard.md"
    combined_json = out_path / "scorecard.json"
    combined_md.write_text(render_scorecard_markdown(combined), encoding="utf-8")
    combined_json.write_text(render_scorecard_json(combined), encoding="utf-8")

    agents_found = sorted(per_agent.keys())
    typer.echo(f"generate-scorecard: loaded {len(runs)} runs, agents: {', '.join(agents_found)}")
    typer.echo(f"generate-scorecard: wrote per-agent scorecards + combined to {out_path}")


@app.command("generate-layered-scorecards")
def generate_layered_scorecards(
    results_dir: str = typer.Argument(default="benchmarks/results", help="Results directory"),
    repo_commit: str = typer.Option(default="unknown", help="Repo commit for the scorecards"),
    output_dir: str = typer.Option(default="", help="Output directory (defaults to results_dir)"),
) -> None:
    """Generate deterministic-first v2 scorecards for tool efficacy and quality retention."""
    from benchmarks.harness.models import RunRecord
    from benchmarks.harness.reporting import (
        generate_quality_retention_scorecard,
        generate_tool_efficacy_scorecard,
        render_quality_retention_json,
        render_quality_retention_markdown,
        render_tool_efficacy_json,
        render_tool_efficacy_markdown,
    )

    results_path = Path(results_dir)
    if not results_path.exists():
        typer.echo(f"generate-layered-scorecards: results directory not found: {results_path}", err=True)
        raise typer.Exit(1)

    runs: list[RunRecord] = []
    for run_file in sorted(results_path.rglob("run.json")):
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))
            runs.append(RunRecord.model_validate(data))
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"generate-layered-scorecards: skipping {run_file} ({exc})", err=True)

    if not runs:
        typer.echo("generate-layered-scorecards: no valid run records loaded", err=True)
        raise typer.Exit(1)

    if repo_commit == "unknown":
        commits = {r.repo_commit for r in runs if r.repo_commit}
        if len(commits) == 1:
            repo_commit = commits.pop()

    out_path = Path(output_dir) if output_dir else results_path
    out_path.mkdir(parents=True, exist_ok=True)

    tool_scorecard = generate_tool_efficacy_scorecard(runs, repo_commit=repo_commit)
    quality_scorecard = generate_quality_retention_scorecard(runs, repo_commit=repo_commit)

    (out_path / "tool-efficacy-scorecard.json").write_text(
        render_tool_efficacy_json(tool_scorecard),
        encoding="utf-8",
    )
    (out_path / "tool-efficacy-scorecard.md").write_text(
        render_tool_efficacy_markdown(tool_scorecard),
        encoding="utf-8",
    )
    (out_path / "quality-retention-scorecard.json").write_text(
        render_quality_retention_json(quality_scorecard),
        encoding="utf-8",
    )
    (out_path / "quality-retention-scorecard.md").write_text(
        render_quality_retention_markdown(quality_scorecard),
        encoding="utf-8",
    )
    typer.echo(f"generate-layered-scorecards: wrote layered scorecards to {out_path}")


@app.command("generate-html-report")
def generate_html_report(
    results_dir: str = typer.Argument(default="benchmarks/results", help="Results directory"),
    tasks_dir: str = typer.Option(
        default="benchmarks/tasks/cassandra/official",
        help="Directory containing task YAML manifests",
    ),
    output_path: str = typer.Option(
        default="",
        help="Output HTML file (defaults to <results_dir>/report.html)",
    ),
) -> None:
    """Generate a standalone HTML report from run.json files."""
    from benchmarks.harness.html_report import load_run_records, render_html_report

    results_path = Path(results_dir)
    if not results_path.exists():
        typer.echo(f"generate-html-report: results directory not found: {results_path}", err=True)
        raise typer.Exit(1)

    runs = load_run_records(results_path)
    if not runs:
        typer.echo(f"generate-html-report: no run.json files found under {results_path}", err=True)
        raise typer.Exit(1)

    html = render_html_report(
        runs,
        tasks_dir=Path(tasks_dir),
        source_results_dir=results_path,
    )

    out_path = Path(output_path) if output_path else results_path / "report.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    typer.echo(f"generate-html-report: loaded {len(runs)} runs")
    typer.echo(f"generate-html-report: wrote {out_path}")


@app.command("generate-layered-html-report")
def generate_layered_html_report(
    results_dir: str = typer.Argument(default="benchmarks/results", help="Results directory"),
    output_path: str = typer.Option(
        default="",
        help="Output HTML file (defaults to <results_dir>/layered-report.html)",
    ),
    repo_commit: str = typer.Option(default="unknown", help="Repo commit for the report"),
) -> None:
    """Generate a standalone HTML report for deterministic-first layered runs."""
    from benchmarks.harness.html_report import load_run_records, render_layered_html_report

    results_path = Path(results_dir)
    if not results_path.exists():
        typer.echo(f"generate-layered-html-report: results directory not found: {results_path}", err=True)
        raise typer.Exit(1)

    runs = load_run_records(results_path)
    if not runs:
        typer.echo(f"generate-layered-html-report: no run.json files found under {results_path}", err=True)
        raise typer.Exit(1)

    html = render_layered_html_report(
        runs,
        repo_commit=repo_commit,
        source_results_dir=results_path,
    )
    out_path = Path(output_path) if output_path else results_path / "layered-report.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    typer.echo(f"generate-layered-html-report: wrote {out_path}")


@app.command("generate-benchmark-overview")
def generate_benchmark_overview(
    results_dir: str = typer.Argument(
        default="benchmarks/results",
        help="Results directory used to place the overview page",
    ),
    output_path: str = typer.Option(
        default="",
        help="Output HTML file (defaults to <results_dir>/benchmark-overview.html)",
    ),
) -> None:
    """Generate a standalone HTML page that explains the benchmark."""
    from benchmarks.harness.benchmark_overview import write_benchmark_overview_html

    results_path = Path(results_dir)
    out_path = Path(output_path) if output_path else results_path / "benchmark-overview.html"
    write_benchmark_overview_html(out_path)

    typer.echo(f"generate-benchmark-overview: wrote {out_path}")


@app.command()
def validate_schemas(
    tasks_dir: str = typer.Option(
        default="benchmarks/tasks/cassandra/official",
        help="Directory containing task YAML manifests",
    ),
    results_dir: str = typer.Option(default="benchmarks/results", help="Results directory"),
) -> None:
    """Validate all task and run manifests against JSON schemas."""
    import jsonschema

    schemas_dir = Path("schemas")
    errors = 0

    task_schema_path = schemas_dir / "task.schema.json"
    task_v2_schema_path = schemas_dir / "task.v2.schema.json"
    legacy_task_schema = json.loads(task_schema_path.read_text()) if task_schema_path.exists() else None
    v2_task_schema = json.loads(task_v2_schema_path.read_text()) if task_v2_schema_path.exists() else None
    if legacy_task_schema or v2_task_schema:
        tasks_path = Path(tasks_dir)
        for task_file in sorted(tasks_path.glob("*.yaml")):
            try:
                raw = yaml.safe_load(task_file.read_text(encoding="utf-8"))
                schema = (
                    v2_task_schema
                    if isinstance(raw, dict) and (raw.get("schema_version") == 2 or raw.get("version") == "v2")
                    else legacy_task_schema
                )
                if schema is None:
                    raise RuntimeError("matching task schema not found")
                jsonschema.validate(raw, schema)
                typer.echo(f"  PASS  {task_file.name}")
            except jsonschema.ValidationError as exc:
                typer.echo(f"  FAIL  {task_file.name}: {exc.message}", err=True)
                errors += 1
            except Exception as exc:  # noqa: BLE001
                typer.echo(f"  ERROR {task_file.name}: {exc}", err=True)
                errors += 1

    # Validate run records
    run_schema_path = schemas_dir / "run.schema.json"
    results_path = Path(results_dir)
    if run_schema_path.exists() and results_path.exists():
        run_schema = json.loads(run_schema_path.read_text())
        for run_file in sorted(results_path.rglob("run.json")):
            try:
                raw = json.loads(run_file.read_text())
                jsonschema.validate(raw, run_schema)
                typer.echo(f"  PASS  {run_file}")
            except jsonschema.ValidationError as exc:
                typer.echo(f"  FAIL  {run_file}: {exc.message}", err=True)
                errors += 1
            except Exception as exc:  # noqa: BLE001
                typer.echo(f"  ERROR {run_file}: {exc}", err=True)
                errors += 1

    if errors:
        typer.echo(f"validate-schemas: {errors} error(s) found", err=True)
        raise typer.Exit(1)
    typer.echo("validate-schemas: all valid")


if __name__ == "__main__":
    app()
