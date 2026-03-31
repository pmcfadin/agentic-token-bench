# Reproduction Instructions

This document walks through everything needed to clone the repository, install dependencies, and run the benchmark suite end to end.

The benchmark targets macOS and Linux. Windows is not supported in v1.

---

## 1. Prerequisites

### Python and uv

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) for environment and dependency management

Install uv if you do not have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:

```bash
uv --version
python3 --version  # should be 3.12+
```

### System Tools

The benchmark enforces tool usage per step by placing wrappers on the `PATH`. The following tools must be installed and available on your system `PATH` before running the official suite.

| Tool | Purpose | Install |
|------|---------|---------|
| [ripgrep](https://github.com/BurntSushi/ripgrep) | Fast code search | `brew install ripgrep` / `apt install ripgrep` |
| [fastmod](https://github.com/facebookincubator/fastmod) | Fast text replacement | `brew install fastmod` / `cargo install fastmod` |
| [ast-grep](https://ast-grep.github.io/) | Syntax-aware search and replace | `brew install ast-grep` / `npm install -g @ast-grep/cli` |
| [comby](https://comby.dev/) | Structural code transformation | `brew install comby` / see comby.dev |
| [rtk](https://github.com/pmcfadin/rtk) | CLI output compression for agents | see project README |
| [qmd](https://github.com/pmcfadin/qmd) | Retrieval minimization for agents | see project README |

Verify each tool is on your `PATH`:

```bash
rg --version
fastmod --version
ast-grep --version
comby --version
rtk --version
qmd --version
```

### Agent CLI Dependencies

Agent CLI tools are required to run live benchmark runs against real agents. They are not needed to run tests or to use fixture data.

| Agent | CLI tool | Notes |
|-------|---------|-------|
| Claude | [claude](https://claude.ai/code) (Claude Code) | Requires Anthropic account |
| Codex | [codex](https://github.com/openai/codex) | Requires OpenAI account |
| Gemini CLI | [gemini](https://github.com/google-gemini/gemini-cli) | Optional; requires Google account |

For most reproduction purposes (tests, fixture data, scorecard generation) you do not need agent CLIs installed.

### Git

```bash
git --version  # any recent version
```

---

## 2. Environment Setup

```bash
git clone https://github.com/pmcfadin/agentic-token-bench.git
cd agentic-token-bench
uv sync
```

`uv sync` installs all Python dependencies into an isolated virtual environment. Run it again any time you update `pyproject.toml`.

Verify the CLI is available:

```bash
uv run atb --help
```

---

## 3. Running Tests

```bash
uv run pytest
```

This runs the full test suite under `tests/`. All tests should pass without any agent CLIs or external tools installed.

To run only smoke tests (faster, used in CI):

```bash
uv run pytest -m smoke
```

To lint and format:

```bash
uv run ruff check .
uv run ruff format .
```

---

## 4. Qualifying Agents

Before an agent can appear in official benchmark results it must pass all four qualification gates:

1. **Reported-token gate** — the CLI exposes stable reported token counts
2. **Forced-tool gate** — the agent works inside the constrained step environment
3. **Audit-trace gate** — enough observable output to reconstruct tool usage
4. **Run-completeness gate** — the harness can capture all required metrics without manual intervention

### Qualify a single agent

```bash
uv run atb qualify-agent claude
uv run atb qualify-agent codex
uv run atb qualify-agent gemini-cli
```

Each command writes a qualification record to `benchmarks/qualification/{agent}.json` and prints `PASS` or `FAIL`.

### Qualify all agents at once

```bash
uv run python scripts/run_qualification.py
```

This runs all three adapters and prints a summary table. It exits 0 only if all agents qualified.

Qualification records are written to `benchmarks/qualification/`. A qualified agent record looks like:

```json
{
  "agent_id": "claude",
  "adapter_version": "0.1.0",
  "qualified": true,
  "reported_token_support": true,
  "forced_tool_support": true,
  "trace_support": true,
  "run_completion_support": true,
  "failure_reason": null,
  "evidence_paths": []
}
```

If an agent does not qualify, the `failure_reason` field explains why. Non-qualified agents are kept in a separate qualification appendix and do not appear in official scorecards.

---

## 5. Running the Benchmark Suite

### List available tasks (no agent required)

```bash
uv run atb run-suite --agent claude --list-only
```

This loads and displays all task manifests from `benchmarks/tasks/cassandra/official/` without executing any runs.

### Run a single task

```bash
uv run atb run-task benchmarks/tasks/cassandra/official/<task>.yaml \
  --agent claude \
  --variant tool_variant
```

Use `--variant baseline` to run the baseline (tool removed) variant. Results are written to `benchmarks/results/<run-id>/`.

### Run a full family

```bash
uv run atb run-family ripgrep --agent claude
```

Note: `run-family` and `run-suite` full execution are not yet implemented. Use `run-task` for individual runs or use fixture data (see section 8).

### Official run matrix

The v1 official matrix for one qualified agent is:

- 6 tool families (ripgrep, qmd, rtk, fastmod, ast-grep, comby)
- 2 tasks per family
- 2 variants per task (baseline and tool_variant)
- 3 repetitions for stability

This yields 72 official runs per qualified agent.

---

## 6. Generating Scorecards

### From live run results

After completing runs, generate scorecards from everything under `benchmarks/results/`:

```bash
uv run atb generate-scorecard benchmarks/results \
  --agent-id claude \
  --repo-commit <commit-sha>
```

This writes:
- `benchmarks/results/scorecard.md` — human-readable summary table
- `benchmarks/results/scorecard.json` — machine-readable scorecard

### From fixture data

If you generated fixture runs first (see section 8), use the results directory from that run:

```bash
uv run atb generate-scorecard benchmarks/results/official \
  --agent-id claude \
  --repo-commit 0269fd5665751e8a6d8eab852e0f66c142b10ee6
```

Or use the dedicated script which also generates per-family scorecards:

```bash
uv run python scripts/generate_scorecards.py
```

Per-family scorecards are written as `benchmarks/results/official/{family}_scorecard.md` and `{family}_scorecard.json`.

---

## 7. Using Fixture Data

Fixture data lets you exercise scorecard generation and reporting without running live agent sessions. The fixture generator produces 72 realistic run records (6 families × 2 tasks × 2 variants × 3 repetitions) with token counts that reflect expected tool savings.

### Generate fixture runs

```bash
uv run python scripts/generate_fixture_runs.py
```

Runs are written to `benchmarks/results/official/`. The script also prints a per-family token variance analysis and an overall stability assessment.

You can specify an alternate output directory:

```bash
uv run python scripts/generate_fixture_runs.py /tmp/my-fixture-runs
```

### Generate scorecards from fixture data

```bash
uv run python scripts/generate_scorecards.py
```

Or point `atb generate-scorecard` at the fixture directory:

```bash
uv run atb generate-scorecard benchmarks/results/official \
  --agent-id claude \
  --repo-commit 0269fd5665751e8a6d8eab852e0f66c142b10ee6
```

This is the fastest way to verify the full pipeline without any installed agent CLIs.

### End-to-end fixture run (no agent CLI required)

```bash
# 1. Clone and install
git clone https://github.com/pmcfadin/agentic-token-bench.git
cd agentic-token-bench
uv sync

# 2. Run tests
uv run pytest

# 3. Generate fixture data
uv run python scripts/generate_fixture_runs.py

# 4. Generate scorecards
uv run python scripts/generate_scorecards.py

# 5. View results
cat benchmarks/results/official/scorecard.md
```

This sequence should complete in under 10 minutes on any modern machine.

---

## 8. Interpreting Results

### Scorecard format

Each scorecard table shows one row per tool family:

| Family | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % | Correctness |
|--------|--------------------|--------------------|-------------|-------------|-------------|
| ripgrep | 15,100 | 8,050 | -7,050 | 46.7% | pass |
| ... | | | | | |

- **Baseline avg tokens** — average reported total tokens across valid baseline runs for that family
- **Variant avg tokens** — average reported total tokens across valid tool-variant runs
- **Token delta** — variant minus baseline (negative means fewer tokens with the tool)
- **Reduction %** — percentage reduction from baseline
- **Correctness** — validation pass rate across valid runs

Only valid runs appear in official scorecards. A run is invalid if reported tokens are missing, tool enforcement was violated, or the trace is incomplete.

### Findings document

See [docs/findings.md](findings.md) for the full findings report including methodology notes, per-family analysis, and the official claim set.

### Raw run artifacts

Each run writes its artifacts to `benchmarks/results/<run-id>/`:

```
run.json             # run record with all metrics
trace.jsonl          # step-by-step event stream
prompt.txt           # canonical prompt delivered to the agent
final_answer.txt     # agent's final answer
validation.json      # validation command output
diff.patch           # file changes made by the agent
stdout.log           # agent stdout
stderr.log           # agent stderr
token_evidence.txt   # raw token count evidence
tool_invocations.jsonl  # per-tool invocation records
```

### Benchmark contract

The full benchmark specification and all locked decisions for v1 are in [docs/plans/2026-03-31-v1-build-plan-design.md](plans/2026-03-31-v1-build-plan-design.md). If any behavior in the harness disagrees with that document, treat it as a bug.
