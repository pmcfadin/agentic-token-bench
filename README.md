# agentic-token-bench

[![GitHub Stars](https://img.shields.io/github/stars/pmcfadin/agentic-token-bench?style=social)](https://github.com/pmcfadin/agentic-token-bench)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Do token-saving CLI tools actually work in agentic coding workflows?**

Every file read, search, or edit in an AI coding session stuffs full content into context — most of it noise. On a capped plan, that means hitting limits mid-task. The fix isn't a bigger plan; it's running a CLI tool first and handing the LLM only the result.

`agentic-token-bench` is an open benchmark that measures exactly how much each tool helps — with real before/after numbers on a real codebase. → **[Live results: patrickmcfadin.com/tokenmaxxing](https://patrickmcfadin.com/tokenmaxxing)**

---

## Results

Six CLI tools benchmarked against Apache Cassandra. All runs are deterministic — same input, same output, every time.

| Tool | Avg raw tokens | Avg reduced tokens | Reduction | Deterministic pass rate |
|------|---------------:|-------------------:|----------:|:-----------------------:|
| [qmd](https://github.com/tobi/qmd) | 24,437 | 188 | **99.2%** | 100% |
| [ripgrep](https://github.com/BurntSushi/ripgrep) | 1,043 | 48 | **95.4%** | 100% |
| [rtk](https://github.com/rtk-ai/rtk) | 12,284 | 648 | **94.7%** | 100% |
| [ast-grep](https://github.com/ast-grep/ast-grep) | 2,436 | 162 | **93.3%** | 100% |
| [comby](https://github.com/comby-tools/comby) | 1,879 | 308 | **83.6%** | 100% |
| [fastmod](https://github.com/facebookincubator/fastmod) | 2,436 | 850 | **65.1%** | 100% |

**No mocked results.** Every number above comes from running the actual tool against actual Cassandra source files and counting real tokens.

---

## Using the Tools

The numbers above are real. Here's how to put them to work.

**Before/after example — ripgrep:**
```
Without ripgrep: read every file in the directory → 1,043 tokens
With ripgrep:    rg -l read_repair_chance .       →    48 tokens   (95.4% reduction)
```

The LLM sees a list of file paths instead of every file's content. Same answer, 95% fewer tokens.

| Resource | What's inside |
|----------|--------------|
| [`docs/integration-guide.md`](docs/integration-guide.md) | All 6 tools: use cases, copy-paste commands, Claude Code / Codex / Gemini CLI setup |
| [`docs/agent-configs/`](docs/agent-configs/) | Paste-ready CLAUDE.md snippets, Codex PATH config, Gemini stream-json extraction |
| [`docs/agent-configs/README.md`](docs/agent-configs/README.md) | Quick-start and tool selection guide |
| [`docs/agent-internals/`](docs/agent-internals/) | Verified agent internals for Claude Code, Codex, and Gemini CLI |
| [`docs/tokenmax-install-spec.md`](docs/tokenmax-install-spec.md) | Installer contract and command behavior for `tokenmax` |

---

## Tokenmax Installer

`tokenmax` is the user-facing installer for wiring these tools into Claude Code, Codex, and Gemini CLI without hand-editing each config surface.

### Run it from this repo

The CLI lives in this repository today. From the repo root:

```bash
npm install
node bin/tokenmax.js doctor
node bin/tokenmax.js install all
```

You can also make the local executable available on your shell `PATH`:

```bash
npm link
tokenmax doctor
tokenmax install all
```

### Bootstrap scripts

This repo also ships thin bootstrap scripts for the future published package flow:

```bash
scripts/tokenmax/install.sh
scripts/tokenmax/install.ps1
```

Their job is intentionally small: verify `node` and `npm`, install `tokenmax`, print the version, and optionally run `tokenmax install all --yes`.

### Supported commands

```bash
tokenmax doctor
tokenmax status
tokenmax install all
tokenmax install claude
tokenmax install codex
tokenmax install gemini
tokenmax repair all
tokenmax uninstall all
```

Supported flags in v1:

```bash
--json
--yes
--dry-run
--force
```

### What `tokenmax install all` changes

`tokenmax` is configure-only in v1. It does **not** install `qmd`, `rtk`, `rg`, `ast-grep`, `comby`, or `fastmod`. It probes for those tools on `PATH`, warns on anything missing, and writes only the documented agent config that applies.

- Claude Code: manages a Tokenmax block in `~/.claude/CLAUDE.md`, generates `~/.claude/commands/tokenmax.md`, and writes the documented `rtk` hook to `~/.claude/settings.json` only when `rtk` is installed.
- Codex: manages a Tokenmax block in `~/.codex/AGENTS.md` and generates `~/.codex/skills/tokenmax/SKILL.md`.
- Gemini CLI: manages a Tokenmax block in `~/.gemini/GEMINI.md` and generates `~/.gemini/commands/tokenmax.toml`.

All managed edits are reversible. Tokenmax records state, backups, and manifests under `~/.tokenmax/`, and `tokenmax status` reports drift from the last successful install.

---

## The Pattern

The core idea: run a deterministic CLI tool first, LLM sees only the result.

```
Full file (24,437 tokens)  →  qmd get Gossiper.java:361 -l 24  →  Exact passage (188 tokens)
```

The LLM doesn't need the whole file to answer a question about one function. A good CLI tool returns exactly the slice it needs. This benchmark measures whether that's true in practice, and by how much.

---

## Methodology

The benchmark uses a **deterministic-first, layered** design. The LLM is the last resort, not the first instrument.

### Layer 1 — Tool efficacy (deterministic)

The tool runs against fixed input artifacts. The harness measures:

- **Raw bytes / tokens** — the input the LLM would have had to read unassisted
- **Reduced bytes / tokens** — the tool's output
- **Reduction ratio** — how much was cut
- **Deterministic pass rate** — whether the tool produced the correct output on every run

Deterministic checks validate the output directly: exact file paths, exact line ranges, exact rewrite counts, expected diffs. No LLM is involved in Layer 1.

### Layer 2 — Quality retention (LLM judge, small model)

After the tool runs, a small LLM is asked: *can the reduced artifact still answer the original question?* The judge scores both the raw artifact and the reduced artifact, producing:

- **Raw quality score** — can the LLM answer from the unfiltered input?
- **Reduced quality score** — can the LLM answer from the tool's output?
- **Quality delta** — the difference (negative means the tool output lost information)

The judge is a small model only. An expensive model is used only when a small model cannot resolve the question — and that escalation is recorded in the run artifact.

### Why two layers?

Token reduction is necessary but not sufficient. A tool that cuts 99% of tokens but also cuts the answer is not useful. Layer 1 measures efficiency; Layer 2 measures whether efficiency came at a correctness cost.

---

## Task Design

Each tool family has two tasks on Apache Cassandra at a pinned commit (`0269fd5`). Tasks are structured as:

```yaml
tool_invocation:
  tool_id: qmd
  args: [get, "src/java/org/apache/cassandra/gms/Gossiper.java:361", -l, "24"]
  output_artifact: reduced_output.txt

deterministic_checks:
  - name: exact_gossip_passage
    command: python scripts/validate_cassandra_v2_qmd.py --task cassandra-qmd-01-v2

quality_evaluation:
  question: >
    Return the exact source path, line range, and passage text that describes
    the gossip-round target-selection logic.
  small_model_allowed: true
  expensive_model_allowed: false
```

**Input artifacts are fixed.** Each task specifies fixture files — slices of Cassandra source — that are copied into a fresh workspace before each run. The workspace is reset between runs. Results are not sensitive to what's on disk outside the fixture set.

**Validators are exact.** Every family uses machine-checkable validation:

| Family | What the validator checks |
|--------|--------------------------|
| `qmd` | Exact source path, line range, and passage text |
| `ripgrep` | Exact set of matching file paths |
| `rtk` | Required signal tokens present; noise fields absent |
| `fastmod` | Exact replacement count; no remaining original strings |
| `ast-grep` | Exact AST-aware rewrite count; no unintended matches |
| `comby` | Exact structural replacement count; diff correctness |

No fuzzy scoring in Layer 1. A task either passes its deterministic checks or it doesn't.

---

## Tool Enforcement

For legacy agent runs, tool availability is enforced by the harness, not by instructions to the agent.

**PATH control.** The harness constructs a temporary directory with only the allowed tools on `PATH`. A tool that is not in the allowed set for a given step is physically absent — the agent cannot call it regardless of what it decides to do.

**Wrapper mediation.** Every tool is wrapped. The wrapper passes through stdout and stderr faithfully, and records a structured invocation event to `tool_invocations.jsonl` in the run artifact directory. Required-tool violations are detectable from the trace.

**Validity classification.** A run is invalid — and excluded from scorecards — if:

- Reported tokens are missing or could not be extracted
- A required tool was not actually invoked
- A blocked tool was invoked
- Validation commands did not execute

Invalid runs are recorded but never aggregated. The exclusion reason is written to the run record.

---

## Token Accounting

**Reported values only (for legacy agent runs).** The official token metric is the count reported by the agent CLI itself. Estimated or inferred counts are never used.

**Evidence files.** Every run artifact directory contains `token_evidence.txt` — the raw snippet from agent output from which token counts were extracted. Third parties can inspect this file to verify that reported counts come directly from agent output, not from estimation.

**v2 tool-only runs.** In deterministic-first v2 runs, token counts are measured by tokenizing the raw input artifact and the tool output artifact directly using the same tokenizer. No agent CLI is involved.

---

## Run Artifacts

Each run writes a directory under `benchmarks/results/` with:

```
cassandra-qmd-01-v2__tool_variant__tool_only__20260402-170617/
├── run.json                  # Full run record (schema in schemas/run.schema.json)
├── raw_input.txt             # The full input the LLM would have seen unassisted
├── reduced_output.txt        # The tool's output
├── tool_invocations.jsonl    # Structured tool invocation trace
├── validation.json           # Deterministic check results
└── token_evidence.txt        # Raw token count evidence (legacy agent runs)
```

Scorecards are generated from these artifacts:

```
benchmarks/results/
├── tool-efficacy-scorecard.json     # Layer 1 results (deterministic)
├── quality-retention-scorecard.json # Layer 2 results (LLM judge)
├── benchmark-data.json              # Compact export for the public results page
└── layered-report.html              # Full HTML report
```

---

## Running the Benchmark

### Prerequisites

```bash
# Python 3.12, managed by uv
uv sync

# Clone Cassandra at the pinned commit and index it
task setup
```

### Run all tools

```bash
task bench          # Runs all 12 v2 tool-only tasks
task report         # Generates scorecards and HTML report
task export-data    # Writes benchmark-data.json for the public page
```

### Run a single tool family

```bash
uv run atb run-tool-task benchmarks/tasks/cassandra/v2/cassandra-qmd-01.yaml --skip-checkout
uv run atb run-tool-task benchmarks/tasks/cassandra/v2/cassandra-qmd-02.yaml --skip-checkout
```

### Run quality evaluation (Layer 2)

```bash
uv run atb run-quality-eval benchmarks/tasks/cassandra/v2/cassandra-qmd-01.yaml \
  --agent claude --latest-run
```

### Generate reports

```bash
uv run atb generate-layered-scorecards
uv run atb generate-layered-html-report
```

---

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `benchmarks/harness/` | Core harness: runner, CLI, reporting, models |
| `benchmarks/tasks/cassandra/v2/` | v2 task manifests (YAML) |
| `benchmarks/tasks/cassandra/fixtures/` | Fixed input artifacts (Cassandra source slices) |
| `benchmarks/results/` | Run artifacts, scorecards, HTML report |
| `agents/` | Agent adapters (Claude, Codex, Gemini CLI) |
| `tools/` | Tool wrappers |
| `scripts/` | Per-family deterministic validators |
| `schemas/` | Public JSON schemas for tasks and run records |
| `docs/` | Methodology, findings, and design docs |

Key docs:

- [`docs/integration-guide.md`](docs/integration-guide.md) — how to use each tool with Claude Code, Codex, and Gemini CLI
- [`docs/agent-configs/`](docs/agent-configs/) — paste-ready CLAUDE.md snippets and agent-specific configs
- [`docs/methodology.md`](docs/methodology.md) — full v2 methodology spec
- [`docs/findings.md`](docs/findings.md) — v1 findings (ripgrep family, live agent runs)
- [`docs/redesign.md`](docs/redesign.md) — v2 design rationale and implementation plan
- [`docs/task-authoring-guide.md`](docs/task-authoring-guide.md) — how to write new tasks

---

## Limitations

**Not universal.** Results describe tool effects on Apache Cassandra under specific task shapes. The benchmark does not claim that token savings observed here generalize to other repositories, languages, task types, or agent configurations.

**One repository.** All v2 comparisons are on Cassandra at one pinned commit. Repository-level effects are not separated from tool effects.

**Reported tokens, not ground-truth tokens.** For legacy agent runs, the official metric is what the agent CLI reports. `token_evidence.txt` allows inspection but does not correct for agent-side reporting differences.

**v2 quality retention is early.** The quality-retention scorecard has 2 runs per family. The tool-efficacy scorecard has 8–18 runs per family. Quality scores should be read as directional, not definitive, at current run counts.

---

## Submit a Tool

Know a CLI tool that saves tokens in agentic coding workflows?

Criteria:
- Takes file or codebase input
- Produces smaller, targeted output (diff, filtered results, index)
- Deterministic — same input, same output, every time

**[Open an issue with the tool submission template →](https://github.com/pmcfadin/agentic-token-bench/issues/new?template=submit-tool.yml)**

---

## Tests

```bash
uv run pytest          # 466 tests
uv run ruff check .    # Lint
uv run ruff format .   # Format
```

## License

Apache 2.0
