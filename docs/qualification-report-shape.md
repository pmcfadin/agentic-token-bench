# Qualification Report Shape

This document describes the qualification report format produced when an agent adapter runs through the qualification protocol. The report is the authoritative record of whether an agent may appear in official benchmark scorecards.

Reference: `docs/plans/2026-03-31-v1-build-plan-design.md` — "Agent Qualification Protocol" and "Qualification outputs".

---

## Overview

Before any agent enters official benchmark runs, it must pass a qualification round. The qualification round runs a fixed set of probes against the agent adapter. Each probe targets one qualification gate. The results are collected into a qualification record, which is written as a machine-readable JSON file and summarised in a human-readable markdown report.

There are two possible outcomes:

- `qualified` — the agent passed all four gates and may appear in official scorecards.
- `not_qualified` — one or more gates failed; the agent is listed in the qualification appendix with the failure reason.

---

## Qualification Gates

An agent must pass all four gates. Failing any single gate means the overall result is `not_qualified`.

| Gate | Field | Description |
|---|---|---|
| Reported-token gate | `reported_token_support` | The CLI exposes stable reported token counts that can be extracted programmatically. |
| Forced-tool gate | `forced_tool_support` | The agent can operate inside a constrained step environment and required tools appear in the trace when mandated. |
| Audit-trace gate | `trace_support` | The run emits enough observable output to reconstruct tool usage and step progress. |
| Run-completeness gate | `run_completion_support` | The harness can capture start, finish, tokens, artifacts, validation output, and final status without manual intervention. |

---

## Qualification Probes

Every adapter ships at least five probes. Each probe targets one or more gates.

| Probe | Gate(s) exercised | Description |
|---|---|---|
| Token reporting probe | Reported-token gate | Run a minimal task and confirm that `input_tokens`, `output_tokens`, and `total_tokens` can be parsed from agent output. |
| No-tool step probe | Run-completeness gate | Run a step with no required tool and no blocked tools; confirm the run starts, completes, and artifacts are written. |
| Forced single-tool step probe | Forced-tool gate | Run a step that requires one specific tool; confirm the tool appears in the invocation trace. |
| Blocked-tool failure probe | Forced-tool gate | Run a step that blocks a tool and attempt to invoke it; confirm the harness marks the run invalid. |
| Completion and artifact probe | Run-completeness gate | Run a full minimal task; confirm all expected artifacts are present in the artifact directory. |

---

## Per-Agent Qualification Summary

The top-level qualification summary covers the agent as a whole.

### Data model

Defined in `benchmarks/harness/models.py` as `QualificationRecord` and in `schemas/qualification.schema.json`.

| Field | Type | Description |
|---|---|---|
| `agent_id` | `str` | Canonical agent identifier (e.g. `"claude"`, `"codex"`, `"gemini-cli"`). |
| `adapter_version` | `str` | Version string of the adapter that ran the probes (e.g. `"0.1.0"`). |
| `qualified` | `bool` | `true` if all four gates passed; `false` otherwise. |
| `reported_token_support` | `bool` | Whether the token reporting probe passed. |
| `forced_tool_support` | `bool` | Whether the forced-tool probe passed. |
| `trace_support` | `bool` | Whether the audit-trace gate was satisfied. |
| `run_completion_support` | `bool` | Whether the run-completeness probe passed. |
| `failure_reason` | `str \| null` | Human-readable explanation of why the agent did not qualify. `null` when `qualified` is `true`. |
| `evidence_paths` | `list[str]` | Paths to the probe artifact directories that back the qualification decision. |

All fields serialise to the public schema at `schemas/qualification.schema.json`. Internal adapter state may be richer, but the public record must conform to this shape.

---

## Per-Probe Results

Each probe produces its own result section. The section records whether the probe passed, the specific check performed, and the evidence collected.

### Token reporting probe

This probe confirms that the adapter can extract reported token counts reliably.

Fields recorded per probe run:

| Field | Description |
|---|---|
| `probe_name` | `"token_reporting"` |
| `passed` | Whether the probe succeeded. |
| `input_tokens` | Extracted input token count, or `null` if extraction failed. |
| `output_tokens` | Extracted output token count, or `null` if extraction failed. |
| `total_tokens` | Extracted total token count, or `null` if extraction failed. |
| `evidence_snippet` | The raw text from agent output from which the counts were parsed. |
| `extraction_method` | Short description of how the counts were found (see Token Extraction Method Summary). |
| `failure_detail` | Description of why extraction failed, or `null` if it succeeded. |

