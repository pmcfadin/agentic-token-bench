# Release Gates

These gates control when work expands from one phase to the next. Do not broaden scope until the gate for the current phase passes. Each gate has a checklist, verification commands where applicable, and the phase milestone it protects.

Source of truth for the gate definitions: `docs/plans/2026-03-31-v1-build-plan-design.md`, section "Minimum Acceptance Gates".

---

## Gate 0: Contract Gate

**Phase milestone:** Exit Phase 0 (Contract Lock)

Phase 0 turns benchmark rules into executable contracts. This gate confirms that the contracts are real and testable before any pod builds production logic against them.

### Criteria checklist

- [ ] All four JSON schemas validate against their own meta-schema
  - `schemas/task.schema.json`
  - `schemas/run.schema.json`
  - `schemas/event.schema.json`
  - `schemas/qualification.schema.json`
- [ ] At least one sample task manifest exists under `benchmarks/tasks/cassandra/official/` and is valid against `schemas/task.schema.json`
- [ ] At least one sample run record exists and is valid against `schemas/run.schema.json`
- [ ] At least one sample qualification record exists and is valid against `schemas/qualification.schema.json`
- [ ] One smoke qualification run completes without error (the harness can probe an agent adapter and write a qualification record)

### Verification commands

```bash
# Lint and schema validation
uv run ruff check .
uv run pytest tests/schemas/ -v

# Validate schemas (once validate-schemas is implemented)
uv run atb validate-schemas

# Smoke qualification run (once qualify-agent is implemented)
uv run atb qualify-agent <agent-id>
```

The smoke qualification run does not require a qualified result. It requires only that the harness runs without crashing and writes a qualification record to `benchmarks/qualification/`.

---

## Gate 1: Pilot Gate

**Phase milestone:** Exit Phase 1 (Qualification and Pilot Family)

Phase 1 proves the first official family end to end. This gate confirms that the measurement machinery works before all six families are built out.

### Criteria checklist

- [ ] At least one agent (`codex`, `claude`, or `gemini-cli`) has a `qualified: true` qualification record in `benchmarks/qualification/`
- [ ] That agent's qualification record shows `reported_token_support: true` and `forced_tool_support: true`
- [ ] One complete tool family (recommended: `ripgrep` or `fastmod`) has both tasks defined under `benchmarks/tasks/cassandra/official/`
- [ ] Both tasks in the pilot family run to completion under the `baseline` variant and produce a valid run record
- [ ] Both tasks in the pilot family run to completion under the `tool_variant` variant and produce a valid run record
- [ ] Every valid run record includes non-null `reported_input_tokens`, `reported_output_tokens`, and `reported_total_tokens`
- [ ] Automated validation executed for every completed run (no manually judged runs count here)
- [ ] A draft scorecard for the pilot family can be generated without manual intervention

### Verification commands

```bash
# Check qualification record exists and shows qualified
ls benchmarks/qualification/

# Run pilot family baseline and variant (once run-family is implemented)
uv run atb run-family ripgrep --agent <agent-id>

# Generate scorecard draft (once generate-scorecard is implemented)
uv run atb generate-scorecard

# Run tests covering pilot family artifacts
uv run pytest tests/official_runs/ -v
```

Token capture is automated if the run records are written without manual editing and each contains a populated `token_evidence.txt` artifact.

---

## Gate 2: Coverage Gate

**Phase milestone:** Exit Phase 2 (Full Official Coverage)

Phase 2 completes the v1 official scorecard for one qualified agent. This gate confirms that the full matrix is runnable and stable before the release pack is assembled.

### Criteria checklist

- [ ] All six tool families are present with task manifests:
  - [ ] `ripgrep` — 2 tasks
  - [ ] `qmd` — 2 tasks
  - [ ] `rtk` — 2 tasks
  - [ ] `fastmod` — 2 tasks
  - [ ] `ast-grep` — 2 tasks
  - [ ] `comby` — 2 tasks
