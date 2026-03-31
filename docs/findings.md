# Findings: Agentic Token Bench v1

> **This is a template, not final findings.**
> All data sections are marked `[PENDING: data from official runs]`.
> This file will be updated once official benchmark runs are complete and validated.

---

## 1. Executive Summary

[PENDING: data from official runs]

This section will summarize the top-line results across all six tool families on the Apache Cassandra benchmark. It will state which tools produced measurable token reductions, whether correctness held, and what the overall signal is for practitioners choosing among these tools.

---

## 2. Methodology Summary

This benchmark measures whether specific external tools reduce reported token usage in agentic coding tasks on Apache Cassandra without reducing correctness.

Key design choices:

- **One repository**: Apache Cassandra (Java), pinned to a single commit per official run set
- **Six tool families**: ripgrep, qmd, rtk, fastmod, ast-grep, comby
- **Controlled comparison unit**: each tool family has two tasks; each task runs as a baseline variant (tool removed) and a tool variant (tool enforced)
- **Reported tokens only**: estimated token counts are not used in official results
- **Automated validation first**: human review is reserved for borderline partial passes
- **Agent qualification gate**: no agent appears in official results without passing all four qualification gates

For the complete method, see [docs/methodology.md](methodology.md) (to be authored in Phase 3).

For the benchmark contract, see [docs/plans/2026-03-31-v1-build-plan-design.md](plans/2026-03-31-v1-build-plan-design.md).

---

## 3. Per-Tool-Family Findings

Each subsection below covers one official tool family. Each family ran two tasks on Cassandra, each task in both a baseline and a tool variant. Tables show averages across valid runs only. Invalid runs are excluded per the official run validity rules.

### 3.1 ripgrep

**Purpose**: Measure discovery efficiency when the agent must locate relevant code or configuration quickly, avoiding broad file reads.

**Baseline**: plain shell discovery without ripgrep.
**Tool variant**: step requires ripgrep; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-ripgrep-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-ripgrep-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-ripgrep-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-ripgrep-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-ripgrep-01 | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-ripgrep-02 | [PENDING: data from official runs] | [PENDING: data from official runs] |

---

### 3.2 qmd

**Purpose**: Measure retrieval efficiency when the agent must answer a repo or documentation question from a narrow passage, rather than reading large files.

**Baseline**: raw file reading and ordinary shell navigation.
**Tool variant**: step requires qmd; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-qmd-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-qmd-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-qmd-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-qmd-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-qmd-01 | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-qmd-02 | [PENDING: data from official runs] | [PENDING: data from official runs] |

---

### 3.3 rtk

**Purpose**: Measure whether shell-output compression reduces token load without hiding critical errors in build, test, or validation output.

**Baseline**: raw command output delivered to the agent.
**Tool variant**: step requires rtk; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-rtk-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-rtk-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-rtk-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-rtk-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-rtk-01 | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-rtk-02 | [PENDING: data from official runs] | [PENDING: data from official runs] |

---

### 3.4 fastmod

**Purpose**: Measure token and correctness effects on repetitive text-shaped changes such as renames and config key migrations.

**Baseline**: agent performs edits without fastmod.
**Tool variant**: step requires fastmod; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-fastmod-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-fastmod-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-fastmod-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-fastmod-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-fastmod-01 | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-fastmod-02 | [PENDING: data from official runs] | [PENDING: data from official runs] |

---

### 3.5 ast-grep

**Purpose**: Measure token and correctness effects on syntax-shaped rewrites such as call-site changes and structured API migrations in Java source.

**Baseline**: agent performs equivalent edits without ast-grep.
**Tool variant**: step requires ast-grep; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-ast-grep-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-ast-grep-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-ast-grep-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-ast-grep-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-ast-grep-01 | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-ast-grep-02 | [PENDING: data from official runs] | [PENDING: data from official runs] |

---

### 3.6 comby

**Purpose**: Measure token and correctness effects on structural but tool-expressible rewrites where comby templates fit cleanly.

**Baseline**: agent performs equivalent edits without comby.
**Tool variant**: step requires comby; tool is enforced via PATH restriction.

#### Token Comparison

| Task | Baseline avg tokens | Variant avg tokens | Token delta | Reduction % |
|---|---|---|---|---|
| cassandra-comby-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-comby-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Correctness

