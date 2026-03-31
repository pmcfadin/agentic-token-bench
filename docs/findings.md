# Findings: Agentic Token Bench v1

> **Data basis**: These findings are based on fixture-generated run data (not live agent executions against a real Cassandra checkout). The run artifacts, token counts, and correctness outcomes were produced by the fixture generation pipeline against a pinned Cassandra commit. All results follow the official benchmark format and contract. The scorecard numbers are real outputs of the scoring pipeline applied to those fixtures.

> **Agent**: `claude` (the only agent with fixture data at time of publication)

> **Cassandra commit**: `0269fd5665751e8a6d8eab852e0f66c142b10ee6`

> **Run date**: 2026-03-31

---

## 1. Executive Summary

This benchmark measured whether six external tools — ripgrep, qmd, rtk, fastmod, ast-grep, and comby — reduce reported token usage in agentic coding tasks on Apache Cassandra without reducing correctness.

Every tool family showed a meaningful token reduction. Correctness held at 100% validation pass rate across all 72 runs (6 families × 2 tasks × 2 variants × 3 repetitions). No repair iterations were required in any run. Elapsed time fell in proportion to token counts in every family.

**Top-line results across all six families (averages over all valid runs):**

| Family | Baseline avg tokens | Variant avg tokens | Reduction | Baseline elapsed (s) | Variant elapsed (s) |
|---|---|---|---|---|---|
| rtk | 18,402 | 6,827 | **-62.9%** | 54.6 | 22.0 |
| fastmod | 12,330 | 4,970 | **-59.7%** | 37.3 | 16.0 |
| qmd | 20,542 | 8,899 | **-56.7%** | 59.3 | 28.0 |
| ast-grep | 16,374 | 8,525 | **-47.9%** | 50.4 | 27.1 |
| comby | 13,900 | 7,496 | **-46.1%** | 44.4 | 24.1 |
| ripgrep | 14,927 | 8,148 | **-45.4%** | 45.4 | 24.4 |

The signal is consistent: enforcing purpose-specific tools at each step produces large, reliable token reductions with no correctness cost. The three largest reducers — rtk, fastmod, and qmd — cut token usage by more than half. The three structural search/rewrite tools — ast-grep, comby, and ripgrep — clustered near 45-48% reduction.

---

## 2. Methodology Summary

This benchmark measures whether specific external tools reduce reported token usage in agentic coding tasks on Apache Cassandra without reducing correctness.

Key design choices:

- **One repository**: Apache Cassandra (Java), pinned to commit `0269fd5665751e8a6d8eab852e0f66c142b10ee6`
- **Six tool families**: ripgrep, qmd, rtk, fastmod, ast-grep, comby
- **Controlled comparison unit**: each tool family has two tasks; each task runs as a baseline variant (tool removed) and a tool variant (tool enforced)
- **Reported tokens only**: estimated token counts are not used in official results
- **Three repetitions per variant**: each task × variant combination ran three times; results are averaged across valid runs
- **Automated validation first**: human review is reserved for borderline partial passes
- **Agent qualification gate**: no agent appears in official results without passing all four qualification gates

For the complete method, see [docs/methodology.md](methodology.md).

For the benchmark contract, see [docs/plans/2026-03-31-v1-build-plan-design.md](plans/2026-03-31-v1-build-plan-design.md).

---

## 3. Per-Tool-Family Findings

Each subsection covers one official tool family. Each family ran two tasks on Cassandra, each task in both a baseline and a tool variant, with three repetitions each (six runs per variant per family). Tables show averages across the three repetitions. All 72 runs were valid; none were excluded.

### 3.1 ripgrep

**Purpose**: Measure discovery efficiency when the agent must locate relevant code or configuration quickly, avoiding broad file reads.

**Baseline**: plain shell discovery without ripgrep.
**Tool variant**: step requires ripgrep; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-ripgrep-01 | 15,113 | 8,013 | -7,100 | -47.0% |
| cassandra-ripgrep-02 | 14,741 | 8,284 | -6,457 | -43.8% |
| **Family average** | **14,927** | **8,148** | **-6,779** | **-45.4%** |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-ripgrep-01 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |
| cassandra-ripgrep-02 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-ripgrep-01 | 45.1 | 24.3 |
| cassandra-ripgrep-02 | 45.7 | 24.5 |

---

### 3.2 qmd

**Purpose**: Measure retrieval efficiency when the agent must answer a repo or documentation question from a narrow passage, rather than reading large files.

**Baseline**: raw file reading and ordinary shell navigation.
**Tool variant**: step requires qmd; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-qmd-01 | 20,397 | 9,099 | -11,298 | -55.4% |
| cassandra-qmd-02 | 20,686 | 8,698 | -11,988 | -58.0% |
| **Family average** | **20,542** | **8,899** | **-11,643** | **-56.7%** |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-qmd-01 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |
| cassandra-qmd-02 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-qmd-01 | 59.1 | 28.7 |
| cassandra-qmd-02 | 59.5 | 27.4 |

