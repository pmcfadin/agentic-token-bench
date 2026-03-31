# Qualification Appendix

This appendix is the public-facing record of which agents have qualified for official benchmark
scorecards and which are pending qualification. It covers all three v1 agent adapters:
`claude`, `codex`, and `gemini-cli`.

All three adapters are implemented and pass mock-based unit tests. Live CLI qualification
against real Cassandra tasks has been completed for `claude` and is pending for `codex` and
`gemini-cli`. Pending agents are not eligible for official scorecard inclusion until they
complete a live qualification run.

The source of truth for each agent's qualification status is the corresponding
`benchmarks/qualification/<agent_id>/qualification.json` file. Where the prose below
disagrees with that file, the JSON record takes precedence.

---

## Summary Table

| Agent | Adapter Version | Qualification Status | Notes |
|---|---|---|---|
| `claude` | 0.1.0 | **Qualified** | First qualified agent for v1; all four gates passed on live CLI |
| `codex` | 0.1.0 | **Pending qualification** | Adapter implemented; live CLI run against Cassandra tasks not yet executed |
| `gemini-cli` | 0.1.0 | **Pending qualification** | Adapter implemented; live CLI run against Cassandra tasks not yet executed |

Pending agents must not appear in official scorecard tables. They will be re-evaluated
when a live qualification run is scheduled.

---

## Qualified Agents

### claude (adapter 0.1.0, qualified 2026-03-31)

Claude is the first agent to qualify for v1 official benchmark runs. All four qualification
gates passed during live CLI probing.

#### Gate Summary

| Gate | Result |
|---|---|
| Reported-token gate | pass |
| Forced-tool gate | pass |
| Audit-trace gate | pass |
| Run-completeness gate | pass |

#### Adapter Details

**Binary**: `claude` (Claude Code CLI, reference path
`/Applications/cmux.app/Contents/Resources/bin/claude`)

**Invocation flags**: `-p <prompt> --output-format json`

**Adapter version**: 0.1.0

#### Token Extraction Method

```
Source: stdout JSON payload from --output-format json
JSON path: .usage.input_tokens, .usage.output_tokens
Pattern: json.loads(stdout)["usage"]
Total tokens: input_tokens + output_tokens (computed; not a separate field)
Stability notes: Token counts appear only when the agent completes normally.
  Interrupted runs (SIGTERM, timeout, non-zero exit) do not emit a usage block.
  Cache fields (cache_creation_input_tokens, cache_read_input_tokens) are present
  in the usage block but are not counted as part of the primary I/O totals.
Fallback: Run is marked invalid if the usage block is absent or unparseable.
```

Example JSON output containing the token block:

```json
{
  "type": "result",
  "subtype": "success",
  "result": "...",
  "usage": {
    "input_tokens": 3,
    "cache_creation_input_tokens": 12447,
    "cache_read_input_tokens": 6561,
    "output_tokens": 4
  }
}
```

#### Probe Results

| Probe | Result | Notes |
|---|---|---|
| Token reporting probe | pass | `usage.input_tokens` and `usage.output_tokens` extracted successfully |
| No-tool step probe | pass | Exit status 0; all artifacts written |
| Forced single-tool step probe | pass | `--allowedTools` flag respected; required tool appeared in trace |
| Blocked-tool failure probe | pass | Blocked tool invocation detected; run marked invalid |
| Completion and artifact probe | pass | All expected artifacts present; validation executed |

#### Evidence Paths

```
benchmarks/qualification/claude/token-reporting-probe/
benchmarks/qualification/claude/no-tool-step-probe/
benchmarks/qualification/claude/forced-tool-step-probe/
benchmarks/qualification/claude/blocked-tool-probe/
benchmarks/qualification/claude/completion-artifact-probe/
```

---

## Pending Qualification

Agents in this section have fully implemented adapters that pass mock-based tests. They
have not yet completed a live qualification run against real Cassandra tasks. They are
listed here so their status is transparent. They are not eligible for official scorecard
inclusion until they pass all four qualification gates on a live run.

---

### codex (adapter 0.1.0, status pending as of 2026-03-31)

The `CodexAdapter` wraps the OpenAI Codex CLI (`codex exec`). The adapter is complete and
passes all unit tests using mock subprocess output.

