# Findings: Agentic Token Bench Legacy v1

> **Data basis**: The ripgrep family results in this document are based on live
> agent executions across three agents (claude, codex, gemini-cli) against a
> real Cassandra checkout. Claude ran 12 runs (3 repetitions x 2 tasks x 2
> variants). Codex and Gemini CLI each ran 4 runs (1 repetition x 2 tasks x 2
> variants). The remaining five tool families (qmd, rtk, fastmod, ast-grep,
> comby) have not yet completed live runs; their sections are retained from the
> legacy v1 fixture baseline and are marked accordingly.

> **Agents with live data**: `claude` (12 runs), `codex` (4 runs), `gemini-cli` (4 runs)

> **Cassandra commit**: `0269fd5665751e8a6d8eab852e0f66c142b10ee6`

> **Run date**: 2026-04-01

---

## 1. Executive Summary

This legacy v1 benchmark measured whether six external tools — ripgrep, qmd,
rtk, fastmod, ast-grep, and comby — reduce reported token usage in agentic
coding tasks on Apache Cassandra without reducing correctness.

**Current status**: Live benchmark runs have been completed for the ripgrep
family only, across three agents. The remaining five families are pending live
runs. The ripgrep results are the first empirical data from real agent
executions under the legacy end-to-end benchmark contract. V2 will keep the
same families but split deterministic tool efficacy from downstream quality
retention.

### ripgrep family: live results across three agents

