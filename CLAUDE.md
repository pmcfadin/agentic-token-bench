# agentic-token-bench

Benchmark framework for measuring token-saving tools in agentic coding workflows.

## Stack

- Python 3.12, managed by `uv`
- `typer` for CLI, `pydantic` for models, `pytest` for tests
- DuckDB for result aggregation
- YAML for task manifests, JSONL for event streams and traces

## Commands

```bash
uv sync                    # Install dependencies
uv run pytest              # Run tests
uv run ruff check .        # Lint
uv run ruff format .       # Format
uv run atb --help          # CLI help
```

## Implementation Contract

The authoritative implementation spec is `docs/plans/2026-03-31-v1-build-plan-design.md`. If code disagrees with that document, treat it as a bug.

## Conventions

- Schemas under `schemas/` are public contracts. Pydantic models may be richer but must serialize to the public schema.
- All CLI commands live in `benchmarks/harness/cli.py`.
- No Windows support in v1.
- Run `uv sync` after changing `pyproject.toml`.

## Directory Ownership

| Directory | Owner |
|-----------|-------|
| `benchmarks/harness/`, `agents/`, `schemas/` | Pod A (harness & adapters) |
| `benchmarks/tasks/`, `benchmarks/repos/` | Pod B (tasks & validation) |
| `tools/` | Pod C (tool wrappers) |
| `charts/`, findings docs | Pod D (reporting) |