This probe fails if any of `input_tokens`, `output_tokens`, or `total_tokens` cannot be extracted. A run with missing token counts is not an official run.

### No-tool step probe

This probe confirms the agent can complete a step with no tool constraints and that the harness can capture the result.

Fields recorded per probe run:

| Field | Description |
|---|---|
| `probe_name` | `"no_tool_step"` |
| `passed` | Whether the probe succeeded. |
| `exit_status` | Process exit code from the agent CLI. |
| `artifacts_present` | List of artifact filenames found in the probe artifact directory. |
| `failure_detail` | Description of the failure, or `null` if it succeeded. |

### Forced single-tool step probe

This probe confirms the agent uses a required tool when one is mandated for a step.

Fields recorded per probe run:

| Field | Description |
|---|---|
| `probe_name` | `"forced_tool_step"` |
| `passed` | Whether the probe succeeded. |
| `required_tool` | Name of the tool that was required for the step. |
| `tool_invocation_found` | Whether at least one successful invocation of the required tool appeared in `tool_invocations.jsonl`. |
| `invocation_count` | Number of invocations of the required tool recorded in the trace. |
| `failure_detail` | Description of the failure, or `null` if it succeeded. |

### Blocked-tool failure probe

This probe confirms the harness correctly detects and rejects use of a blocked tool.

Fields recorded per probe run:

| Field | Description |
|---|---|
| `probe_name` | `"blocked_tool"` |
| `passed` | Whether the probe succeeded (i.e. the harness correctly invalidated the run). |
| `blocked_tool` | Name of the tool that was blocked. |
| `violation_detected` | Whether the harness detected the blocked tool invocation. |
| `run_marked_invalid` | Whether the run was classified as `invalid` after the violation. |
| `failure_detail` | Description of the failure, or `null` if it succeeded. |

### Completion and artifact probe

This probe confirms that a full minimal task run produces all required artifacts without manual intervention.

Fields recorded per probe run:

| Field | Description |
|---|---|
| `probe_name` | `"completion_and_artifact"` |
| `passed` | Whether the probe succeeded. |
| `artifacts_expected` | List of artifact filenames that must be present. |
| `artifacts_found` | List of artifact filenames actually found in the artifact directory. |
| `artifacts_missing` | List of expected filenames that were absent. |
| `validation_executed` | Whether the validation command ran to completion. |
| `failure_detail` | Description of the failure, or `null` if it succeeded. |

Expected artifact filenames for a complete run:

```
run.json
trace.jsonl
prompt.txt
final_answer.txt
validation.json
stdout.log
stderr.log
token_evidence.txt
tool_invocations.jsonl
```

---

## Token Extraction Method Summary

Each adapter must document how it extracts token counts from agent output. This summary appears in the qualification record and in the qualification appendix.

The summary must state:

1. **Source** — where the counts come from (e.g. final summary line in stdout, structured JSON output, a sidecar file, or a parsed stderr pattern).
2. **Pattern** — the specific regex, JSON path, or parsing rule used to locate the counts.
3. **Stability notes** — any known conditions under which the extraction may fail or produce incorrect values.
4. **Fallback behaviour** — what the adapter does when extraction fails (the correct answer is: reject the run as invalid, not substitute estimated counts).

Example summary:

```
Source: stdout final summary block
Pattern: regex r"Usage:\s+(\d+)\s+input,\s+(\d+)\s+output,\s+(\d+)\s+total"
Stability notes: Counts appear only when the agent completes normally. Interrupted runs
  (SIGTERM, timeout) do not emit the summary block.
Fallback: Run is marked invalid if the pattern does not match.
```

Estimated token counts are never acceptable in official runs. If the extraction method relies on estimation rather than reported values, the agent does not qualify.

---

## Trace Evidence Summary

Each qualification run must produce enough observable output to audit tool usage and step progress. The trace evidence summary documents what was captured.

The summary must cover:

1. **Trace file location** — path to `trace.jsonl` in the probe artifact directory.
2. **Event types observed** — list of distinct `event_type` values found in the trace.
3. **Tool invocation log** — path to `tool_invocations.jsonl` and a count of recorded invocations.
4. **Step coverage** — which step IDs appear in the trace.
5. **Gaps or missing coverage** — any steps or event types that were expected but absent.

A trace is considered sufficient when it allows a reviewer to confirm:

