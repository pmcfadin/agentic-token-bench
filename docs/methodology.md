# Benchmark Methodology

This document describes the v2 benchmark methodology for `agentic-token-bench`.
v2 is the deterministic-first contract for new results: tools produce or reduce
artifacts first, deterministic checks validate those artifacts second, and an
LLM is used only when a downstream quality judgment is still needed.

The original v1 end-to-end agent workflow remains available as a legacy/
appendix track for historical reproduction and compatibility. When this document
and the legacy v1 implementation plan conflict, use this document for v2
interpretation and the implementation plan for legacy-agent reproduction.

---

## 1. Benchmark Design

V2 is intentionally narrow and layered.

**Single repository.** All official tasks run against Apache Cassandra at one
pinned commit. Using one repository removes repo-level confounds from
tool-effect comparisons. The pinned commit is fixed for an entire scorecard
release; results are not mixed across commits.

**Single-tool task families.** The unit of comparison is a tool family: one
tool under test, two tasks on Cassandra, one baseline variant per task, and one
enforced-tool variant per task. In v2, the official evidence is split into two
layers: deterministic tool efficacy and downstream quality retention. Official
scorecards do not mix tools within a comparison. Mixed-tool workflows appear in
a clearly labeled appendix (legacy Track B) and are not the basis for tool-
specific claims.

**Controlled comparison.** Each family produces one direct comparison: the same
task, the same agent, the same Cassandra commit, with and without the tool
under test. The baseline variant removes the tool; the tool variant enforces it.
All other conditions are held constant. For v2, the comparison is read as
deterministic artifact quality first, then downstream answer quality if an LLM
judge is required.

V2 keeps the same six official tool families: `ripgrep`, `qmd`, `rtk`,
`fastmod`, `ast-grep`, and `comby`. Each family has two tasks, yielding twelve
official tasks. The legacy v1 end-to-end matrix remains reproducible for
compatibility; v2 adds the deterministic-first interpretation on top of those
families.

---

## 2. Tool Enforcement and Validation Model

Tool availability is enforced by the harness, not by instructions to the agent.
That model still matters for legacy-agent runs and for compatibility checks. In
v2, direct artifact validation is the primary measurement path whenever the
tool output can be checked without an agent conversation.

**PATH control.** For each step in a task, the harness constructs a temporary
tool directory and places only the allowed tool wrappers on `PATH`. System
commands required for the agent to function are also available. Tools that are
not in the allowed set for that step are absent from `PATH`; the agent cannot
call them regardless of what it decides to do.

**Wrapper mediation.** Every benchmark tool is wrapped. The wrapper keeps the
real tool name so the agent calls it naturally. It records invocation time,
exit status, and arguments, and appends a structured event to
`tool_invocations.jsonl` in the run artifact directory. Stdout and stderr are
passed through faithfully.

**Required and blocked tool rules.** Each task step declares `required_tool`,
`allowed_tools`, and `blocked_tools`. When a step requires a tool, the wrapper
trace must show at least one successful invocation of that tool within that
step. When a run variant is `baseline`, the tool under test is absent from
`PATH`. If the agent invokes a blocked tool, the run is immediately classified
as invalid. Enforcement violations are harness-level decisions; correctness
review does not override them.

---

## 3. Token Accounting

**Reported values only for legacy-agent runs.** When an agent CLI is involved,
the official token metric is the count reported by the agent CLI itself.
Estimated or inferred token counts are not permitted in official results. Any
run that does not produce stable, extractable reported token counts is
classified as invalid and excluded from official scorecards.

For v2 tool-only and quality-eval phases, bytes reduced, preservation checks,
and downstream quality scores matter more than raw agent-token totals.

**Evidence required.** Every run artifact directory contains a
`token_evidence.txt` file. This file holds the raw snippet from agent output
from which input, output, and total token counts were extracted. Reviewers and
third parties can inspect this file to verify that reported counts come directly
from agent output. The adapter method used to extract tokens is also recorded in
the qualification record for each agent.

---

## 4. Agent Qualification Protocol

No agent CLI enters the official benchmark until it passes qualification.
Qualification is run by the harness using the `qualify-agent` command and
produces a machine-readable qualification record.

**Four gates.** An agent qualifies only if it passes all four:

1. **Reported-token gate.** The CLI exposes stable reported token counts that
   can be extracted programmatically for benchmark runs.
2. **Forced-tool gate.** The agent can operate inside the constrained step
   environment, and required tools appear in the trace when mandated.
3. **Audit-trace gate.** The run emits enough observable output to reconstruct
   tool usage and step progress.
4. **Run-completeness gate.** The harness can capture start, finish, tokens,
   artifacts, validation output, and final status without manual intervention.

**Five probes.** Every agent adapter ships at least these qualification probes:

1. Token reporting probe
2. Simple no-tool step probe
3. Forced single-tool step probe
4. Blocked-tool failure probe
5. Completion and artifact probe

**Qualification before official runs.** If only one agent qualifies at launch,
the public benchmark ships with that one qualified agent. Non-qualified agents
are reported separately in a qualification appendix with their failure reason.
Non-qualified agents do not appear in official scorecard comparisons.

---

## 5. Run Validity Rules

The harness distinguishes valid failures from invalid runs. Both categories are
recorded; only valid runs appear in official scorecards.

**A run is valid if:**

* The agent started successfully.
* Reported token counts were captured.
* The step trace is complete enough to audit.
* Required tools and blocked tools were enforced correctly throughout.
* Validation commands executed.

A valid run may still fail the task. Task failure and run invalidity are
separate classifications.