#### Gate Summary (live run not yet executed)

| Gate | Status |
|---|---|
| Reported-token gate | pending |
| Forced-tool gate | pending |
| Audit-trace gate | pending |
| Run-completeness gate | pending |

#### Adapter Details

**Binary**: `codex` (OpenAI Codex CLI, resolved via `$PATH`)

**Invocation flags**: `exec --full-auto --json --ephemeral --skip-git-repo-check <prompt>`

**Adapter version**: 0.1.0

#### Token Extraction Method

```
Source: JSON Lines (JSONL) emitted to stdout via the --json flag
Event type targeted: turn.completed (last occurrence wins)
JSON path: event["usage"]["input_tokens"], event["usage"]["output_tokens"]
Total tokens: derived as input_tokens + output_tokens if total_tokens absent from event
Fallback (plain text): regex scan for "tokens used\n<formatted integer>" in stdout;
  plain-text mode does not break out input/output counts separately.
Stability notes: Token counts appear in the last turn.completed event. Runs that do not
  emit this event (crash, timeout, non-zero exit) will not produce token data. The
  plain-text fallback captures only total_tokens and sets input/output to 0, which
  does not satisfy the reported-token gate requirements for official runs.
Fallback: ValueError raised when no token information is found; run is marked invalid.
```

#### Probe Results (mock-based only)

| Probe | Result | Notes |
|---|---|---|
| Token reporting probe | pending live run | Mock tests pass; live `turn.completed` event parsing not yet validated |
| No-tool step probe | pending live run | Mock tests pass; live exit status and artifact capture not yet validated |
| Forced single-tool step probe | pending live run | Mock tests pass; `--allowedTools` or equivalent enforcement not yet validated live |
| Blocked-tool failure probe | pending live run | Mock tests pass; blocked tool detection not yet validated live |
| Completion and artifact probe | pending live run | Mock tests pass; full artifact set not yet validated live |

#### What Needs to Change for Full Qualification

1. Install the `codex` binary and ensure it is reachable on `$PATH` in the CI or
   qualification environment.
2. Run `qualify-agent codex` against a live Cassandra workspace.
3. Confirm that a `turn.completed` event with a `usage` block appears in the JSONL output
   for each step. The plain-text fallback is insufficient for official runs because it does
   not break out `input_tokens` and `output_tokens` separately.
4. Confirm that the forced-tool enforcement path (step `PATH` restriction) works correctly
   with the `codex exec --full-auto` execution model.
5. Confirm that the `--ephemeral` and `--skip-git-repo-check` flags are compatible with the
   Cassandra workspace setup in the harness.

---

### gemini-cli (adapter 0.1.0, status pending as of 2026-03-31)

The `GeminiCliAdapter` wraps the Gemini CLI binary (`gemini`). The adapter is complete and
passes all unit tests using mock subprocess output.

#### Gate Summary (live run not yet executed)

| Gate | Status |
|---|---|
| Reported-token gate | pending |
| Forced-tool gate | pending |
| Audit-trace gate | pending |
| Run-completeness gate | pending |

#### Adapter Details

**Binary**: `gemini` (Gemini CLI, resolved via `$PATH`)

**Invocation flags**: `-p <prompt> --output-format stream-json`

**Adapter version**: 0.1.0

#### Token Extraction Method

```
Source: stream-json output emitted to stdout via --output-format stream-json
Event type targeted: final result line with type == "result"
JSON path: result_line["stats"]["input_tokens"], result_line["stats"]["output_tokens"],
           result_line["stats"]["total_tokens"]
Fallback: regex pattern matching "input_tokens: N ... output_tokens: N ... total_tokens: N"
  against combined stdout + stderr.
Stability notes: Token counts appear only in the terminal result line. Interrupted runs
  may not emit this line. The regex fallback handles alternate plain-text layouts but
  may break if the Gemini CLI changes its output format.
Fallback: Returns (0, 0, 0, "") when no token data is found; run is marked invalid.
```

Example result line containing the token block:

```json
{"type":"result","status":"success","stats":{"total_tokens":512,"input_tokens":480,"output_tokens":32}}
```

#### Probe Results (mock-based only)

