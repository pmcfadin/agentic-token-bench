# Cassandra v1 Benchmark Implementation Plan

## Status

Validated through interactive brainstorming on 2026-03-31 and updated for implementors.

This document is the implementation contract for v1. It is not a vision memo. If the code, schemas, or CLI behavior disagree with this document, treat that as a bug.

## Goal

Build the fastest credible public benchmark for measuring whether specific external tools reduce token usage in agentic coding without reducing correctness.

V1 is intentionally narrow:

* one repository: Apache Cassandra
* CLI agent invocation only
* no API-based execution
* official token metric is reported-only
* required tool usage is enforced, not suggested
* official comparisons are single-tool task families

## Locked Product Decisions

These decisions are fixed for v1 unless this document is updated explicitly.

### Scope

* Official v1 repository: Apache Cassandra
* Official v1 tools:
  * `qmd`
  * `rtk`
  * `fastmod`
  * `ast-grep`
  * `comby`
  * `ripgrep`
* Official v1 agents under evaluation:
  * `codex`
  * `claude`
  * `gemini-cli`

### Benchmark shape

* Fastest credible public benchmark is the top priority
* All listed tools must be tested in v1
* Agent comparison is staged, not a full cross-product on day one
* Official runs use one canonical instruction pack across agents
* Official tasks are phased and step-aware
* Required tools are forced per step
* Official scorecards use single-tool task families
* Each tool family gets two official tasks
* Official baseline for each family is the same task with the tested tool removed
* Correctness is judged by automated validation first, with human review only for borderline cases

### Token accounting

* Official token metric uses reported values only
* Estimated tokens are not allowed in official results
* Any run without stable reported token counts is not an official run

### Release policy

* All agents must pass a qualification round before they appear in official scorecards
* If only one agent qualifies at first, the public benchmark still ships with that one qualified agent
* Non-qualified agents are reported separately as pending qualification

## What The Benchmark Must Prove

For each official tool family on Cassandra, the benchmark must answer:

1. Did the enforced tool reduce reported token usage compared with the baseline?
2. Did it preserve or improve correctness?
3. Did it change validation outcomes, repair loops, or elapsed time?
4. Can the effect be reproduced under the same task contract?

The public claim must stay narrow. V1 is not trying to prove universal tool superiority. It is trying to produce defensible evidence under a controlled setup.

## Implementation Stack

Use these defaults unless there is a clear blocker.

### Core stack

* Python 3.12
* `uv` for Python versioning, environment management, locking, and task execution
* `typer` for the benchmark CLI
* `pydantic` for typed models
* `pytest` for tests
* JSON Schema for public schema files under `schemas/`
* JSONL for event streams and run traces
* DuckDB for result aggregation

### Why this stack

This project is a CLI orchestration and measurement harness. Its core work is:

* spawning agent CLIs
* controlling `PATH` and per-step tool availability
* capturing stdout, stderr, and artifacts
* parsing reported token counts
* classifying run validity
* writing result bundles and scorecards

Python is the best v1 fit for that combination. It gives direct process control, straightforward filesystem tooling, good schema support, and a low-friction path from raw artifacts to reports.

### Platform assumptions

V1 targets:

* macOS
* Linux

Do not spend v1 time on Windows support. The benchmark depends on shell behavior, `PATH` control, and TTY handling that will be easier to stabilize on Unix-like systems first.

### Allowed exceptions

If one agent CLI needs a small helper binary or sidecar to expose reliable TTY or parsing behavior, that is acceptable. Do not move the whole project to another stack to satisfy one adapter edge case.

## Official Benchmark Tracks

V1 has two tracks.

### Track A: Official scorecard

This is the primary public benchmark.

Properties:

* Cassandra only
* one pinned commit at a time
* one qualified agent at minimum
* single-tool task families
* phased task manifests
* required-tool enforcement
* reported-token accounting only
* automated validation first

This track is the source of benchmark claims.

### Track B: Appendix workflows

This is secondary and must be labeled clearly.

Properties:

* mixed-tool workflows
* still on Cassandra
* used to show tool composition in realistic flows
* not the main basis for tool-specific claims

This track exists because real coding loops compose tools, but it must not dilute the attribution logic of the official scorecard.

## Official Comparison Unit

The official unit of comparison is a tool family.

Each family contains:

