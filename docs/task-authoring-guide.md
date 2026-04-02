# Task Authoring Guide

This guide explains how to write official benchmark tasks for agentic-token-bench.
All tasks must conform to `schemas/task.schema.json` and the rules in
`docs/plans/2026-03-31-v1-build-plan-design.md`.

This guide also introduces the v2 deterministic-first direction. New work
should minimize LLM use unless a downstream evaluation stage truly needs a
semantic judgment. The legacy v1 step-manifest format remains supported for
compatibility and historical reproduction.

## Quick start

Copy `benchmarks/tasks/task-template.yaml` and edit it. Validate your task
before opening a pull request:

```bash
uv run atb validate-schemas
```

For v2-style task design, check the deterministic-first requirements below
before you lock the manifest. For legacy v1 tasks, schema validation is the
existing gate.

## v2 task model

v2 tasks are phase-based rather than prompt-stage based. A v2 task should
describe:

- the input artifact(s) and fixture source
- the tool invocation contract
- the deterministic preservation or correctness checks
- any optional downstream evaluation question(s)
- the evaluator policy, including when a small model is acceptable and when an
  expensive model is allowed only as a last resort

The default rule is simple: use deterministic validation first, then bring in
an LLM only if a human-quality judgment is still needed. Do not force every
task through a summarize-style free-form answer when the artifact can be
checked directly.

---

## Required fields

Every task manifest is a YAML file. All of the following fields are required
unless noted.

### `task_id`

A unique, lowercase, hyphen-separated identifier for this task.

Format: `<repo>-<tool-family>-<sequence>`

Example: `cassandra-ripgrep-01`

### `title`

A short human-readable description of what the task asks the agent to do.
Keep it under 80 characters.

### `family`

The tool family this task belongs to. Must be one of the official families:
`ripgrep`, `qmd`, `rtk`, `fastmod`, `ast-grep`, `comby`.

Each family must have exactly two official tasks (`-01` and `-02`).

### `repo`

The target repository. For the Cassandra benchmark this is always
`cassandra`.

### `pinned_commit`

The exact git commit SHA the harness must check out before running this task.
Use the placeholder `<PINNED_COMMIT>` in templates. Replace it with a real SHA
before submitting an official task.

All tasks in one release share the same pinned Cassandra commit. Do not mix
commits across official tasks.

### `objective`

One or two sentences stating what the agent should accomplish. Write at the
level of intent, not steps. This text appears in the canonical prompt pack.

### `task_description`

A full description of the task suitable for an agent reading it cold. Include:

- What the target behavior or code area is
- What artifacts the agent must find or produce
- Any explicit constraints (e.g., "do not edit code")

This text also appears in the canonical prompt pack.

### `success_criteria`

A YAML list of short, verifiable statements. Each criterion must be checkable
by the validation command or by a human reviewer using the final answer
artifact. Write criteria that map directly to the `fields` in the final step's
`completion_contract`.

### `validation_commands`

A YAML list of shell commands the harness runs after the agent completes all
steps. Each command must exit `0` on success and non-zero on failure.

Validation scripts live in `scripts/`. Name them `validate_<task_slug>.py`
and accept `--task <task_id>` as an argument.

Every official task must have at least one automated validation command.
Human review is allowed only for borderline partial passes, anticipated
validation gaps, or safety concerns.

### `human_review_triggers` (optional)

A list of conditions under which a human reviewer should inspect the run
even when automated validation passes. Keep this list short. Good examples:

- "validation output is partial"
- "more than one candidate path returned for any field"

### `steps`

An ordered list of step objects. See the Step model section below.

### `baseline_policy`

Controls how the harness runs the baseline variant of this task.

```yaml
baseline_policy:
  remove_tool_under_test: true
```

Always set `remove_tool_under_test: true` for official tasks. This removes
the tool under test from the step `PATH` so the agent cannot use it.

### `tool_variant_policy`

Controls how the harness runs the enforced-tool variant of this task.

```yaml
tool_variant_policy:
  enforce_tool_under_test: true
```

Always set `enforce_tool_under_test: true` for official tasks. This exposes
the tool under test and fails the run as invalid if the agent does not use it
in the step where it is required.

