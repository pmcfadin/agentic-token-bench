"""CLI for the agentic-token-bench benchmark harness."""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(
    name="atb",
    help="agentic-token-bench: benchmark token-saving tools in agentic coding workflows.",
)

_QUAL_DIR = Path("benchmarks/qualification")
_ADAPTER_VERSION = "0.1.0"

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
    task: str = typer.Argument(help="Task ID to run"),
    agent: str = typer.Option(help="Agent ID"),
    variant: str = typer.Option(default="tool_variant", help="baseline or tool_variant"),
) -> None:
    """Run a single benchmark task."""
    typer.echo(f"run-task: not yet implemented (task={task}, agent={agent}, variant={variant})")
    raise typer.Exit(1)


@app.command()
def run_family(
    family: str = typer.Argument(help="Tool family to run"),
    agent: str = typer.Option(help="Agent ID"),
) -> None:
    """Run all tasks for a tool family."""
    typer.echo(f"run-family: not yet implemented (family={family}, agent={agent})")
    raise typer.Exit(1)


@app.command()
def run_suite(agent: str = typer.Option(help="Agent ID")) -> None:
    """Run the full official benchmark suite."""
    typer.echo(f"run-suite: not yet implemented (agent={agent})")
    raise typer.Exit(1)


@app.command()
def generate_scorecard(
    results_dir: str = typer.Argument(default="benchmarks/results", help="Results directory"),
) -> None:
    """Generate scorecards from benchmark results."""
    typer.echo(f"generate-scorecard: not yet implemented (results_dir={results_dir})")
    raise typer.Exit(1)


@app.command()
def validate_schemas() -> None:
    """Validate all task and run manifests against JSON schemas."""
    typer.echo("validate-schemas: not yet implemented")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