* one tool under test
* two tasks on Cassandra
* one baseline variant per task
* one enforced-tool variant per task

This yields the initial official matrix for one qualified agent:

* 6 tool families
* 2 tasks each
* 2 variants per task
* 24 official runs before repetition

If the project repeats each run three times for stability, the first qualified agent requires 72 official runs.

## Repository Layout

This layout is the default target for Phase 0.

```text
agentic-token-bench/
  README.md
  pyproject.toml
  uv.lock
  docs/
    spec.md
    methodology.md
    findings.md
    plans/
      2026-03-31-v1-build-plan-design.md
  schemas/
    task.schema.json
    run.schema.json
    event.schema.json
    qualification.schema.json
  benchmarks/
    harness/
      __init__.py
      cli.py
      models.py
      runner.py
      workspace.py
      step_executor.py
      validation.py
      artifacts.py
      reporting.py
      qualification.py
      prompts.py
      tracing.py
    results/
    qualification/
    tasks/
      cassandra/
        official/
        appendix/
    repos/
      cassandra/
        repo.yaml
        setup/
  agents/
    base.py
    codex/
      adapter.py
      parser.py
      probe.py
    claude/
      adapter.py
      parser.py
      probe.py
    gemini_cli/
      adapter.py
      parser.py
      probe.py
  tools/
    base.py
    qmd/
      wrapper.py
      manifest.yaml
    rtk/
      wrapper.py
      manifest.yaml
    fastmod/
      wrapper.py
      manifest.yaml
    ast_grep/
      wrapper.py
      manifest.yaml
    comby/
      wrapper.py
      manifest.yaml
    ripgrep/
      wrapper.py
      manifest.yaml
  scripts/
  tests/
    fixtures/
    schemas/
    qualification/
    official_runs/
```

## Module Responsibilities

These boundaries should stay stable.

### `benchmarks/harness/cli.py`

Owns the public CLI commands.

Expected commands:

* `qualify-agent`
* `run-task`
* `run-family`
* `run-suite`
* `generate-scorecard`
* `validate-schemas`

### `benchmarks/harness/models.py`

Owns internal pydantic models for tasks, runs, events, scorecards, and qualification outputs.

### `benchmarks/harness/runner.py`

Owns end-to-end orchestration for a run.

Responsibilities:

* load task
* choose baseline or variant
* prepare workspace
* create prompt pack
* invoke step executor
* invoke validation
* classify result
* write artifacts

### `benchmarks/harness/workspace.py`

Owns Cassandra checkout, reset, copy, and cleanup logic.

### `benchmarks/harness/step_executor.py`

Owns step-by-step execution and tool enforcement.

Responsibilities:

* construct per-step environment
* control visible tools
* run agent step
* append trace events
* enforce required and blocked tool rules

### `benchmarks/harness/qualification.py`

Owns qualification probes and pass or fail decisions for each agent adapter.

### `benchmarks/harness/prompts.py`

Owns the canonical instruction pack and any agent-neutral prompt rendering.

### `benchmarks/harness/tracing.py`

Owns event writing and trace normalization.

### `benchmarks/harness/validation.py`

Owns execution of validation commands and normalization of validation output.

### `benchmarks/harness/artifacts.py`

Owns run directory creation and artifact writing.

### `benchmarks/harness/reporting.py`

Owns scorecard aggregation and report generation.

### `agents/base.py`

Defines the adapter interface every agent must implement.

### `tools/base.py`

Defines the wrapper interface every tool wrapper must implement.

## Data Contracts

Schemas under `schemas/` are public contracts. Internal pydantic models may be richer, but they must serialize to the public schema.

### Task manifest contract

Each official task must define:

* `task_id`
* `title`
* `family`
* `repo`
* `pinned_commit`
* `objective`
* `task_description`
* `success_criteria`
* `validation_commands`
* `human_review_triggers`
* `steps`
* `baseline_policy`
* `tool_variant_policy`

### Task step contract

Each used step must define:

* `step_id`
* `name`
* `objective`
* `required_tool`
* `allowed_tools`
* `blocked_tools`
* `completion_contract`
* `artifact_requirements`

### Run record contract

Each run record must define:

* `run_id`
* `task_id`
* `family`
* `variant`
* `agent_id`
* `adapter_version`
* `repo_commit`
* `status`
* `validity`
* `reported_input_tokens`
* `reported_output_tokens`
* `reported_total_tokens`
* `elapsed_seconds`
* `repair_iterations`
* `validation_status`
* `files_changed`
* `diff_size`
* `artifact_dir`