---

## Legacy v1 step model

Steps are the execution units of a legacy v1 task. Each task has one or more
steps that run in order. The harness creates a separate constrained environment
for each step.

### Available step types

Legacy v1 tasks use these step identifiers. Use them as both `step_id` and
`name`.

| Step | Purpose |
|------|---------|
| `discover` | Find candidate locations, files, or references using a search tool. |
| `retrieve` | Pull the minimal context needed from located files. |
| `analyze` | Reason over retrieved context to identify the correct answer or plan. |
| `edit` | Apply targeted code or config changes. |
| `validate` | Run local checks to verify the edit is correct. |
| `summarize` | Produce the final structured answer. |

Not every task needs all six steps. A simple discovery task may need only
`discover` and `summarize`. An edit task may need `discover`, `retrieve`,
`edit`, `validate`, and `summarize`.

For v2, the equivalent behavior should be expressed as a tool phase plus
deterministic checks, not as a free-form summarize prompt, unless the summarize
step is the only place where a downstream quality judgment can be made.

### Step fields

#### `step_id`

A string identifier for this step. Use the step type names listed above.
Step IDs must be unique within a task.

#### `name`

Human-readable name. Match it to `step_id` for clarity.

#### `objective`

One or two sentences describing what the agent should accomplish in this step.
This text appears in the per-step section of the prompt pack.

#### `required_tool`

The single tool the agent must invoke at least once during this step. Set to
`null` if no tool is required.

When this is non-null:

- The tool wrapper must record at least one successful invocation.
- The run is invalid if the tool is never called.
- In the `baseline` variant the tool is removed from `PATH` entirely.

#### `allowed_tools`

List of benchmark tools the agent may call in this step. The harness exposes
only these tools (as wrapped binaries) on the step `PATH`.

Use an empty list `[]` for steps where no benchmark tools should be available,
such as a `summarize` step.

Do not include the tool in `allowed_tools` if it is also in `blocked_tools`.

#### `blocked_tools`

List of benchmark tools that must not be called in this step. If any blocked
tool is invoked, the run becomes invalid.

For the `summarize` step, block all benchmark tools to force the agent to
reason from accumulated context rather than making new tool calls.

#### `completion_contract`

Describes what the agent must produce to complete the step.

```yaml
completion_contract:
  kind: structured_answer
  fields: [field_one, field_two]
```

`kind` is always `structured_answer` in legacy v1 tasks. `fields` lists the
named outputs the agent must provide. The final step's fields must map
directly to the task's `success_criteria`.

For v2, prefer direct artifact checks wherever possible instead of relying on
a final free-form answer.

#### `artifact_requirements`

List of artifacts the harness must find after the step completes.

Common values:

- `step_trace` — the JSONL trace for this step (required for all non-final steps)
- `final_answer` — the agent's structured final answer (required for the last step)

---

## Tool enforcement rules

Tool enforcement is a hard contract, not a suggestion. The harness implements
it mechanically using `PATH` control and wrapper traces.

### How enforcement works

For each step, the harness creates a temporary directory and places only the
wrapped binaries for `allowed_tools` on the `PATH`. Standard system commands
remain available.

- If a step has `required_tool: ripgrep`, the wrapped `rg` binary is on the
  `PATH` for the tool variant and absent for the baseline.
- If a tool appears in `blocked_tools`, its wrapper is absent from the `PATH`.
  If the agent somehow calls it, the run is marked invalid.

### Wrapper behavior

Each tool wrapper is a thin passthrough that also:

- Records invocation time and exit status
- Records arguments (or a safe hash of arguments)
- Appends a structured event to `tool_invocations.jsonl`
- Passes through stdout and stderr faithfully

Do not include bare tool binaries in `allowed_tools`. The harness uses the
wrapper name, not the raw binary.

### Run validity

A run is **invalid** (excluded from official scorecards) if:

- The required tool was not called in the step where it is required
- A blocked tool was called in any step
- Reported token counts are missing
- The step trace is incomplete

---

## Baseline vs tool_variant policies

These policies describe the legacy v1 comparison model. Each official task runs
twice: once as `baseline` and once as `tool_variant`. The comparison between
these two runs is the legacy benchmark result.