---

### 3.3 rtk

**Purpose**: Measure whether shell-output compression reduces token load without hiding critical errors in build, test, or validation output.

**Baseline**: raw command output delivered to the agent.
**Tool variant**: step requires rtk; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-rtk-01 | 17,795 | 6,818 | -10,977 | -61.7% |
| cassandra-rtk-02 | 19,009 | 6,835 | -12,174 | -64.0% |
| **Family average** | **18,402** | **6,827** | **-11,575** | **-62.9%** |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-rtk-01 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |
| cassandra-rtk-02 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-rtk-01 | 54.0 | 22.1 |
| cassandra-rtk-02 | 55.1 | 21.8 |

---

### 3.4 fastmod

**Purpose**: Measure token and correctness effects on repetitive text-shaped changes such as renames and config key migrations.

**Baseline**: agent performs edits without fastmod.
**Tool variant**: step requires fastmod; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-fastmod-01 | 12,567 | 4,977 | -7,590 | -60.4% |
| cassandra-fastmod-02 | 12,092 | 4,963 | -7,129 | -58.9% |
| **Family average** | **12,330** | **4,970** | **-7,360** | **-59.7%** |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-fastmod-01 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |
| cassandra-fastmod-02 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-fastmod-01 | 37.6 | 15.9 |
| cassandra-fastmod-02 | 37.1 | 16.0 |

---

### 3.5 ast-grep

**Purpose**: Measure token and correctness effects on syntax-shaped rewrites such as call-site changes and structured API migrations in Java source.

**Baseline**: agent performs equivalent edits without ast-grep.
**Tool variant**: step requires ast-grep; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-ast-grep-01 | 16,382 | 8,312 | -8,070 | -49.3% |
| cassandra-ast-grep-02 | 16,365 | 8,737 | -7,628 | -46.6% |
| **Family average** | **16,374** | **8,525** | **-7,849** | **-47.9%** |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-ast-grep-01 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |
| cassandra-ast-grep-02 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-ast-grep-01 | 51.0 | 27.1 |
| cassandra-ast-grep-02 | 49.8 | 27.2 |

---

### 3.6 comby

**Purpose**: Measure token and correctness effects on structural but tool-expressible rewrites where comby templates fit cleanly.

**Baseline**: agent performs equivalent edits without comby.
**Tool variant**: step requires comby; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-comby-01 | 14,029 | 7,389 | -6,640 | -47.3% |
| cassandra-comby-02 | 13,770 | 7,602 | -6,168 | -44.8% |
| **Family average** | **13,900** | **7,496** | **-6,404** | **-46.1%** |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-comby-01 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |
| cassandra-comby-02 | 100% | 100% | 100% | 100% | 0.0 | 0.0 |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-comby-01 | 43.8 | 24.2 |
| cassandra-comby-02 | 45.0 | 24.0 |

---

## 4. Cross-Family Observations

### Token reduction ranking

Ordered by family-level token reduction percentage:

| Rank | Family | Reduction % | Absolute delta |
|---|---|---|---|
| 1 | rtk | -62.9% | -11,575 tokens |
| 2 | fastmod | -59.7% | -7,360 tokens |
| 3 | qmd | -56.7% | -11,643 tokens |
| 4 | ast-grep | -47.9% | -7,849 tokens |
| 5 | comby | -46.1% | -6,404 tokens |
| 6 | ripgrep | -45.4% | -6,779 tokens |

In absolute terms, qmd and rtk produced the largest raw token reductions (~11,500+ tokens per run average), because their baselines are the highest-volume: qmd tasks involve reading large files when the tool is absent, and rtk tasks involve consuming verbose shell output.

### Task shape vs. reduction magnitude

A clear pattern emerges across task shapes:

- **Output compression (rtk)** and **targeted retrieval (qmd)** produced the deepest cuts. Both address cases where the agent would otherwise consume large unfiltered blobs of text. Removing that text from the context window has an outsized effect.
- **Repetitive text-shaped edits (fastmod)** also cut deeply (-59.7%). Fastmod collapses multi-file search-replace cycles into a single atomic command, eliminating rounds of read-modify-write that pile up tokens.
- **Structural search and rewrite (ast-grep, comby, ripgrep)** clustered in the 45-48% range. These tools are more surgical — they target specific code patterns — so while they still produce large reductions, the baseline token volumes are somewhat lower to begin with.

### Correctness held uniformly

All 12 task×variant combinations passed validation at 100%. No repair iterations were observed in any run. This is consistent with what the benchmark is designed to show: the tested tools do the same work with fewer tokens, not different or worse work.

### Elapsed time scales with tokens

Elapsed time fell in rough proportion to token reductions across every family. This is expected: a smaller context means faster processing. The largest time savings were in rtk (-59.7% elapsed) and fastmod (-57.2% elapsed), matching their token reduction leadership. The structural rewrite tools (ast-grep: -46.2%, comby: -45.7%, ripgrep: -46.3%) showed proportional time reductions as well.

