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

**v2 redesign (active):** The authoritative direction for all new work is `docs/redesign.md`. This defines the layered benchmark methodology (deterministic first, LLM last), the v2 task model, phase-separated runner, new artifact types, and updated scorecard shape. Do not add features, tasks, or validators that contradict this design. When in doubt, re-read `docs/redesign.md` before writing code.

**v1 spec (legacy, preserved):** `docs/plans/2026-03-31-v1-build-plan-design.md` remains the reference for v1 behavior. v1 runs, manifests, and reports must stay readable and must not be broken by v2 changes. If v1 code disagrees with the v1 spec, treat it as a bug — but do not change v1 behavior to match v2 assumptions.

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
