# Qualification Appendix

This appendix is the public-facing record of which agents have qualified for official benchmark
scorecards. It covers all three v1 agent adapters: `claude`, `codex`, and `gemini-cli`.

All three adapters are implemented, pass mock-based unit tests, and have completed live CLI
qualification runs against real Cassandra tasks. All three agents are qualified for official
scorecard inclusion.

The source of truth for each agent's qualification status is the corresponding
`benchmarks/qualification/<agent_id>/qualification.json` file. Where the prose below
disagrees with that file, the JSON record takes precedence.

---

## Summary Table

| Agent | Adapter Version | Qualification Status | Notes |
|---|---|---|---|
| `claude` | 0.1.0 | **Qualified** | All four gates passed on live CLI |
| `codex` | 0.1.0 | **Qualified** | All four gates passed on live CLI |
| `gemini-cli` | 0.1.0 | **Qualified** | All four gates passed on live CLI; token extraction bug #46 is a known issue (see below) |

**Known issue**: The Gemini CLI token extraction path returned 0 tokens for the ripgrep-01
baseline run. This is tracked as issue #46 and is a defect in the extraction pipeline, not
a disqualifying failure — the qualification probes passed, but a production run exposed an
edge case where the token count was not captured. That run's data is excluded from comparison
tables. The bug is pending a fix and a re-run.

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

### codex (adapter 0.1.0, qualified 2026-04-01)

The `CodexAdapter` wraps the OpenAI Codex CLI (`codex exec`). The adapter is complete,
passes all unit tests, and has completed a live qualification run against real Cassandra
tasks. All four gates passed.

#### Gate Summary

| Gate | Result |
|---|---|
| Reported-token gate | pass |
| Forced-tool gate | pass |
| Audit-trace gate | pass |
| Run-completeness gate | pass |

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

#### Probe Results

| Probe | Result | Notes |
|---|---|---|
| Token reporting probe | pass | `turn.completed` event with `usage` block extracted successfully on live run |
| No-tool step probe | pass | Exit status 0; all artifacts written |
| Forced single-tool step probe | pass | PATH restriction respected; required tool appeared in trace |
| Blocked-tool failure probe | pass | Blocked tool invocation detected; run marked invalid |
| Completion and artifact probe | pass | All expected artifacts present; validation executed |

#### Live Run Token Evidence

Codex produced substantially higher raw token counts than Claude on the same ripgrep tasks,
confirming that token reporting is functioning:

- ripgrep-01 baseline: 276,568 tokens
- ripgrep-01 tool_variant: 38,213 tokens
- ripgrep-02 baseline: 82,758 tokens
- ripgrep-02 tool_variant: 48,040 tokens

#### Evidence Paths

```
benchmarks/qualification/codex/token-reporting-probe/
benchmarks/qualification/codex/no-tool-step-probe/
benchmarks/qualification/codex/forced-tool-step-probe/
benchmarks/qualification/codex/blocked-tool-probe/
benchmarks/qualification/codex/completion-artifact-probe/
```

---

### gemini-cli (adapter 0.1.0, qualified 2026-04-01)

The `GeminiCliAdapter` wraps the Gemini CLI binary (`gemini`). The adapter is complete,
passes all unit tests, and has completed a live qualification run against real Cassandra
tasks. All four gates passed.

#### Gate Summary

| Gate | Result |
|---|---|
| Reported-token gate | pass |
| Forced-tool gate | pass |
| Audit-trace gate | pass |
| Run-completeness gate | pass |

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

#### Probe Results

| Probe | Result | Notes |
|---|---|---|
| Token reporting probe | pass | `stats` block with token counts extracted successfully on live run |
| No-tool step probe | pass | Exit status 0; all artifacts written |
| Forced single-tool step probe | pass | PATH restriction respected; required tool appeared in trace |
| Blocked-tool failure probe | pass | Blocked tool invocation detected; run marked invalid |
| Completion and artifact probe | pass | All expected artifacts present; validation executed |

#### Live Run Token Evidence

Gemini CLI token counts from live ripgrep runs (note the known extraction bug on ripgrep-01 baseline):

- ripgrep-01 baseline: 0 (extraction bug — issue #46; real token count not captured)
- ripgrep-01 tool_variant: 1,542,880 tokens
- ripgrep-02 baseline: 59,702 tokens
- ripgrep-02 tool_variant: 68,144 tokens

#### Known Issue: Token Extraction Bug #46

The Gemini CLI ripgrep-01 baseline run returned a token count of 0. This is not a normal
zero-token run; it reflects a defect in the extraction pipeline where the terminal result
line was not captured for that specific run. The qualification probes passed because the
probe tasks are shorter and more predictable than full benchmark tasks. Issue #46 tracks
the root cause and fix. Until resolved, any Gemini CLI run where the extraction returns 0
should be treated as invalid and excluded from comparison tables.

This bug does not revoke qualification. It is a known operational defect that affects data
quality on specific runs, not a failure of the adapter's fundamental token-reporting capability.

#### Evidence Paths

```
benchmarks/qualification/gemini-cli/token-reporting-probe/
benchmarks/qualification/gemini-cli/no-tool-step-probe/
benchmarks/qualification/gemini-cli/forced-tool-step-probe/
benchmarks/qualification/gemini-cli/blocked-tool-probe/
benchmarks/qualification/gemini-cli/completion-artifact-probe/
```

---

## Guidance for Qualification

Any agent adapter that wants to appear in official benchmark scorecards must pass all four
qualification gates on a live run. The steps below apply to any future adapters.

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

Once an agent qualifies, add it to the "Qualified Agents" section. Update the gate summary
table, fill in the actual probe results with real token counts and invocation evidence, and
record the qualification date.

---

## Implementation Note

All three adapters (`ClaudeAdapter`, `CodexAdapter`, `GeminiCliAdapter`) are fully
implemented in `agents/claude/adapter.py`, `agents/codex/adapter.py`, and
`agents/gemini_cli/adapter.py` respectively. Each adapter implements the full
`AgentAdapter` interface: `probe()`, `run_step()`, `extract_reported_tokens()`, and
`normalize_final_status()`. Each has a corresponding parser module that handles token
extraction from the CLI's native output format.

All three adapters have now completed live qualification runs against real Cassandra tasks,
confirming that token extraction and tool-enforcement mechanisms work correctly in practice.
The Gemini CLI token extraction bug (issue #46) was discovered during live benchmark runs
after qualification — it affects specific run configurations, not the qualification probes
themselves.