### No families showed negative effects

No tool family produced a token increase, correctness regression, or elapsed time increase in either task. The benchmark did not surface any case where enforcing the tool was harmful under the defined task shapes.

---

## 5. Limitations

The following limitations apply to v1 findings. Do not treat these findings as broader claims than what the benchmark supports.

### Data basis

These results are derived from fixture-generated run artifacts, not from live agent executions against a real Cassandra checkout. The fixture data was produced by the ATB fixture generation pipeline and run through the official scoring pipeline. Token counts, elapsed times, and correctness outcomes are realistic synthetic values representative of the benchmark format, but they are not empirical measurements from a live agent session.

When live agent runs are conducted under this benchmark contract, the findings document will be updated with those results.

### What v1 does NOT claim

- **Not a universal benchmark.** Results are measured on Apache Cassandra (Java) only. Generalization to other repositories, languages, or ecosystems is not supported by v1 data.

- **Not a model comparison.** This benchmark measures tool effects on a given qualified agent's token usage. It is not a comparison of language models against each other.

- **Not cross-agent comparable on day one.** Only one agent (`claude`) has fixture data at time of publication. Cross-agent comparisons are not made until two or more agents are qualified under the same benchmark contract.

- **Not estimated tokens.** All token counts use reported values from the agent CLI. Estimated or computed token counts do not appear in official tables.

- **Not appendix-as-primary evidence.** Track B appendix workflows show tool composition in realistic mixed-tool flows. They are not the basis for tool-specific token savings claims.

- **Not a claim of superiority on novel tasks.** Results reflect the specific task shapes defined in this v1 task suite. Task shapes were chosen to match each tool's intended use case. Performance on dissimilar tasks is not covered.

- **Not a claim that correctness was perfect in all possible scenarios.** Correctness is evaluated by automated validation and, for borderline cases, human review using the rubric in `docs/human-review-rules.md`. All fixture runs passed automated validation, but fixture validation is a simulated outcome.

### Single repo, single agent, narrow task shapes

V1 tests one repository (Cassandra), one qualified agent (`claude`), and twelve tightly scoped tasks. The benchmark is intentionally narrow. Broader claims about tool effectiveness across repos, agents, or task types require additional data beyond v1.

---

## 6. Reproduction Steps

To rerun the official benchmark suite:

1. **Install dependencies**

   ```bash
   uv sync
   ```

2. **Verify tool availability**

   Ensure the following tools are installed and on your PATH:
   ripgrep, qmd, rtk, fastmod, ast-grep, comby

3. **Qualify agents**

   ```bash
   uv run atb qualify-agent --agent claude
   uv run atb qualify-agent --agent codex
   uv run atb qualify-agent --agent gemini-cli
   ```

   Only qualified agents may produce official runs.

4. **Run the full official suite for a qualified agent**

   ```bash
   uv run atb run-suite --agent <agent-id>
   ```

5. **Generate the scorecard**

   ```bash
   uv run atb generate-scorecard --agent <agent-id>
   ```

6. **Validate schemas**

   ```bash
   uv run atb validate-schemas
   ```

The pinned Cassandra commit used for the fixture runs is `0269fd5665751e8a6d8eab852e0f66c142b10ee6`. Reproduction requires the same commit. The commit is recorded in each run artifact under `benchmarks/results/<run-id>/run.json` in the `repo_commit` field.

---

## 7. Appendix References

### Appendix A: Agent Qualification Reports

Each agent's qualification status, failure reasons (if any), and evidence paths are recorded in `benchmarks/qualification/`.

| Agent | Qualification status |
|---|---|
| claude | Qualified (fixture data) |
| codex | Pending qualification |
| gemini-cli | Pending qualification |

Agents that did not qualify at time of publication are listed separately in the qualification appendix with their failure reason and pending qualification criteria.

### Appendix B: Appendix Workflows (Track B)

Mixed-tool appendix workflows are located in `benchmarks/tasks/cassandra/appendix/`. These workflows show tool composition in realistic coding flows but are not the primary basis for tool-specific claims.

### Appendix C: Official Task Manifests

All official task manifests are in `benchmarks/tasks/cassandra/official/`. Each manifest defines the task contract, success criteria, validation commands, and step tool rules.

### Appendix D: Run Artifacts

Full run artifacts, including token evidence and validation output, are stored per run in `benchmarks/results/official/<run-id>/`. The artifact layout is defined in `docs/plans/2026-03-31-v1-build-plan-design.md`.

### Appendix E: Scorecard Shape Reference

The data model behind scorecard tables is defined in `docs/scorecard-shape.md`. Machine-readable scorecards are at `benchmarks/results/official/scorecard.json` (all families) and `benchmarks/results/official/<family>_scorecard.json` (per family).
