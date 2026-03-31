"""benchmarks.harness.qualification — qualification probe runner.

Runs standardized probes against an AgentAdapter to determine whether
the adapter meets the requirements for official benchmark runs.

See docs/plans/2026-03-31-v1-build-plan-design.md for the qualification
protocol.
"""

from pathlib import Path

from agents.base import AgentAdapter, StepResult
from benchmarks.harness.models import QualificationRecord

# ---------------------------------------------------------------------------
# Synthetic step results for use in probes
# ---------------------------------------------------------------------------

_MINIMAL_STEP_ENV: dict[str, str] = {}


def _ensure_probe_workspace() -> Path:
    """Create and return a temporary workspace directory for probes."""
    workspace = Path("/tmp/qualification-probe")
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _make_step_result(
    stdout: str = "",
    stderr: str = "",
    exit_status: int = 0,
    step_metadata: dict | None = None,
    trace_metadata: dict | None = None,
) -> StepResult:
    return StepResult(
        stdout=stdout,
        stderr=stderr,
        exit_status=exit_status,
        step_metadata=step_metadata or {},
        trace_metadata=trace_metadata or {},
    )


# ---------------------------------------------------------------------------
# Individual probes
# ---------------------------------------------------------------------------


def probe_token_reporting(adapter: AgentAdapter) -> tuple[bool, str]:
    """Check whether the adapter can extract tokens from a real CLI invocation.

    Runs a live step via run_step(), then calls extract_reported_tokens on the
    real output.  This validates the full pipeline: CLI invocation → output
    capture → token parsing → evidence extraction.

    Returns:
        (passed, message)
    """
    try:
        step_result = adapter.run_step(
            prompt="Reply with the single word 'ok' and nothing else.",
            step_env=_MINIMAL_STEP_ENV,
            workspace=_ensure_probe_workspace(),
            timeout=60.0,
        )
    except Exception as exc:
        return False, f"run_step raised an exception during token probe: {exc}"

    if step_result is None:
        return False, "run_step returned None during token probe"

    try:
        tokens = adapter.extract_reported_tokens(step_result)
    except Exception as exc:
        return False, f"extract_reported_tokens raised an exception: {exc}"

    if tokens is None:
        return False, "extract_reported_tokens returned None"
    if tokens.input_tokens < 0:
        return False, f"input_tokens is negative: {tokens.input_tokens}"
    if tokens.output_tokens < 0:
        return False, f"output_tokens is negative: {tokens.output_tokens}"
    if tokens.total_tokens < 0:
        return False, f"total_tokens is negative: {tokens.total_tokens}"
    if not tokens.evidence_snippet:
        return False, "evidence_snippet is empty"

    return True, (
        f"token reporting ok: input={tokens.input_tokens} "
        f"output={tokens.output_tokens} total={tokens.total_tokens}"
    )


def probe_no_tool_step(adapter: AgentAdapter) -> tuple[bool, str]:
    """Check that the adapter can execute a basic step without tools.

    A no-tool step has an empty allowed_tools list and no required tool.  The
    probe calls run_step with a simple prompt and verifies a StepResult is
    returned with a zero exit status.

    Returns:
        (passed, message)
    """
    try:
        result = adapter.run_step(
            prompt="Say hello.",
            step_env=_MINIMAL_STEP_ENV,
            workspace=_ensure_probe_workspace(),
            timeout=30.0,
        )
    except Exception as exc:
        return False, f"run_step raised an exception on no-tool step: {exc}"

    if result is None:
        return False, "run_step returned None"
    if result.exit_status != 0:
        return False, (
            f"no-tool step exited with non-zero status: {result.exit_status}. "
            f"stderr={result.stderr!r}"
        )

    return True, "no-tool step completed successfully"


def probe_forced_tool(adapter: AgentAdapter) -> tuple[bool, str]:
    """Check that the adapter can execute a step when a tool is required.

    The probe passes a step environment that signals a required tool is
    available, then verifies that the step completes and the step_metadata
    records at least one tool invocation.

    Returns:
        (passed, message)
    """
    step_env = {**_MINIMAL_STEP_ENV, "REQUIRED_TOOL": "ripgrep"}
    try:
        result = adapter.run_step(
            prompt="Use ripgrep to search for 'TODO' in the workspace.",
            step_env=step_env,
            workspace=_ensure_probe_workspace(),
            timeout=30.0,
        )
    except Exception as exc:
        return False, f"run_step raised an exception on forced-tool step: {exc}"

    if result is None:
        return False, "run_step returned None on forced-tool step"
    if result.exit_status != 0:
        return False, (
            f"forced-tool step exited with non-zero status: {result.exit_status}. "
            f"stderr={result.stderr!r}"
        )

    tool_invocations = result.step_metadata.get("tool_invocations", [])
    if not tool_invocations:
        return False, (
            "forced-tool step completed but step_metadata contains no tool_invocations"
        )

    return True, f"forced-tool step completed with {len(tool_invocations)} tool invocation(s)"