### Qualification record contract

Each qualification result must define:

* `agent_id`
* `adapter_version`
* `qualified`
* `reported_token_support`
* `forced_tool_support`
* `trace_support`
* `run_completion_support`
* `failure_reason`
* `evidence_paths`

### Event record contract

Each trace event must define:

* `timestamp`
* `run_id`
* `step_id`
* `event_type`
* `actor`
* `payload`

## Example Task Manifest

Use YAML for task authoring unless implementation friction makes JSON materially better.

```yaml
task_id: cassandra-ripgrep-01
title: Locate the code path for a specific configuration behavior
family: ripgrep
repo: cassandra
pinned_commit: "<commit-sha>"
objective: Find the implementation and related docs for the target behavior.
task_description: >
  Identify the source file, related configuration entry, and one validating test
  for the described behavior. Do not edit code.
success_criteria:
  - Correct source path identified
  - Correct config path identified
  - Correct test path identified
validation_commands:
  - "python scripts/validate_locate_paths.py --task cassandra-ripgrep-01"
human_review_triggers:
  - "validation output is partial"
steps:
  - step_id: discover
    name: discover
    objective: Find candidate source locations.
    required_tool: ripgrep
    allowed_tools: [ripgrep]
    blocked_tools: [qmd, rtk, fastmod, ast-grep, comby]
    completion_contract:
      kind: structured_answer
      fields: [candidate_paths]
    artifact_requirements: [step_trace]
  - step_id: summarize
    name: summarize
    objective: Provide the final answer in the required format.
    required_tool: null
    allowed_tools: []
    blocked_tools: [qmd, rtk, fastmod, ast-grep, comby, ripgrep]
    completion_contract:
      kind: structured_answer
      fields: [source_path, config_path, test_path]
    artifact_requirements: [final_answer]
baseline_policy:
  remove_tool_under_test: true
tool_variant_policy:
  enforce_tool_under_test: true
```

## Example Run Artifact Layout

Every run should create one artifact directory.

```text
benchmarks/results/<run-id>/
  run.json
  trace.jsonl
  prompt.txt
  final_answer.txt
  validation.json
  diff.patch
  stdout.log
  stderr.log
  token_evidence.txt
  tool_invocations.jsonl
```

## Official Run Lifecycle

Every official run should follow the same lifecycle.

1. Load the task manifest.
2. Resolve the target Cassandra commit.
3. Prepare an isolated workspace from that commit.
4. Select the run variant: `baseline` or `tool_variant`.
5. Render the canonical prompt pack.
6. For each step:
   * create a step-specific environment
   * expose only allowed wrapped tools
   * block the tool under test when running the baseline
   * invoke the agent adapter
   * collect trace events and tool invocations
   * fail the run as invalid if enforcement rules are broken
7. Run validation commands.
8. Extract reported token counts from agent output.
9. Classify the run as valid or invalid.
10. Write artifacts.
11. Aggregate results into scorecards later.

## Canonical Prompt Pack

Official runs must use one canonical instruction pack with minimal agent-specific wrapping.

The canonical pack must include:

* task objective
* repository context
* phase list
* per-step tool rules
* completion contract
* validation expectation
* output format for the final answer

Agent-specific adapters may change only what is required to invoke the CLI cleanly. They may not change the benchmark instructions in any material way.

## Tool Enforcement Model

This is a hard requirement. Do not rely on prompt-only guidance.

### Enforcement mechanism

For each step, the harness should create a temporary tool directory and place only allowed wrappers on the `PATH`.

Example:

* if the step requires `ripgrep`, the step `PATH` exposes the wrapped `ripgrep` binary and any required system commands
* if the run variant is `baseline`, the wrapped `ripgrep` binary is absent
* if a blocked benchmark tool is called, the run becomes invalid

### Wrapper behavior

Each wrapper must:

* keep the real tool name so the agent can call it naturally
* record invocation time
* record exit status
* record arguments or a safe hash of arguments
* append a structured event to `tool_invocations.jsonl`
* pass through stdout and stderr faithfully unless the tool itself is meant to transform output

### Required-tool evidence

When a step requires a tool, the wrapper trace must show at least one successful invocation of that tool inside that step.