The ripgrep family shows meaningful token and time reductions for Claude and Codex. Gemini CLI results are partially usable — ripgrep-02 ran cleanly, but ripgrep-01 baseline produced a token count of 0 due to a token extraction bug (see issue #46); that run is excluded from the Claude-comparable summary.

**Claude (12 runs, 3 repetitions per variant):**

| Task | Baseline avg tokens | Variant avg tokens | Reduction | Baseline elapsed (s) | Variant elapsed (s) |
|---|---|---|---|---|---|
| ripgrep-01 | ~1,759 | ~1,982 | +12.8% | ~111 | ~100 |
| ripgrep-02 | ~2,731 | ~1,938 | -29.0% | ~165 | ~66 |
| **Family average** | **~2,245** | **~1,960** | **-12.7%** | **~138.5** | **~83.2** |

**Codex (4 runs, 1 repetition per variant):**

| Task | Baseline tokens | Variant tokens | Reduction | Baseline elapsed (s) | Variant elapsed (s) |
|---|---|---|---|---|---|
| ripgrep-01 | 276,568 | 38,213 | -86.2% | 1,377 | 364 |
| ripgrep-02 | 82,758 | 48,040 | -41.9% | 178 | 157 |
| **Family average** | **~179,663** | **~43,127** | **-76.0%** | **~778** | **~261** |

**Gemini CLI (4 runs, 1 repetition per variant):**

| Task | Baseline tokens | Variant tokens | Reduction | Baseline elapsed (s) | Variant elapsed (s) |
|---|---|---|---|---|---|
| ripgrep-01 | 0 (extraction bug — see issue #46) | 1,542,880 | n/a | 1,494 | 489 |
| ripgrep-02 | 59,702 | 68,144 | +14.1% | 113 | 85 |

> **Note on Gemini ripgrep-01 baseline**: The 0-token reading is a known extraction defect, not a real measurement. The token count for that run cannot be used for comparison. Issue #46 tracks the fix.

**Top-line observations:**
- Codex shows the largest ripgrep reductions by far: -86.2% on ripgrep-01, consistent with Codex's much higher absolute token volumes at baseline.
- Claude shows a modest family-average reduction (-12.7%) with high variance between tasks: ripgrep-01 saw a small token *increase* in the tool variant, while ripgrep-02 showed a meaningful -29% reduction.
- Gemini CLI data is incomplete due to the extraction bug; ripgrep-02 alone shows a small token increase (+14.1%) in the tool variant.
- Time savings are substantial across all agents where measurement is valid: Claude -40%, Codex -66%.

**Pending (not yet measured with live runs):**

| Family | Status |
|---|---|
| qmd | Not yet measured |
| rtk | Not yet measured |
| fastmod | Not yet measured |
| ast-grep | Not yet measured |
| comby | Not yet measured |

---

## 2. Methodology Summary

This legacy benchmark measures whether specific external tools reduce reported
token usage in agentic coding tasks on Apache Cassandra without reducing
correctness.

Key design choices:

- **One repository**: Apache Cassandra (Java), pinned to commit `0269fd5665751e8a6d8eab852e0f66c142b10ee6`
- **Six tool families**: ripgrep, qmd, rtk, fastmod, ast-grep, comby
- **Controlled comparison unit**: each tool family has two tasks; each task runs as a baseline variant (tool removed) and a tool variant (tool enforced)
- **Reported tokens only**: estimated token counts are not used in official results
- **Three repetitions per variant (target)**: each task × variant combination targets three repetitions; single-rep runs are noted where only one repetition was available
- **Automated validation first**: human review is reserved for borderline partial passes
- **Agent qualification gate**: no agent appears in official results without passing all four qualification gates

The v2 methodology keeps the same families but changes the official reading of
those runs: tool efficacy is measured first, and downstream quality retention is
reported separately when an LLM judge is needed.

For the complete method, see [docs/methodology.md](methodology.md).

For the benchmark contract, see [docs/plans/2026-03-31-v1-build-plan-design.md](plans/2026-03-31-v1-build-plan-design.md).

---

## 3. Per-Tool-Family Findings

Each subsection covers one official tool family. Section 3.1 contains live data. Sections 3.2–3.6 are retained from the v1 fixture baseline and are labeled as such — they will be replaced with live data as runs complete.

### 3.1 ripgrep

**Purpose**: Measure discovery efficiency when the agent must locate relevant code or configuration quickly, avoiding broad file reads.

**Baseline**: plain shell discovery without ripgrep.
**Tool variant**: step requires ripgrep; tool is enforced via PATH restriction.

**Data source**: Live runs — claude 12 runs (3 reps), codex 4 runs (1 rep), gemini-cli 4 runs (1 rep).

#### Token Comparison — Claude (3 repetitions per variant)

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-ripgrep-01 | ~1,759 | ~1,982 | +223 | +12.8% |
| cassandra-ripgrep-02 | ~2,731 | ~1,938 | -793 | -29.0% |
| **Family average** | **~2,245** | **~1,960** | **-285** | **-12.7%** |

#### Token Comparison — Codex (1 repetition per variant)

| Task | Baseline tokens | Variant tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-ripgrep-01 | 276,568 | 38,213 | -238,355 | -86.2% |
| cassandra-ripgrep-02 | 82,758 | 48,040 | -34,718 | -41.9% |
| **Family average** | **~179,663** | **~43,127** | **-136,537** | **-76.0%** |

#### Token Comparison — Gemini CLI (1 repetition per variant)

| Task | Baseline tokens | Variant tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-ripgrep-01 | 0 (extraction bug — issue #46) | 1,542,880 | n/a | n/a |
| cassandra-ripgrep-02 | 59,702 | 68,144 | +8,442 | +14.1% |

#### Time Comparison — Claude

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) | Time delta |
|---|---|---|---|
| cassandra-ripgrep-01 | ~111 | ~100 | -10% |
| cassandra-ripgrep-02 | ~165 | ~66 | -60% |
| **Family average** | **~138.5** | **~83.2** | **-40%** |

#### Time Comparison — Codex

| Task | Baseline elapsed (s) | Variant elapsed (s) | Time delta |
|---|---|---|---|
| cassandra-ripgrep-01 | 1,377 | 364 | -74% |
| cassandra-ripgrep-02 | 178 | 157 | -12% |
| **Family average** | **~778** | **~261** | **-66%** |

#### Time Comparison — Gemini CLI

| Task | Baseline elapsed (s) | Variant elapsed (s) | Time delta |
|---|---|---|---|
| cassandra-ripgrep-01 | 1,494 | 489 | -67% |
| cassandra-ripgrep-02 | 113 | 85 | -25% |

#### Known Issues

**Gemini ripgrep-01 baseline token count is 0**: The token extraction pipeline returned 0 for the Gemini CLI ripgrep-01 baseline run. This is a known defect in the Gemini token extraction path, tracked as issue #46. That data point cannot be used for comparison and is excluded from reduction calculations. The fix is pending.

---

### 3.2–3.6 Legacy Fixture Families

The following five tool families have task definitions and validation scripts
ready but have not yet completed live runs. They remain in this document as
legacy fixture baselines until v2 live runs replace them.

| Family | Category | Purpose |
|---|---|---|
| qmd | retrieval | Measure retrieval efficiency from narrow doc passages vs. broad file reads |
| rtk | compression | Measure whether shell-output compression reduces token load |
| fastmod | transformation | Measure token effects on repetitive text-shaped changes (renames, config migrations) |
| ast-grep | transformation | Measure token effects on syntax-shaped rewrites (call-site changes, API migrations) |
| comby | transformation | Measure token effects on structural rewrites using comby templates |

Each family follows the same controlled comparison: baseline (tool removed from PATH) vs. tool variant (tool enforced via PATH).

---

## 4. Cross-Family Observations

The following observations are based on the ripgrep family only. Cross-family synthesis will be added as remaining families complete live runs.

### Agent scale differences are large

The most striking finding from the ripgrep live runs is the scale difference between agents. Codex baseline tokens (82K–277K per run) are 30–150x higher than Claude baseline tokens (1.7K–2.7K per run). This means percentage reductions are not directly comparable across agents — a -86% reduction for Codex represents a far larger absolute savings than a -29% reduction for Claude.

### Tool variant effect is task-dependent for Claude

Claude's ripgrep results show high task-level variance: ripgrep-01 saw a small token *increase* (+12.8%) in the tool variant, while ripgrep-02 showed a meaningful reduction (-29%). The family average (-12.7%) masks this split. The task shapes differ in ways that matter: ripgrep-01 may involve a discovery pattern where the tool variant's overhead (tool invocation, structured output parsing) slightly outweighs the reduction from avoiding broad reads.

### Gemini CLI data is incomplete

Only one of the two Gemini ripgrep tasks produced usable token data at this time (ripgrep-02). The ripgrep-01 baseline extraction bug (issue #46) prevents a valid comparison for that task. Conclusions about Gemini CLI ripgrep performance should wait for issue #46 to be resolved and that run to be re-executed.

### Time savings are more consistent than token savings

Elapsed time reductions were more uniform than token reductions across agents and tasks. Claude saved 40% of elapsed time at the family level; Codex saved 66%. Even where token counts did not fall, time often did — suggesting that tool-variant tasks complete faster regardless of whether they produce fewer tokens, possibly because the tool handles the work more directly.

---

## 5. Limitations

The following limitations apply to current findings.

### Only one tool family has live data

Only the ripgrep family has been run with live agents. Five families (qmd, rtk, fastmod, ast-grep, comby) have not yet completed live runs. Any cross-family comparisons in this document would be premature.

### Single repetition for Codex and Gemini CLI

Claude ran 3 repetitions per variant (the full target), giving averaged results. Codex and Gemini CLI each ran only 1 repetition per variant. Single-rep results have higher variance and should be interpreted with appropriate uncertainty.

### Gemini CLI token extraction bug

The Gemini CLI ripgrep-01 baseline run returned 0 tokens due to a token extraction defect (issue #46). This affects the completeness of Gemini CLI results until the bug is fixed and the run is re-executed.

### What legacy v1 does NOT claim

- **Not a universal benchmark.** Results are measured on Apache Cassandra (Java) only. Generalization to other repositories, languages, or ecosystems is not supported by legacy v1 data.

- **Not a model comparison.** This benchmark measures tool effects on a given qualified agent's token usage. It is not a comparison of language models against each other.

- **Not estimated tokens.** All token counts use reported values from the agent CLI. Estimated or computed token counts do not appear in official tables.

- **Not a claim of superiority on novel tasks.** Results reflect the specific task shapes defined in this legacy v1 task suite. Task shapes were chosen to match each tool's intended use case. Performance on dissimilar tasks is not covered.

### Single repo, narrow task shapes

Legacy v1 tests one repository (Cassandra) and two tightly scoped ripgrep tasks
(with ten more task pairs pending across five families). The benchmark is
intentionally narrow. Broader claims about tool effectiveness across repos,
agents, or task types require additional data beyond what is currently
available.

---

## 6. Reproduction Steps

To rerun the legacy benchmark suite:

1. **Install dependencies**

   ```bash
   uv sync
   ```

2. **Verify tool availability**

   For legacy v1 (ripgrep family only): ensure `rg` (ripgrep) is installed.
   For the full suite: ripgrep, qmd, rtk, fastmod, ast-grep (sg), comby.

3. **Qualify an agent**

   ```bash
   uv run atb qualify-agent claude
   ```

   Supported agents: `claude`, `codex`, `gemini-cli`. Only qualified agents may produce official runs.

4. **Run the ripgrep family**

   ```bash
   uv run atb run-family ripgrep --agent claude
   ```

   Or run the full official suite: `uv run atb run-suite --agent claude`

5. **Generate per-agent scorecards**

   ```bash
   uv run atb generate-scorecard benchmarks/results
   ```

   This auto-detects agents and writes per-agent scorecards (e.g. `scorecard-claude.json`).

6. **Generate the HTML report**

   ```bash
   uv run atb generate-html-report benchmarks/results
   ```

The pinned Cassandra commit used for runs is `0269fd5665751e8a6d8eab852e0f66c142b10ee6`. Reproduction requires the same commit. The commit is recorded in each run artifact under `benchmarks/results/<run-id>/run.json` in the `repo_commit` field.

---

## 7. Appendix References

### Appendix A: Agent Qualification Reports

Each agent's qualification status, failure reasons (if any), and evidence paths are recorded in `benchmarks/qualification/`.

| Agent | Qualification status |
|---|---|
| claude | Qualified (live runs) |
| codex | Qualified (live runs) |
| gemini-cli | Qualified (live runs; token extraction bug #46 is a known issue, not a disqualifying defect) |

### Appendix B: Appendix Workflows (Track B)

Mixed-tool appendix workflows are located in `benchmarks/tasks/cassandra/appendix/`. These workflows show tool composition in realistic coding flows but are not the primary basis for tool-specific claims.
They are legacy appendix evidence, not the official v2 methodology.

### Appendix C: Official Task Manifests

All official task manifests are in `benchmarks/tasks/cassandra/official/`. Each manifest defines the task contract, success criteria, validation commands, and step tool rules.

### Appendix D: Run Artifacts

Full run artifacts, including token evidence and validation output, are stored per run in `benchmarks/results/official/<run-id>/`. The artifact layout is defined in `docs/plans/2026-03-31-v1-build-plan-design.md`.

### Appendix E: Scorecard Shape Reference

The data model behind scorecard tables is defined in `docs/scorecard-shape.md`. Machine-readable scorecards are at `benchmarks/results/official/scorecard.json` (all families) and `benchmarks/results/official/<family>_scorecard.json` (per family).