- which tools were invoked in which step
- whether required tools were actually called
- whether blocked tools were called
- when the run started and finished

If the trace cannot support any of these inferences, the audit-trace gate fails.

---

## Failure Reasons When Not Qualified

When `qualified` is `false`, the `failure_reason` field must contain a specific, actionable description. Use the canonical phrases below. Supplement with detail as needed.

| Cause | Canonical failure reason |
|---|---|
| Token extraction failed | `"Token extraction failed: <extraction_method> returned null for one or more of input_tokens, output_tokens, total_tokens."` |
| Tokens estimated, not reported | `"Token counts are estimated, not reported. Official runs require reported values only."` |
| Required tool not used | `"Forced-tool probe failed: required tool '<tool_name>' was not found in tool_invocations.jsonl for step '<step_id>'."` |
| Blocked tool not detected | `"Blocked-tool probe failed: use of blocked tool '<tool_name>' was not detected or did not invalidate the run."` |
| Trace insufficient | `"Audit-trace gate failed: trace.jsonl does not contain enough events to reconstruct step progress and tool usage."` |
| Artifacts missing | `"Completion probe failed: the following expected artifacts were absent: <comma-separated list>."` |
| Validation did not execute | `"Run-completeness gate failed: validation command did not execute."` |
| Agent CLI did not start | `"Agent CLI failed to start. Check stderr.log for details."` |

When multiple gates fail, record each failure in the `failure_reason` field as a semicolon-separated list. The field is free text after the canonical phrase.

---

## Example Report: Markdown Format

This is the markdown summary format written to `benchmarks/qualification/<agent_id>/qualification-report.md`.

```markdown
# Qualification Report: claude

**Adapter version**: 0.1.0
**Date**: 2026-03-31
**Result**: QUALIFIED

## Gate Summary

| Gate | Passed |
|---|---|
| Reported-token gate | yes |
| Forced-tool gate | yes |
| Audit-trace gate | yes |
| Run-completeness gate | yes |

## Probe Results

### Token Reporting Probe

- Result: PASS
- Input tokens: 1842
- Output tokens: 312
- Total tokens: 2154
- Extraction method: stdout final summary block, regex `Usage:\s+(\d+)\s+input,\s+(\d+)\s+output,\s+(\d+)\s+total`
- Evidence snippet: `Usage: 1842 input, 312 output, 2154 total`

### No-Tool Step Probe

- Result: PASS
- Exit status: 0
- Artifacts present: run.json, trace.jsonl, prompt.txt, final_answer.txt, stdout.log, stderr.log, token_evidence.txt, tool_invocations.jsonl

### Forced Single-Tool Step Probe

- Result: PASS
- Required tool: ripgrep
- Tool invocation found: yes
- Invocation count: 3

### Blocked-Tool Failure Probe

- Result: PASS
- Blocked tool: qmd
- Violation detected: yes
- Run marked invalid: yes

### Completion and Artifact Probe

- Result: PASS
- Artifacts expected: run.json, trace.jsonl, prompt.txt, final_answer.txt, validation.json, stdout.log, stderr.log, token_evidence.txt, tool_invocations.jsonl
- Artifacts found: all present
- Validation executed: yes

## Token Extraction Method

Source: stdout final summary block
Pattern: `Usage:\s+(\d+)\s+input,\s+(\d+)\s+output,\s+(\d+)\s+total`
Stability notes: Counts appear only when the agent completes normally. Interrupted runs do not emit the summary block.
Fallback: Run is marked invalid if the pattern does not match.

## Trace Evidence

- Trace file: benchmarks/qualification/claude/token-reporting-probe/trace.jsonl
- Event types observed: step_start, tool_invoke, tool_result, step_end, run_complete
- Tool invocation log: benchmarks/qualification/claude/token-reporting-probe/tool_invocations.jsonl (4 invocations)
- Step coverage: discover, summarize

## Evidence Paths

- benchmarks/qualification/claude/token-reporting-probe/
- benchmarks/qualification/claude/no-tool-step-probe/
- benchmarks/qualification/claude/forced-tool-step-probe/
- benchmarks/qualification/claude/blocked-tool-probe/
- benchmarks/qualification/claude/completion-artifact-probe/
```

---

## Example Report: JSON Format