## Agent Adapter Contract

Each agent adapter must implement the same interface.

### Required methods

* `probe()`
* `run_step()`
* `extract_reported_tokens()`
* `normalize_final_status()`

### `probe()`

Runs qualification checks and returns a qualification record.

### `run_step()`

Inputs:

* rendered prompt
* step environment
* workspace path
* timeout

Outputs:

* raw stdout
* raw stderr
* exit status
* step completion metadata
* trace metadata if available

### `extract_reported_tokens()`

Must return:

* `input_tokens`
* `output_tokens`
* `total_tokens`
* `evidence_snippet`

If any of these cannot be extracted reliably, the adapter does not qualify for official runs.

## Agent Qualification Protocol

No CLI enters the official benchmark until it qualifies.

### Qualification gates

An agent qualifies only if it passes all of the following:

1. Reported-token gate
   * the CLI exposes stable reported token counts for benchmark runs
   * those counts can be extracted programmatically
2. Forced-tool gate
   * the agent can operate inside the constrained step environment
   * required tools appear in the trace when mandated
3. Audit-trace gate
   * the run emits enough observable output to reconstruct tool usage and step progress
4. Run-completeness gate
   * the harness can capture start, finish, tokens, artifacts, validation output, and final status without manual intervention

### Qualification outputs

Each agent should produce:

* qualification status: `qualified` or `not_qualified`
* failure reason if not qualified
* token extraction method summary
* trace evidence summary
* adapter version

### Qualification probes

Every adapter should ship at least these probes:

* token reporting probe
* simple no-tool step probe
* forced single-tool step probe
* blocked-tool failure probe
* completion and artifact probe

### Release implication

If only one agent qualifies, release v1 with that agent. Keep the others in a clearly labeled qualification appendix.

## Run Validity Rules

The harness must distinguish valid failures from invalid runs.

### Valid run

A run is valid if:

* the agent started successfully
* reported token counts were captured
* the step trace is complete enough to audit
* required tools and blocked tools were enforced correctly
* validation executed

A valid run may still fail the task.

### Invalid run

A run is invalid if:

* reported tokens are missing
* the required tool was not actually used
* a blocked tool was used
* the trace is incomplete
* validation did not execute because of harness failure
* the CLI adapter could not capture the official metrics

Invalid runs do not belong in official scorecards.

## Metrics

V1 must stay narrow here too.

### Official metrics

* reported input tokens
* reported output tokens
* reported total tokens
* validation pass or fail
* first-pass success
* repair iteration count
* elapsed wall-clock time
* files changed
* diff size

### Supporting metrics

These can appear in run artifacts and appendix analysis:

* files opened
* lines read
* bytes read
* shell commands executed
* step durations
* tool invocation counts

Supporting metrics are useful, but they do not replace reported token counts in the official benchmark.

## Correctness Policy

Correctness beats token savings.

### Primary rule

Every official task must have automated validation.

### Secondary rule

Human review is only for:

* borderline partial passes
* validation gaps that were anticipated in the task definition
* safety concerns that automated validation cannot judge

### Review rubric

Keep the rubric small:

* `correctness`: `pass`, `minor_issue`, `fail`
* `safety`: `clear`, `review_needed`, `unsafe`
* `notes`: free text

## Official Tool Families

The v1 families are:

### `ripgrep`

Purpose:

Measure discovery efficiency when the agent must locate relevant code or docs quickly.

Task shape:

* find the correct implementation area
* confirm the target path
* avoid broad file opening

Baseline:

* plain shell discovery without `ripgrep`

Variant:

* step requires `ripgrep`

### `qmd`

Purpose:

Measure retrieval efficiency when the agent must answer a repo or documentation question from a narrow passage.

Baseline:

* raw file reading and ordinary shell navigation

Variant:

* step requires `qmd`

### `rtk`

Purpose:

Measure whether shell-output compression reduces token load without hiding critical errors.

Baseline:

* raw command output delivered to the agent

Variant:

* step requires `rtk`

### `fastmod`

Purpose:

Measure token and correctness effects on repetitive text-shaped changes.

Baseline:

* agent performs edits without `fastmod`

Variant:

* step requires `fastmod`

### `ast-grep`

Purpose:

Measure token and correctness effects on syntax-shaped rewrites.

Baseline:

* agent performs equivalent edits without `ast-grep`

