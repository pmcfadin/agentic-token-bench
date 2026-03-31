"""CLI for the agentic-token-bench benchmark harness."""

import typer

app = typer.Typer(
    name="atb",
    help="agentic-token-bench: benchmark token-saving tools in agentic coding workflows.",
)


@app.command()
def qualify_agent(agent: str = typer.Argument(help="Agent ID to qualify")) -> None:
    """Run qualification probes for an agent adapter."""
    typer.echo(f"qualify-agent: not yet implemented (agent={agent})")
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
