# Suite Redesign Plan: Deterministic First, LLM Last

## Summary
Redesign the benchmark so the official suite measures tool value before LLM behavior. The new official methodology will be layered:

- Layer 1: deterministic tool execution and artifact validation
- Layer 2: downstream quality-loss evaluation using an LLM only when deterministic checks cannot answer the question
- Layer 3: legacy end-to-end agent workflows retained as appendix experiments, not official evidence

This will land as a phased replacement. The current v1 suite remains runnable and historically intact while v2 is built in parallel. The default policy for the new suite is: deterministic checks first, small-model evaluation only for ambiguity, expensive-model evaluation only as a last resort.

## Implementation Changes
### 1. Redefine the benchmark contract
- Publish a new methodology spec that changes the unit of comparison from “full agent run with and without a tool” to “tool-produced artifact and its downstream usability.”
- Keep the six existing families and Cassandra as the anchor repo.
- Define two official score dimensions for every family:
  - tool efficacy: token/byte reduction plus family-specific deterministic validity
  - downstream quality retention: whether the reduced artifact still supports the correct answer or action
- Demote end-to-end agent workflows to a legacy appendix track. They remain useful for realism, but they are no longer the official attribution mechanism.
- Stop treating reported agent tokens as the single universal primary metric. They remain important where applicable, but the primary metric becomes family-specific.

### 2. Introduce a v2 task model
- Add a versioned task schema rather than mutating the current manifest shape in place.
- New task manifests must define:
  - input artifact(s) and fixture source
  - tool invocation contract
  - deterministic preservation/correctness checks
  - optional downstream evaluation question(s)
  - evaluator policy: deterministic only, small model allowed, expensive model allowed only on escalation
- Preserve v1 manifests unchanged so historical runs and docs remain valid.
- Update the task-authoring guide to make “LLM adds unique value here” an explicit requirement for any evaluation stage.

### 3. Split the harness into phases
- Refactor the runner so a benchmark run can have distinct phases instead of a single agentic step chain.
- Add three execution modes:
  - `tool-only`: run the benchmarked tool or wrapper against fixed input artifacts
  - `quality-eval`: evaluate raw vs reduced artifacts using deterministic checks first, optional LLM judge second
  - `legacy-agent`: current v1-style end-to-end workflow, explicitly labeled legacy
- Keep the current agent adapters for legacy mode and for the downstream judge stage only.
- Remove prompts from the primary tool-execution path. Prompts should exist only for the judge stage or legacy mode.
- Extend validation so it can validate tool outputs directly instead of validating an agent conversation transcript.

### 4. Expand run artifacts and data model
- Extend the run model so one run can record multiple phases and multiple metric classes.
- Add new artifact types:
  - raw input artifact snapshot
  - reduced/tool output artifact
  - preservation manifest listing required signals
  - deterministic validation results
  - optional judge prompt, judge output, and judge rationale
- Add new metrics to run records:
  - raw bytes and reduced bytes
  - raw tokens and reduced tokens when measurable
  - compression/reduction ratio
  - deterministic pass/fail for signal preservation or rewrite correctness
  - downstream quality score
  - quality delta between raw and reduced artifacts
  - LLM call count by class: none, small, expensive
  - escalation reason when expensive evaluation was used
- Keep legacy run fields readable and supported in aggregation/reporting.

### 5. Redesign family methodology
- `rtk`
  - Rewrite completely.
  - Primary benchmark: compress noisy log/output and verify deterministic preservation of sentinel signals, failure lines, stack traces, or required anchors.
  - Secondary benchmark: ask a downstream evaluator to answer the failure-identification question from the compressed artifact and compare that answer against the raw-artifact answer.
  - Remove “compress and interpret in the same official LLM-heavy step” from the official suite.
- `qmd`
  - Keep, but make the primary output exact retrieval, not explanation.
  - Deterministically validate source path, quoted passage or extracted text, and line range.
  - Downstream LLM evaluation is secondary: can a model answer the target question from the reduced passage.