For v2, keep the same family boundaries, but separate tool execution from
downstream quality evaluation so the LLM only appears where it adds value.

### Baseline variant

The harness removes the tool under test from the step `PATH`. The agent must
complete the task using only standard shell tools and whatever is available
in `allowed_tools` after the tool under test is stripped.

Set `baseline_policy.remove_tool_under_test: true` in every official task.

### Tool variant

The harness enforces the tool under test. The wrapped binary is on the `PATH`
for the step where `required_tool` is set. The run is invalid if the agent
does not invoke it at least once.

Set `tool_variant_policy.enforce_tool_under_test: true` in every official task.

### What the comparison measures

The legacy v1 benchmark question for each family is:

> Did the enforced tool reduce reported token usage compared with the baseline,
> while preserving or improving correctness?

To keep attribution clean, each task family tests exactly one tool. Do not add
a second benchmark tool to the `allowed_tools` list for a tool family's official
tasks. Mixed-tool workflows belong in the appendix (legacy Track B).

---

## Authoring guardrails

These rules come directly from the implementation contract. Violating them
produces runs that cannot appear in the official scorecard.

### Every task must have automated validation

Do not author a task unless you can write a validation script that checks the
answer mechanically. Human review is the fallback, not the default.

### Tasks must be narrow

Each task tests one tool family. Do not write tasks that require multiple
benchmark tools to complete. If you find yourself adding two tools to
`required_tool`, split the task. For v2, this also means do not combine tool
execution and downstream LLM judgment in the same required step unless the
task's only purpose is to study that handoff.

### Use the pinned commit

All official tasks must reference the same pinned Cassandra commit. Tasks
referencing different commits produce incomparable results and cannot be
included in the official scorecard.

### Do not mix reported and estimated tokens

The benchmark uses only reported token counts from the agent CLI. If a task
variant produces runs where the agent does not report tokens, those runs are
invalid. Design tasks that complete within the agent's reporting window.

### Step ordering must be deterministic

The harness runs steps in list order. Design the step sequence so each step's
output feeds naturally into the next. Do not write steps that depend on
information not yet available at that point in the sequence.

### Blocked tools must cover all other benchmark tools

In the `summarize` step (and any step where you want to prevent benchmark tool
use), list all six official tool families in `blocked_tools`. Leaving a tool
off the blocked list means the agent can silently use it without detection.

For v2 tasks, prefer direct artifact validation over summarize-step blocking
when the artifact itself can answer the question.

### Final step must produce `final_answer`

The last step must include `final_answer` in `artifact_requirements`. This is
the artifact the validation command reads. Without it, validation cannot run.

### One task ID per file

Each YAML file contains exactly one task manifest. Name the file to match
`task_id`: `cassandra-ripgrep-01.yaml`.

---

## File placement

Official tasks for the ripgrep family on Cassandra belong in:

```
benchmarks/tasks/cassandra/official/cassandra-ripgrep-01.yaml
benchmarks/tasks/cassandra/official/cassandra-ripgrep-02.yaml
```

Appendix (mixed-tool) workflows belong in:

```
benchmarks/tasks/cassandra/appendix/
```

Do not place official tasks in the appendix directory or vice versa.

Legacy v1 official tasks belong in `official/`. Any future v2 appendix or
compatibility workflows should be labeled explicitly so readers do not confuse
them with the deterministic-first official path.

---

## Validation script contract

Validation scripts must:

- Accept `--task <task_id>` as a CLI argument
- Read the agent's `final_answer.txt` from the current run artifact directory
  (passed via the `ATB_ARTIFACT_DIR` environment variable or a second argument)
- Exit `0` on full pass, `1` on fail, `2` on partial pass
- Write a machine-readable summary to stdout as a single JSON object with at
  minimum `{"status": "pass"|"partial"|"fail", "details": {...}}`

Partial pass (`exit 2`) triggers human review if `human_review_triggers` are
also satisfied.

For v2-style tasks, validation scripts may validate artifacts directly and may
supplement deterministic checks with an optional downstream quality-eval
result. Keep the machine-readable summary explicit about which stage failed.
