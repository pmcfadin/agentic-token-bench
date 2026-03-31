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

## License

Apache 2.0