Variant:

* step requires `ast-grep`

### `comby`

Purpose:

Measure token and correctness effects on structural but tool-expressible rewrites.

Baseline:

* agent performs equivalent edits without `comby`

Variant:

* step requires `comby`

## Official Task Inventory

V1 should start with 12 official tasks.

### `ripgrep`

* Task 1: locate the implementation and config path for a narrowly defined behavior
* Task 2: locate all relevant references for a targeted change with minimal broad reads

### `qmd`

* Task 1: answer a Cassandra doc or architecture question from a narrow source passage
* Task 2: retrieve the minimal context needed to support a precise code change

### `rtk`

* Task 1: interpret noisy build or test output to identify the actionable failure
* Task 2: compress large validation output while preserving the error that should drive the next step

### `fastmod`

* Task 1: repeated text replacement across multiple files
* Task 2: rename or config migration that is text-shaped rather than syntax-shaped

### `ast-grep`

* Task 1: syntax-aware call-site rewrite
* Task 2: structured API migration in Java source

### `comby`

* Task 1: structural pattern rewrite that is awkward for plain text replacement
* Task 2: repeated code pattern adjustment where comby templates fit well

## Team Structure

Use one integrator and four pods.

### Integrator

Owns:

* benchmark contract
* merge sequencing
* shared interfaces
* phase gates
* final claim approval

### Pod A: Harness and agent adapters

Owns:

* `benchmarks/harness/`
* `agents/`
* `schemas/`

Responsibilities:

* runner CLI
* step executor
* Cassandra workspace setup
* agent qualification harness
* token extraction
* run validity classification

### Pod B: Cassandra tasks and validation

Owns:

* `benchmarks/tasks/cassandra/`
* `benchmarks/repos/cassandra/`

Responsibilities:

* select pinned Cassandra commit
* author official tasks
* author appendix workflows
* define validation commands
* define human review triggers

### Pod C: Tool wrappers

Owns:

* `tools/`

Responsibilities:

* implement wrappers for all six tools
* baseline tool-removal support
* invocation trace consistency
* dependency detection

### Pod D: Reporting and publication

Owns:

* `charts/`
* findings docs
* scorecard generation

Responsibilities:

* scorecards
* qualification reports
* appendix reports
* publication bundle

## Coordination Rules

The team needs explicit operating rules or the benchmark will drift.

### Rule 1: Contract first

No pod should build against a guessed interface. Shared schemas and adapter contracts must merge before downstream work starts.

### Rule 2: Disjoint write scopes

Pods own different directories. Only the integrator edits shared cross-cutting docs and interfaces after review.

### Rule 3: Artifact-based handoff

Every handoff must include runnable artifacts:

* sample task manifest
* sample run record
* sample qualification record
* fixture trace
* validation example

### Rule 4: Small merges

Merge by contract milestone, not by long-lived branch.

### Rule 5: CI is mandatory

Every merge should run:

* schema validation
* unit tests
* fixture tests
* one smoke qualification run
* one smoke benchmark run

## Ordered Build Priorities

This is the actual build order.

### P0: Enforcement and observability

Before anything else:

* task schema
* run schema
* qualification schema
* step enforcement model
* agent adapter interface
* reported-token extraction path
* run validity rules

### P1: One end-to-end family on Cassandra

After the contract:

* one qualified agent
* one official tool family
* two tasks
* baseline plus tool variant
* automated validation
* scorecard output

### P2: Full official tool coverage

Then:

* all six tool families
* two tasks per family
* repeated runs
* official scorecard for the first qualified agent

### P3: Appendix workflows and publication bundle

Then:

* mixed-tool appendix tasks
* methodology docs
* findings docs
* qualification appendix for non-qualified agents

### P4: Additional agents

Only after the benchmark is stable:

* qualify remaining agents
* run the unchanged official suite
* publish cross-agent comparisons

## Detailed Phase Plan

## Phase 0: Contract Lock

Duration:

* 3 to 5 working days

Objective:

Turn the benchmark rules into executable contracts.

Deliverables:

* repository scaffold
* runner CLI skeleton
* task manifest format with phased steps
* qualification record format
* run record format
* event stream format
* agent adapter interface
* tool wrapper interface
* run validity and rejection rules
* canonical prompt pack template

Exit criteria:

* every official rule in this document is represented somewhere executable
* a pod can build without guessing how a run should be judged

