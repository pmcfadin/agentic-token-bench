# agentic-token-bench

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Do token-saving tools actually work in agentic coding workflows?**

`agentic-token-bench` is an open benchmark that measures whether external tools reduce token usage when AI coding agents work on real codebases — without reducing correctness.

## Key Findings (v1 — ripgrep family)

We ran three AI agents (Claude, Codex, Gemini CLI) on identical code-discovery tasks against Apache Cassandra, with and without ripgrep.

| Agent | Token Reduction | Time Reduction | Runs |
|-------|----------------|----------------|------|
| **Codex** | **-76.0%** | -66% | 4 |
| **Claude** | **-12.7%** | -40% | 12 |
| **Gemini CLI** | partial data | -46% | 4 |

Codex showed massive savings; Claude showed modest but consistent improvement. Full results with per-task breakdowns in [docs/findings.md](docs/findings.md).

## How It Works

1. **Task manifests** define coding tasks on a pinned Cassandra checkout
2. **PATH enforcement** controls which tools the agent can use (baseline removes the tool; variant enforces it)
3. **Agent adapters** run Claude, Codex, or Gemini CLI and extract reported token counts
4. **Automated validation** checks the agent's answer against expected results
5. **Per-agent scorecards** compare baseline vs. tool-variant performance

No Docker required — PATH-based isolation is sufficient and reproducible.

## Quick Start

### View results

Browse the [HTML report](benchmarks/results/report.html) or read [docs/findings.md](docs/findings.md).

### Regenerate from existing data

```bash
git clone https://github.com/pmcfadin/agentic-token-bench.git
cd agentic-token-bench
uv sync
uv run atb generate-scorecard benchmarks/results
uv run atb generate-html-report benchmarks/results
```

### Run your own benchmarks

```bash
uv sync

# Qualify an agent
uv run atb qualify-agent claude

# Run the ripgrep family (baseline + tool_variant for each task)
uv run atb run-family ripgrep --agent claude

# Generate per-agent scorecards
uv run atb generate-scorecard benchmarks/results
```

Supported agents: `claude`, `codex`, `gemini-cli`. See [docs/findings.md](docs/findings.md) for full reproduction steps.

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `benchmarks/harness/` | Core harness: runner, CLI, reporting |
| `benchmarks/tasks/` | Task manifests (YAML) |
| `benchmarks/results/` | Run artifacts and scorecards |
| `agents/` | Agent adapters (Claude, Codex, Gemini CLI) |
| `tools/` | Tool wrappers (ripgrep, rtk, fastmod, qmd, ast-grep, comby) |
| `docs/` | Methodology, findings, and design docs |

## v1 Scope

- **Repository**: Apache Cassandra (Java), pinned commit
- **Tool family tested**: ripgrep (code discovery)
- **Agents tested**: Claude, Codex, Gemini CLI
- **Pending families**: qmd, rtk, fastmod, ast-grep, comby (task definitions ready, live runs planned for v2)

## Tests

```bash
uv run pytest          # 767 tests
uv run ruff check .    # Lint
```

## License

Apache 2.0