| Probe | Result | Notes |
|---|---|---|
| Token reporting probe | pending live run | Mock tests pass; live stats block parsing not yet validated |
| No-tool step probe | pending live run | Mock tests pass; live exit status and artifact capture not yet validated |
| Forced single-tool step probe | pending live run | pending — forced_tool_support is explicitly set to False in the basic probe; deeper probe not yet implemented |
| Blocked-tool failure probe | pending live run | Mock tests pass; blocked tool detection not yet validated live |
| Completion and artifact probe | pending live run | Mock tests pass; full artifact set not yet validated live |

#### What Needs to Change for Full Qualification

1. Install the `gemini` binary and ensure it is reachable on `$PATH` in the CI or
   qualification environment.
2. Run `qualify-agent gemini-cli` against a live Cassandra workspace.
3. Confirm that the `--output-format stream-json` flag is available in the installed
   version and that the `stats` block in the result line contains `input_tokens`,
   `output_tokens`, and `total_tokens` as separate fields.
4. Implement and run the forced-tool probe. The basic `probe()` method in `GeminiCliAdapter`
   explicitly sets `forced_tool_support=False` because forced-tool validation requires a
   deeper probe beyond the minimal binary invocation check. A dedicated forced-tool step
   probe must be run and must pass before the forced-tool gate can be marked as passed.
5. Confirm that the `step_env` PATH-restriction mechanism works correctly with the Gemini
   CLI's execution model.

---

## Guidance for Qualification

Any agent adapter that wants to appear in official benchmark scorecards must pass all four
qualification gates on a live run. The steps below apply to both `codex` and `gemini-cli`
and to any future adapters.

### Step 1 — Binary availability

Ensure the agent CLI binary is installed and on `$PATH` in the environment where
qualification will run. The adapter's `probe()` method checks for the binary first and
returns an immediate `not_qualified` result if the binary is missing.

### Step 2 — Run the qualification command

```bash
python -m benchmarks.harness.cli qualify-agent <agent_id>
```

This command runs all five probes and writes results to
`benchmarks/qualification/<agent_id>/`.

### Step 3 — Check the four gates

Review `benchmarks/qualification/<agent_id>/qualification.json` and confirm all four
gate fields are `true`:

- `reported_token_support` — token counts can be extracted from agent output
- `forced_tool_support` — required tools appear in the trace when mandated
- `trace_support` — audit trace is sufficient to reconstruct step progress
- `run_completion_support` — harness can capture all required outputs without manual intervention

### Step 4 — Token extraction must use reported values

Estimated token counts are not acceptable in official runs. If the CLI does not emit
reported token counts in a structured form that can be parsed programmatically, the
reported-token gate will not pass. Substituting estimated counts is grounds for
disqualification regardless of other gate results.

### Step 5 — All five probes must pass

Each probe targets one or more gates. All five must pass:

| Probe | Gate(s) |
|---|---|
| Token reporting probe | Reported-token gate |
| No-tool step probe | Run-completeness gate |
| Forced single-tool step probe | Forced-tool gate |
| Blocked-tool failure probe | Forced-tool gate |
| Completion and artifact probe | Run-completeness gate |

### Step 6 — Update this appendix

Once an agent qualifies, move it from the "Pending Qualification" section to the
"Qualified Agents" section. Update the gate summary table, fill in the actual probe
results with real token counts and invocation evidence, and record the qualification date.

---

## Implementation Note

All three adapters (`ClaudeAdapter`, `CodexAdapter`, `GeminiCliAdapter`) are fully
implemented in `agents/claude/adapter.py`, `agents/codex/adapter.py`, and
`agents/gemini_cli/adapter.py` respectively. Each adapter implements the full
`AgentAdapter` interface: `probe()`, `run_step()`, `extract_reported_tokens()`, and
`normalize_final_status()`. Each has a corresponding parser module that handles token
extraction from the CLI's native output format.

Mock-based unit tests covering token extraction, probe logic, and status normalization
pass for all three adapters. What distinguishes `claude` from the other two is that a
live qualification run has been executed, confirming that the token extraction and
tool-enforcement mechanisms work correctly against a real CLI invocation on Cassandra
tasks. `codex` and `gemini-cli` will be promoted from pending to qualified once their
respective live qualification runs complete successfully.