## Phase 1: Qualification and Pilot Family

Duration:

* 1 week

Objective:

Qualify agents and prove the first official family end to end.

Recommended first family:

* `ripgrep` or `fastmod`

Why:

* easy to enforce
* easy to audit
* easy to validate

Deliverables:

* qualification probes for `codex`, `claude`, and `gemini-cli`
* one qualified agent or an explicit no-qualification report
* first pinned Cassandra commit
* two tasks for the pilot family
* baseline and enforced-tool variants
* first official scorecard draft

Exit criteria:

* at least one agent qualifies
* one tool family runs cleanly through baseline and variant paths
* official metrics can be produced without manual intervention

## Phase 2: Full Official Coverage

Duration:

* 2 to 3 weeks

Objective:

Complete the official v1 scorecard for one qualified agent.

Deliverables:

* all six tool wrappers
* 12 official tasks
* baseline and tool variants for all tasks
* repeated runs for stability
* official scorecards by tool family

Exit criteria:

* all six tools appear in official results
* every official run has reported token counts
* every task has automated validation
* scorecards show tokens, correctness, and time side by side

## Phase 3: Appendix and Release Pack

Duration:

* 1 to 2 weeks

Objective:

Turn the internal benchmark into a release-quality artifact.

Deliverables:

* mixed-tool appendix workflows
* methodology document
* findings report
* qualification appendix
* reproduction instructions

Exit criteria:

* a third party can understand the method and rerun the suite
* the public claim set matches the actual benchmark limits

## Phase 4: Multi-Agent Expansion

Duration:

* ongoing after initial release

Objective:

Expand official coverage to more qualified agents without changing the benchmark contract.

Deliverables:

* additional agent adapters as needed
* qualification reruns
* unchanged official suite executed on new qualified agents

Exit criteria:

* cross-agent results are comparable because the benchmark itself did not move

## Phase 0 Issue List

These are the first issues to open.

### Integrator

* approve this implementation plan
* create repo-wide naming conventions
* define release gates

### Pod A

* scaffold `pyproject.toml`
* add `uv` tasks for test, lint, schema-check, and smoke-run
* implement adapter base classes
* implement qualification probe runner
* implement step environment restriction
* implement event writer

### Pod B

* select and pin Cassandra commit
* define task authoring template
* write first two pilot tasks
* define validation command template
* define human review trigger rules

### Pod C

* implement tool wrapper base
* implement `ripgrep` wrapper
* implement `fastmod` wrapper
* implement invocation trace writer
* define wrapper manifest format

### Pod D

* define scorecard shape
* define qualification report shape
* implement run summary generator
* define public findings template

## Minimum Acceptance Gates

Do not broaden scope until these gates pass.

### Gate 0: Contract gate

Pass when:

* schemas validate
* sample manifests exist
* one smoke qualification run works

### Gate 1: Pilot gate

Pass when:

* one agent qualifies
* one tool family completes baseline and variant runs
* reported tokens are captured automatically
* validation is automated

### Gate 2: Coverage gate

Pass when:

* all six tool families are present
* all twelve tasks are runnable
* repeated runs produce stable artifact shapes

### Gate 3: Release gate

Pass when:

* scorecards are reproducible
* invalid runs are excluded correctly
* qualification appendix exists
* reproduction steps are documented

## Publication Rules

To keep the release credible:

* do not mix reported and estimated token metrics in official tables
* do not include invalid runs in official comparisons
* do not promote appendix workflows as primary evidence
* do not claim cross-agent comparability until the agents are qualified under the same contract
* do not broaden to more repos before Cassandra v1 is stable

## Fastest Credible Release Path

If schedule pressure is high, use this order:

1. finish Phase 0
2. qualify agents
3. pick the first qualified agent
4. complete one pilot family
5. expand to all six families
6. publish the single-agent official scorecard
7. add appendix workflows
8. qualify and add more agents later

This keeps the benchmark honest while still shipping quickly.

## Final Recommendation

Treat v1 as a controlled measurement product, not a general platform.

The true critical path is:

1. enforce the tool contract
2. capture reported tokens reliably
3. qualify the agents
4. prove one family
5. cover all six tools on Cassandra
6. publish the single-agent scorecard
7. expand agents only after the method is stable

If the team protects that order, the first public benchmark will be narrow, useful, and defensible.