This is the machine-readable record written to `benchmarks/qualification/<agent_id>/qualification.json`. It conforms to `schemas/qualification.schema.json`.

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
  "evidence_paths": [
    "benchmarks/qualification/claude/token-reporting-probe/",
    "benchmarks/qualification/claude/no-tool-step-probe/",
    "benchmarks/qualification/claude/forced-tool-step-probe/",
    "benchmarks/qualification/claude/blocked-tool-probe/",
    "benchmarks/qualification/claude/completion-artifact-probe/"
  ]
}
```

### Example: Not-qualified agent

```json
{
  "agent_id": "gemini-cli",
  "adapter_version": "0.2.1",
  "qualified": false,
  "reported_token_support": false,
  "forced_tool_support": true,
  "trace_support": true,
  "run_completion_support": true,
  "failure_reason": "Token extraction failed: stdout final summary block pattern returned null for input_tokens and output_tokens. Token counts are estimated, not reported. Official runs require reported values only.",
  "evidence_paths": [
    "benchmarks/qualification/gemini-cli/token-reporting-probe/",
    "benchmarks/qualification/gemini-cli/no-tool-step-probe/",
    "benchmarks/qualification/gemini-cli/forced-tool-step-probe/",
    "benchmarks/qualification/gemini-cli/blocked-tool-probe/",
    "benchmarks/qualification/gemini-cli/completion-artifact-probe/"
  ]
}
```

---

## Qualification Artifact Directory Layout

Each probe run writes its artifacts to an isolated subdirectory.

```
benchmarks/qualification/<agent_id>/
  qualification.json
  qualification-report.md
  token-reporting-probe/
    run.json
    trace.jsonl
    stdout.log
    stderr.log
    token_evidence.txt
    tool_invocations.jsonl
  no-tool-step-probe/
    run.json
    trace.jsonl
    stdout.log
    stderr.log
    tool_invocations.jsonl
  forced-tool-step-probe/
    run.json
    trace.jsonl
    stdout.log
    stderr.log
    tool_invocations.jsonl
  blocked-tool-probe/
    run.json
    trace.jsonl
    stdout.log
    stderr.log
    tool_invocations.jsonl
  completion-artifact-probe/
    run.json
    trace.jsonl
    prompt.txt
    final_answer.txt
    validation.json
    stdout.log
    stderr.log
    token_evidence.txt
    tool_invocations.jsonl
```

---

## Integration with the Qualification Appendix

The qualification appendix is part of the Phase 3 release pack. It is the public-facing record of which agents qualified and why others did not.

### Qualified agents

For each qualified agent, the appendix includes:

- The qualification summary table (all four gates: pass).
- The token extraction method summary.
- A link to the qualification artifact directory.
- The adapter version and qualification date.

### Not-qualified agents

For each not-qualified agent, the appendix includes:

- The qualification summary table showing which gates passed and which failed.
- The `failure_reason` text from the qualification record.
- The adapter version and qualification date.
- A note that the agent is pending qualification and will be re-evaluated when the issue is resolved.

Not-qualified agents must not appear in official scorecard tables. They may appear in a separate "pending qualification" section clearly labeled as such.

### Appendix structure

```
## Qualification Appendix

### Qualified Agents

#### claude (adapter 0.1.0, qualified 2026-03-31)

| Gate | Result |
|---|---|
| Reported-token gate | pass |
| Forced-tool gate | pass |
| Audit-trace gate | pass |
| Run-completeness gate | pass |

Token extraction: stdout final summary block, regex match.

### Pending Qualification

#### gemini-cli (adapter 0.2.1, evaluated 2026-03-31)

| Gate | Result |
|---|---|
| Reported-token gate | fail |
| Forced-tool gate | pass |
| Audit-trace gate | pass |
| Run-completeness gate | pass |

Failure reason: Token extraction failed. Counts are estimated, not reported.
Status: Not eligible for official scorecards until token reporting is resolved.
```

### Source of truth

The `qualification.json` file for each agent is the source of truth. The appendix prose is derived from these records. If the appendix disagrees with the JSON record, the JSON record takes precedence.

---

## Notes

- Every qualification run must use a real probe task, not a mocked adapter. The probes exercise the live CLI.
- Qualification must be re-run whenever the adapter version changes. A previously qualified agent is not automatically re-qualified after an adapter update.
- The `qualified` field on `QualificationRecord` is the gate that controls inclusion in official scorecards. Downstream code must check this field, not the individual gate fields.
- All token counts in qualification records use reported values only. Estimated counts are grounds for immediate disqualification.
- Evidence paths in `evidence_paths` must point to real artifact directories that were produced during the qualification run.
