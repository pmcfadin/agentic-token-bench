# Repo-Wide Naming Conventions

This document defines canonical naming rules for all identifiers in
`agentic-token-bench`. These conventions apply across task manifests, run
records, schemas, artifact directories, branch names, and source code.

Reference: `docs/plans/2026-03-31-v1-build-plan-design.md`

---

## Task IDs

Pattern: `cassandra-{family}-{NN}`

- `cassandra` is the fixed repo prefix for v1
- `{family}` is the lowercase, hyphenated family name (see Family Names below)
- `{NN}` is a zero-padded two-digit sequence number starting at `01`

Examples:

```
cassandra-ripgrep-01
cassandra-ripgrep-02
cassandra-qmd-01
cassandra-ast-grep-02
cassandra-fastmod-01
cassandra-comby-02
cassandra-rtk-01
```

Rules:

- All lowercase
- Components separated by hyphens
- Sequence numbers are always two digits (`01`, not `1`)
- Do not reuse task IDs once a task has been published or executed

---

## Run IDs

Pattern: `{task_id}-{variant}-{agent_id}-{YYYYMMDD}T{HHMMSS}`

- `{task_id}` is the full task ID (e.g., `cassandra-ripgrep-01`)
- `{variant}` is either `baseline` or `tool-variant`
- `{agent_id}` is the lowercase, hyphenated agent ID (see Agent IDs below)
- `{YYYYMMDD}T{HHMMSS}` is the UTC wall-clock start time in ISO 8601 compact form

Examples:

```
cassandra-ripgrep-01-baseline-claude-20260401T143022
cassandra-ripgrep-01-tool-variant-claude-20260401T144510
cassandra-qmd-02-baseline-codex-20260402T090015
cassandra-ast-grep-01-tool-variant-gemini-cli-20260403T120300
```

Rules:

- All lowercase except the `T` separator in the timestamp
- Components separated by hyphens except for the `T` separator
- Timestamp is always UTC
- Run IDs must be unique; if two runs of the same task start in the same
  second, append a counter suffix (e.g., `-2`)

---

## Family Names

Family names identify the tool under test in a task family.

Canonical family names:

| Family     | Notes                        |
|------------|------------------------------|
| `ripgrep`  |                              |
| `ast-grep` | hyphen required, not `ast_grep` |
| `qmd`      |                              |
| `rtk`      |                              |
| `fastmod`  |                              |
| `comby`    |                              |

Rules:

- All lowercase
- Use hyphens where the tool name contains a separator (e.g., `ast-grep`)
- Never use underscores in family names
- Family names appear in task IDs, run IDs, schema `family` fields, and
  directory names

---

## Agent IDs

Agent IDs identify the CLI agent under evaluation.

Canonical agent IDs:

| Agent ID     | Notes                              |
|--------------|------------------------------------|
| `claude`     |                                    |
| `codex`      |                                    |
| `gemini-cli` | hyphen required, not `gemini_cli`  |

Rules:

- All lowercase
- Use hyphens where the agent name contains a separator
- Never use underscores in agent IDs
- Agent IDs appear in run IDs, qualification records, schema `agent_id` fields,
  and directory names

Note: Python module names for agents use underscores because Python does not
allow hyphens in identifiers (`agents/gemini_cli/`). The agent ID used in data
records and filenames always uses hyphens (`gemini-cli`).

---

## Artifact Directories

Pattern: `benchmarks/results/{run_id}/`

Each run writes its artifacts to one directory named after the run ID.

Examples:

```
benchmarks/results/cassandra-ripgrep-01-baseline-claude-20260401T143022/
benchmarks/results/cassandra-ripgrep-01-tool-variant-claude-20260401T144510/
benchmarks/results/cassandra-qmd-02-baseline-codex-20260402T090015/
```

Expected contents of each artifact directory:

```
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

Rules:

- Directory name is always the full run ID
- All artifact filenames are lowercase with underscores or dots
- Do not nest run artifact directories inside each other

---

## Branch Names

Pattern: `phase{N}/issue-{N}-{slug}`

- `{N}` in `phase{N}` is the phase number (0, 1, 2, ...)
- `{N}` in `issue-{N}` is the GitHub issue number
- `{slug}` is a short, hyphenated lowercase description of the issue

Examples:

```
phase0/issue-1-repo-scaffold
phase0/issue-3-naming-conventions
phase0/issue-7-adapter-base-class
phase1/issue-14-ripgrep-wrapper
phase2/issue-22-comby-tasks
```

Rules:

- All lowercase
- Phase prefix and issue slug separated by a forward slash
- Slug uses hyphens only, no underscores
- Keep slugs short (three to five words is typical)

---

## Schema Field Names

All JSON Schema field names and Pydantic model attribute names use snake_case.

Examples:

```
task_id
run_id
agent_id
family
pinned_commit
tool_variant_policy
reported_input_tokens
reported_total_tokens
artifact_dir
started_at
finished_at
repair_iterations
```

Rules:

- All lowercase
- Words separated by underscores
- No camelCase, no hyphens in field names
- This applies to both public schema files under `schemas/` and internal
  Pydantic models

---

## Step IDs

Step IDs identify individual phases within a task. The canonical step IDs for
v1 tasks are:

| Step ID    | Purpose                                             |
|------------|-----------------------------------------------------|
| `discover` | Locate relevant source or config areas              |
| `retrieve` | Fetch a narrow passage or document context          |
| `analyze`  | Interpret output or synthesize findings             |
| `edit`     | Apply code or config changes                        |
| `validate` | Confirm that changes or findings meet the contract  |
| `summarize`| Produce the final structured answer                 |

Rules:

- All lowercase
- Single word; no hyphens or underscores
- `step_id` in a task manifest must match one of the canonical IDs above unless
  the task author documents a justified extension
- The `name` field on a step may mirror the `step_id` or provide a short phrase

Example task step using canonical step IDs:

```yaml
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
```

---

## Quick Reference

| Identifier        | Pattern                                                  | Example                                                      |
|-------------------|----------------------------------------------------------|--------------------------------------------------------------|
| Task ID           | `cassandra-{family}-{NN}`                                | `cassandra-ripgrep-01`                                       |
| Run ID            | `{task_id}-{variant}-{agent_id}-{YYYYMMDD}T{HHMMSS}`    | `cassandra-ripgrep-01-baseline-claude-20260401T143022`        |
| Family name       | lowercase, hyphenated                                    | `ripgrep`, `ast-grep`, `qmd`                                 |
| Agent ID          | lowercase, hyphenated                                    | `claude`, `codex`, `gemini-cli`                              |
| Artifact dir      | `benchmarks/results/{run_id}/`                           | `benchmarks/results/cassandra-ripgrep-01-baseline-claude-.../`|
| Branch name       | `phase{N}/issue-{N}-{slug}`                              | `phase0/issue-3-naming-conventions`                          |
| Schema field name | snake_case                                               | `task_id`, `reported_input_tokens`                           |
| Step ID           | lowercase, single word                                   | `discover`, `edit`, `summarize`                              |