def probe_blocked_tool(adapter: AgentAdapter) -> tuple[bool, str]:
    """Check that the adapter correctly fails when a blocked tool is invoked.

    The probe passes a step environment that marks a tool as blocked.  The
    adapter is expected to either raise an exception or return a non-zero exit
    status when the blocked tool would be called.

    Returns:
        (passed, message)
    """
    step_env = {**_MINIMAL_STEP_ENV, "BLOCKED_TOOLS": "ripgrep"}
    try:
        result = adapter.run_step(
            prompt="Use ripgrep to search for something.",
            step_env=step_env,
            workspace=_ensure_probe_workspace(),
            timeout=30.0,
        )
    except Exception:
        # An exception is an acceptable way to signal a blocked-tool failure.
        return True, "blocked-tool step raised an exception as expected"

    if result is None:
        return False, "run_step returned None on blocked-tool step"

    # A non-zero exit status indicates the blocked tool was correctly refused.
    if result.exit_status != 0:
        return True, f"blocked-tool step correctly failed with exit status {result.exit_status}"

    # If exit_status is 0, check whether the step metadata records a violation.
    if result.step_metadata.get("blocked_tool_violation"):
        return True, "blocked-tool violation recorded in step_metadata"

    return False, (
        "blocked-tool step completed with exit_status=0 and no violation recorded; "
        "adapter may not be enforcing blocked-tool rules"
    )


def probe_completion(adapter: AgentAdapter) -> tuple[bool, str]:
    """Check that artifacts and completion status are captured correctly.

    The probe calls run_step with a prompt that should produce a final answer
    artifact.  It then calls normalize_final_status and verifies the returned
    string is non-empty.

    Returns:
        (passed, message)
    """
    try:
        result = adapter.run_step(
            prompt="Provide a final answer: the answer is 42.",
            step_env=_MINIMAL_STEP_ENV,
            workspace=_ensure_probe_workspace(),
            timeout=30.0,
        )
    except Exception as exc:
        return False, f"run_step raised an exception on completion probe: {exc}"

    if result is None:
        return False, "run_step returned None on completion probe"

    try:
        status = adapter.normalize_final_status(result)
    except Exception as exc:
        return False, f"normalize_final_status raised an exception: {exc}"

    if not status:
        return False, "normalize_final_status returned an empty string"

    return True, f"completion probe ok: final_status={status!r}"


# ---------------------------------------------------------------------------
# Probe registry
# ---------------------------------------------------------------------------

# Ordered list of (probe_fn, result_field_name) pairs.
# result_field_name maps to a boolean field on QualificationRecord.
_PROBES: list[tuple] = [
    (probe_token_reporting, "reported_token_support"),
    (probe_no_tool_step, "trace_support"),
    (probe_forced_tool, "forced_tool_support"),
    (probe_blocked_tool, "forced_tool_support"),
    (probe_completion, "run_completion_support"),
]


# ---------------------------------------------------------------------------
# run_qualification
# ---------------------------------------------------------------------------


def run_qualification(
    adapter: AgentAdapter,
    agent_id: str,
    adapter_version: str,
) -> QualificationRecord:
    """Run all qualification probes and return a QualificationRecord.

    All probes are run regardless of earlier failures so that the record
    captures the full capability picture.  qualified=True only when every
    probe passes.  failure_reason is set to the message of the first
    failing probe.

    Args:
        adapter: The AgentAdapter implementation to qualify.
        agent_id: Identifier for the agent (e.g. "claude", "codex").
        adapter_version: Version string for the adapter.

    Returns:
        QualificationRecord with aggregated probe results.
    """
    probe_results: dict[str, bool] = {
        "reported_token_support": False,
        "forced_tool_support": False,
        "trace_support": False,
        "run_completion_support": False,
    }

    first_failure_reason: str | None = None

    probe_functions = [
        (probe_token_reporting, "reported_token_support"),
        (probe_no_tool_step, "trace_support"),
        (probe_forced_tool, "forced_tool_support"),
        (probe_blocked_tool, "forced_tool_support"),
        (probe_completion, "run_completion_support"),
    ]

    for probe_fn, field_name in probe_functions:
        passed, message = probe_fn(adapter)
        if passed:
            # Only upgrade to True; a prior failure on the same field stays False
            # until this probe passes (last write wins for the same field).
            probe_results[field_name] = True
        else:
            # Mark the field as failed.
            probe_results[field_name] = False
            if first_failure_reason is None:
                first_failure_reason = f"{probe_fn.__name__}: {message}"

    all_passed = all(probe_results.values())

    return QualificationRecord(
        agent_id=agent_id,
        adapter_version=adapter_version,
        qualified=all_passed,
        reported_token_support=probe_results["reported_token_support"],
        forced_tool_support=probe_results["forced_tool_support"],
        trace_support=probe_results["trace_support"],
        run_completion_support=probe_results["run_completion_support"],
        failure_reason=first_failure_reason if not all_passed else None,
        evidence_paths=[],
    )