- `ripgrep`
  - Keep, but tighten tasks so the official output is exact candidate paths or target references.
  - Deterministically validate expected paths or reference sets.
  - Remove summarize steps that only restate machine-checkable answers.
- `fastmod`
  - Keep.
  - Primary benchmark is deterministic rewrite correctness: exact replacements, remaining-match checks, and validation commands.
  - Use LLM evaluation only for ambiguous semantic-risk cases, not as a routine part of the official path.
- `ast-grep`
  - Keep.
  - Primary benchmark is deterministic AST-aware rewrite correctness using exact match and no-regression checks.
  - LLM evaluation remains optional and secondary.
- `comby`
  - Keep.
  - Primary benchmark is deterministic structural rewrite correctness with exact postconditions.
  - LLM evaluation remains optional and secondary.

### 6. Rework validators
- Replace fuzzy hint-based validators wherever exact checks are possible.
- Validation policy by family:
  - `ripgrep`, `qmd`: exact path/passage/reference checks
  - `rtk`: exact signal-retention and omission checks
  - `fastmod`, `ast-grep`, `comby`: exact rewrite count, no-remaining-match, and diff/search-based checks
- Keep human review only for declared borderline cases.
- Add a separate judge stage for downstream quality loss. This stage does not determine primary validity unless the family explicitly requires semantic recovery that deterministic checks cannot capture.

### 7. Rework reporting and scorecards
- Replace the single official scorecard with two official views:
  - tool efficacy scorecard
  - downstream quality retention scorecard
- Add explicit fields in reports for:
  - reduction achieved
  - deterministic validity
  - downstream quality delta
  - whether any LLM was used
  - whether expensive LLM evaluation was required
- Keep legacy HTML and markdown reporting for v1, but label it clearly as `legacy-agent` or `appendix`.
- Update benchmark overview content so it no longer implies that the official benchmark is always an end-to-end agent conversation.

### 8. Team implementation phases
1. Contract phase
- Write the new benchmark methodology doc and v2 task schema spec.
- Freeze scoring definitions, artifact definitions, and evaluator escalation policy before code changes begin.

2. Harness phase
- Update core models, runner orchestration, CLI modes, artifact writing, and validation interfaces.
- Implement backward-compatible parsing for v1 runs.

3. Task and validator phase
- Rewrite official `rtk` tasks first.
- Rewrite `qmd` next.
- Tighten `ripgrep` manifests and validators.
- Update mechanical families last, mostly to remove unnecessary LLM-oriented summarize burden.

4. Reporting phase
- Add new scorecard generation and HTML reporting for layered metrics.
- Preserve legacy report generation for old data.

5. Migration and docs phase
- Mark the old methodology as legacy in docs and findings.
- Publish a migration note for task authors, reviewers, and report readers.
- Keep historical results readable and separated from new official outputs.

## Public Interfaces And Data Contracts
- Add a versioned task manifest contract for v2.
- Add phase-aware run records in the harness model.
- Add new CLI commands or modes for `tool-only`, `quality-eval`, and `legacy-agent`.
- Add report schema support for paired scorecards and LLM-escalation metadata.
- Keep v1 manifest loading and run parsing supported during migration.

## Test Plan
- Schema tests for v2 task manifests and backward compatibility with v1 manifests.
- Runner tests for phase-separated execution and artifact creation.
- Validation tests for deterministic preservation checks and exact rewrite checks.
- Aggregation/reporting tests for new scorecard shapes and legacy compatibility.
- Family acceptance tests:
  - `rtk`: compression preserves required failure signals and downstream answer quality can be compared
  - `qmd`: reduced passage is exact and sufficient
  - `ripgrep`: returned references are exact
  - `fastmod`, `ast-grep`, `comby`: rewrites are exact and machine-verifiable
- Regression tests confirming legacy reports still render from current run directories.

## Assumptions And Defaults
- Rollout style: phased replacement, not hard reset.
- Official benchmark scope: layered benchmark is official; end-to-end workflows move to appendix status.
- Expensive LLM policy: last resort only.
- Cassandra remains the anchor repo for the first redesign phase.
- Existing v1 results are preserved and not reinterpreted as if they were produced under the new contract.