**A run is invalid if any of the following are true:**

* Reported tokens are missing or could not be extracted.
* A required tool was not actually used in the step that mandated it.
* A blocked tool was used.
* The step trace is incomplete.
* Validation did not execute because of a harness failure.
* The CLI adapter could not capture the official metrics.

Invalid runs are recorded in the artifact directory but excluded from scorecards
and from any aggregated token or correctness metrics. The exclusion reason is
written to the run record.

---

## 6. Task Design

V2 tasks are phase-based and deterministic-first. A task may define a tool
phase, a validation phase, and an optional downstream quality-eval phase. The
older step-based manifest shape below is retained for legacy-agent
compatibility and historical runs.

**Phased steps.** Legacy v1 tasks are divided into named steps with canonical
IDs: `discover`, `retrieve`, `analyze`, `edit`, `validate`, `summarize`. Each
step has its own tool rules, completion contract, and artifact requirements.
The harness enforces each step's rules independently.

**Completion contracts.** Each step specifies what the agent must produce to
satisfy that step. Contracts are either `structured_answer` (specific fields
required) or another declared kind. The harness checks that artifact
requirements are present before marking a step complete.

**Baseline vs. variant policies.** Every task manifest declares two policies:

* `baseline_policy`: removes the tool under test. The tool is absent from
  `PATH` for relevant steps.
* `tool_variant_policy`: enforces the tool under test. The tool must appear in
  the step trace.

The same task body, prompt, and validation commands are used for both variants.
Only tool availability differs.

Official tasks are authored to be well-defined on Cassandra at the pinned
commit. Each task has explicit `success_criteria` and `validation_commands`.
Task IDs follow the pattern `cassandra-{family}-{NN}` (see `docs/conventions.md`).

---

## 7. Statistical Approach

**Three repetitions per run.** Each task and variant combination is run three
times. Repetitions use the same task manifest, the same pinned Cassandra commit,
and the same canonical prompt pack. The workspace is reset between repetitions.

**Variance measurement.** Reported token counts, elapsed time, and validation
outcomes are recorded for each repetition. The scorecard reports the mean and
range across repetitions for token metrics.

**Stability thresholds.** Repeated runs of the same task and variant must
produce run records with the same artifact structure (the same set of files in
the run artifact directory). Token values and elapsed times may vary; structure
must not. Runs that produce different `validity` classifications for the same
task and variant under the same conditions indicate a harness problem that must
be resolved before Gate 2 can pass (see `docs/release-gates.md`).

---

## 8. Correctness Policy

**Automated validation first.** Every official task must have automated
validation commands. The harness executes these commands and records the result
in `validation.json`. Automated validation is the primary correctness signal.

**Human review only for borderline cases.** Human review is triggered in three
specific conditions, all of which must be declared in the task manifest under
`human_review_triggers`:

1. Borderline partial passes where the failing criteria are qualitative or
   ambiguous and the automated result is genuinely uncertain.
2. Anticipated validation gaps declared by the task author at authoring time,
   where a known limitation in automated validation may produce false negatives.
3. Safety concerns where the agent may have acted outside the task scope in a
   way automated diff analysis cannot fully assess.

Clear automated passes and clear automated failures do not trigger review.
Invalid runs are not sent for correctness review; invalidity is a harness
classification and is not overridden by human judgment.

**Review rubric.** Reviewers use a three-field rubric: `correctness`
(`pass`, `minor_issue`, `fail`), `safety` (`clear`, `review_needed`, `unsafe`),
and `notes` (free text explaining the evidence examined). Full rubric definitions
are in `docs/human-review-rules.md`. Runs with `review_needed` on safety are
held pending a second reviewer.

**Correctness beats token savings.** A run that saves tokens but produces a
safety-`unsafe` outcome is excluded from official results regardless of the
token delta.

---

## 9. Limitations

V2 is a controlled measurement product, not a general platform. The following
limitations apply to all v2 claims. The legacy v1 track remains available for
compatibility and historical comparison, but it is not the primary claim
surface.

**Not universal.** Results describe tool effects on Apache Cassandra under the
specific task shapes defined in v2. The benchmark does not claim that token
savings observed here generalize to other repositories, other languages, other
task types, or other agent configurations.

**One repository.** All official v2 comparisons are on Cassandra at one pinned
commit. Repository-level effects are not separated from tool effects. A tool
that performs well on Cassandra may not perform the same way on a different
codebase.

**One agent at initial launch (potentially).** The benchmark may launch with a
single qualified agent. Cross-agent comparisons require each agent to qualify
under the same contract and run the same official suite. Cross-agent results are
not comparable until both agents have qualified qualification records produced
by the same harness version.

**CLI invocation only for legacy-agent runs.** The legacy track uses CLI agent
invocation. API-based execution is not in scope for that track. Agents that
expose different behavior through a CLI than through their API are measured
only through their CLI.

**Reported tokens, not ground-truth tokens.** The official metric is what the
agent CLI reports. If an agent under-reports or over-reports tokens relative to
actual model consumption, the benchmark reflects the reported figure. Evidence
snippets in `token_evidence.txt` allow inspection but do not correct for
agent-side reporting differences.

**Track A vs. Track B.** Mixed-tool appendix workflows (Track B) are not the
basis for tool-specific claims. Token savings attributed to a specific tool in
official results come only from single-tool family comparisons in Track A.

## 10. Legacy v1 Appendix

The original end-to-end agent workflow is retained as a legacy/appendix track.
Those runs remain reproducible and comparable with earlier releases, but they
should be read as compatibility evidence, not as the primary v2 methodology.
