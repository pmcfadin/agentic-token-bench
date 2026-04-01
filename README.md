# agentic-token-bench

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Measure, route, and package the tools that make agentic coding cheaper and sharper.**

`agentic-token-bench` is an open benchmark and plugin framework for measuring how external tools reduce token usage in agentic programming workflows without reducing correctness.

## Status

Under active development. See [docs/plans/](docs/plans/) for the current implementation plan.

## What This Project Does

Benchmarks and packages tools that reduce token waste across the full agent loop:

- **Retrieval minimization** (qmd)
- **CLI output compression** (rtk)
- **Mechanical transformations** (fastmod, ast-grep, comby)
- **Repo discovery** (ripgrep)

V1 focuses on Apache Cassandra as the benchmark repository, with controlled single-tool task families and enforced tool usage.

## Quick Start

```bash
uv sync
uv run atb --help
```

## Reproduction

Full reproduction instructions are in [docs/reproduction.md](docs/reproduction.md).

**Short path (no agent CLI required):**

```bash
git clone https://github.com/pmcfadin/agentic-token-bench.git
cd agentic-token-bench
uv sync
uv run pytest
uv run python scripts/generate_fixture_runs.py
uv run python scripts/generate_scorecards.py
uv run atb generate-benchmark-overview benchmarks/results
uv run atb generate-html-report benchmarks/results
cat benchmarks/results/official/scorecard.md
```

This exercises the full pipeline using fixture data and completes in under 10 minutes.

**To run against a live agent**, you also need the agent CLI installed and at least one agent qualified:

```bash
uv run atb qualify-agent claude
uv run atb run-task benchmarks/tasks/cassandra/official/<task>.yaml \
  --agent claude --variant tool_variant
uv run atb generate-scorecard benchmarks/results --agent-id claude
```

See [docs/reproduction.md](docs/reproduction.md) for prerequisites, tool installation, agent qualification, and result interpretation.

## License

Apache 2.0