| Task | Baseline val pass rate | Variant val pass rate | Baseline 1st-pass rate | Variant 1st-pass rate | Baseline avg repairs | Variant avg repairs |
|---|---|---|---|---|---|---|
| cassandra-comby-01 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-comby-02 | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] | [PENDING: data from official runs] |

#### Time

| Task | Baseline avg elapsed (s) | Variant avg elapsed (s) |
|---|---|---|
| cassandra-comby-01 | [PENDING: data from official runs] | [PENDING: data from official runs] |
| cassandra-comby-02 | [PENDING: data from official runs] | [PENDING: data from official runs] |

---

## 4. Cross-Family Observations

[PENDING: data from official runs]

This section will compare results across all six families once official data is available. It will address questions such as:

- Which tool families produced the largest token reductions?
- Did any tool families show correctness regressions?
- Are there patterns by task shape (discovery vs. retrieval vs. transformation)?
- How does elapsed time shift compare to token savings?
- Are there families where the enforced tool showed no benefit or a negative effect?

---

## 5. Limitations

The following limitations apply to v1 findings. Do not treat these findings as broader claims than what the benchmark supports.

### What v1 does NOT claim

- **Not a universal benchmark.** Results are measured on Apache Cassandra (Java) only. Generalization to other repositories, languages, or ecosystems is not supported by v1 data.

- **Not a model comparison.** This benchmark measures tool effects on a given qualified agent's token usage. It is not a comparison of language models against each other.

- **Not cross-agent comparable on day one.** Agents appear in official results only after passing the qualification protocol. Until two or more agents are qualified under the same benchmark contract, cross-agent comparisons are not made.

- **Not estimated tokens.** All token counts use reported values from the agent CLI. Estimated or computed token counts do not appear in official tables.

- **Not appendix-as-primary evidence.** Track B appendix workflows show tool composition in realistic mixed-tool flows. They are not the basis for tool-specific token savings claims.

- **Not a claim of superiority on novel tasks.** Results reflect the specific task shapes defined in this v1 task suite. Task shapes were chosen to match each tool's intended use case. Performance on dissimilar tasks is not covered.

- **Not a claim that correctness was perfect.** Correctness is evaluated by automated validation and, for borderline cases, human review using the rubric in `docs/human-review-rules.md`. Validation gaps that were anticipated in a task definition are documented per task.

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
   uv run bench qualify-agent --agent claude
   uv run bench qualify-agent --agent codex
   uv run bench qualify-agent --agent gemini-cli
   ```

   Only qualified agents may produce official runs.

4. **Run the full official suite for a qualified agent**

   ```bash
   uv run bench run-suite --agent <agent-id>
   ```

5. **Generate the scorecard**

   ```bash
   uv run bench generate-scorecard --agent <agent-id>
   ```

6. **Validate schemas**

   ```bash
   uv run bench validate-schemas
   ```

The pinned Cassandra commit used for the official runs is recorded in each run artifact under `benchmarks/results/<run-id>/run.json` in the `repo_commit` field.

Reproduction requires the same Cassandra commit. The commit SHA used for the published findings will be listed here once official runs are complete.

[PENDING: data from official runs — pinned commit SHA and exact command invocation details]

---

## 7. Appendix References

### Appendix A: Agent Qualification Reports

Each agent's qualification status, failure reasons (if any), and evidence paths are recorded in `benchmarks/qualification/`.

| Agent | Qualification status |
|---|---|
| claude | [PENDING: data from official runs] |
| codex | [PENDING: data from official runs] |
| gemini-cli | [PENDING: data from official runs] |

Agents that did not qualify at time of publication are listed separately in the qualification appendix with their failure reason and pending qualification criteria.

### Appendix B: Appendix Workflows (Track B)

Mixed-tool appendix workflows are located in `benchmarks/tasks/cassandra/appendix/`. These workflows show tool composition in realistic coding flows but are not the primary basis for tool-specific claims.

[PENDING: data from official runs — appendix workflow results]

### Appendix C: Official Task Manifests

All official task manifests are in `benchmarks/tasks/cassandra/official/`. Each manifest defines the task contract, success criteria, validation commands, and step tool rules.

### Appendix D: Run Artifacts

Full run artifacts, including traces, token evidence, diffs, and validation output, are stored per run in `benchmarks/results/<run-id>/`. The artifact layout is defined in `docs/plans/2026-03-31-v1-build-plan-design.md`.

### Appendix E: Scorecard Shape Reference

The data model behind scorecard tables is defined in `docs/scorecard-shape.md`.