- [ ] All twelve official tasks are runnable end to end (no harness errors on a clean run)
- [ ] All six tool wrappers are implemented under `tools/` and produce invocation traces
- [ ] Repeated runs of the same task produce run records with the same artifact structure (same set of files in the run directory, same schema validity)
- [ ] No repeated run produces a different `validity` classification for the same task and variant under the same conditions
- [ ] Official scorecards show tokens, correctness, and elapsed time side by side for all six families

### Verification commands

```bash
# Run full suite for the qualified agent (once run-suite is implemented)
uv run atb run-suite --agent <agent-id>

# Confirm twelve tasks are present
ls benchmarks/tasks/cassandra/official/

# Confirm all six tool wrappers exist and pass wrapper tests
uv run pytest tests/ -k "tool" -v

# Generate full scorecard
uv run atb generate-scorecard

# Re-run one family three times and diff the artifact shapes
for i in 1 2 3; do uv run atb run-family ripgrep --agent <agent-id>; done
```

Stable artifact shapes means the set of files written to each `benchmarks/results/<run-id>/` directory is the same across repeated runs. Token values and elapsed times may vary; the structure must not.

---

## Gate 3: Release Gate

**Phase milestone:** Exit Phase 3 (Appendix and Release Pack) — clears v1 for public release

Phase 3 turns the internal benchmark into a release-quality artifact. This gate confirms that the results are reproducible, the exclusion logic is correct, and a third party can understand and rerun the suite.

### Criteria checklist

- [ ] Scorecards are reproducible: running the suite again on the same pinned Cassandra commit produces scorecards that match the published results within expected token variance
- [ ] Invalid runs are excluded correctly: the harness classifies and excludes runs where reported tokens are missing, required tools were not used, a blocked tool was used, the trace is incomplete, or validation did not execute
- [ ] No invalid run appears in any official scorecard or summary table
- [ ] A qualification appendix exists at `benchmarks/qualification/` documenting each agent's status: `qualified` or `not_qualified` with a failure reason
- [ ] Non-qualified agents are listed separately and not included in official scorecard comparisons
- [ ] `docs/spec.md` or a dedicated reproduction guide documents all steps a third party must follow to rerun the suite
- [ ] Reproduction steps have been verified: at least one complete suite run was performed by following the documented steps on a clean environment
- [ ] Mixed-tool appendix workflows are labeled clearly and do not appear in the official scorecard section
- [ ] `docs/findings.md` exists and its claims match what the scorecards actually show

### Verification commands

```bash
# Reproduce official results from scratch
uv run atb run-suite --agent <agent-id>
uv run atb generate-scorecard

# Confirm invalid runs are not in the scorecard
# (inspect the generated scorecard; validity=invalid runs must be absent)

# Check qualification appendix is populated
ls benchmarks/qualification/
cat benchmarks/qualification/<agent-id>-qualification.json

# Lint and tests must be clean before tagging release
uv run ruff check .
uv run pytest -v
```

The release is blocked if any of the following are true:

- A run with `validity: invalid` appears in an official scorecard
- The qualification appendix is missing or empty
- The reproduction steps have not been verified on a clean environment
- Estimated token counts are mixed into official result tables

---

## Gate summary

| Gate | Phase exited | One-line condition |
|------|--------------|--------------------|
| Gate 0 | Phase 0: Contract Lock | Schemas validate, sample manifests exist, smoke qualification run works |
| Gate 1 | Phase 1: Qualification and Pilot Family | One agent qualifies, one family completes baseline and variant, tokens captured automatically, validation automated |
| Gate 2 | Phase 2: Full Official Coverage | All six families present, all twelve tasks runnable, repeated runs produce stable artifact shapes |
| Gate 3 | Phase 3: Appendix and Release Pack | Scorecards reproducible, invalid runs excluded, qualification appendix exists, reproduction steps documented |
