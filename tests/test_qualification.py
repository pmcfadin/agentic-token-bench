"""Tests for benchmarks.harness.qualification."""

from pathlib import Path

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from benchmarks.harness.models import QualificationRecord
from benchmarks.harness.qualification import (
    probe_blocked_tool,
    probe_completion,
    probe_forced_tool,
    probe_no_tool_step,
    probe_token_reporting,
    run_qualification,
)


# ---------------------------------------------------------------------------
# Mock adapters
# ---------------------------------------------------------------------------


class _PassingAdapter(AgentAdapter):
    """Mock adapter that passes all probes."""

    def probe(self) -> QualificationResult:
        return QualificationResult(
            qualified=True,
            reported_token_support=True,
            forced_tool_support=True,
            trace_support=True,
            run_completion_support=True,
        )

    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        blocked_tools_raw = step_env.get("BLOCKED_TOOLS", "")
        blocked = [t.strip() for t in blocked_tools_raw.split(",") if t.strip()]

        # If a blocked tool is mentioned in the prompt, fail with non-zero exit status.
        for tool in blocked:
            if tool in prompt:
                return StepResult(
                    stdout="",
                    stderr=f"Blocked tool {tool!r} is not allowed in this step.",
                    exit_status=1,
                    step_metadata={"blocked_tool_violation": True},
                    trace_metadata={},
                )

        required_tool = step_env.get("REQUIRED_TOOL")
        tool_invocations: list[dict] = []
        if required_tool:
            tool_invocations = [{"tool": required_tool, "exit_code": 0}]

        return StepResult(
            stdout="ok",
            stderr="",
            exit_status=0,
            step_metadata={"tool_invocations": tool_invocations},
            trace_metadata={"trace_available": True},
        )

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        reported = step_result.step_metadata.get("reported_tokens", {})
        return ReportedTokens(
            input_tokens=reported.get("input", 10),
            output_tokens=reported.get("output", 5),
            total_tokens=reported.get("total", 15),
            evidence_snippet="Tokens used: input=10, output=5, total=15",
        )

    def normalize_final_status(self, step_result: StepResult) -> str:
        return "completed" if step_result.exit_status == 0 else "failed"


class _FailingTokenAdapter(_PassingAdapter):
    """Mock adapter whose extract_reported_tokens always raises."""

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        raise ValueError("Token extraction is not supported by this adapter")


class _EmptyEvidenceTokenAdapter(_PassingAdapter):
    """Mock adapter that returns tokens but with an empty evidence_snippet."""

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        return ReportedTokens(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            evidence_snippet="",  # empty — should fail the probe
        )


class _NegativeTokenAdapter(_PassingAdapter):
    """Mock adapter that returns negative token counts."""

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        return ReportedTokens(
            input_tokens=-1,
            output_tokens=5,
            total_tokens=15,
            evidence_snippet="some evidence",
        )


class _NoToolInvocationAdapter(_PassingAdapter):
    """Mock adapter that never records tool_invocations in step_metadata."""

    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        # Always returns success but never includes tool_invocations.
        return StepResult(
            stdout="ok",
            stderr="",
            exit_status=0,
            step_metadata={},
            trace_metadata={},
        )


class _BlockedToolPermissiveAdapter(_PassingAdapter):
    """Mock adapter that ignores blocked tools and always exits 0."""

    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        return StepResult(
            stdout="ok",
            stderr="",
            exit_status=0,
            step_metadata={},
            trace_metadata={},
        )


class _EmptyStatusAdapter(_PassingAdapter):
    """Mock adapter whose normalize_final_status returns an empty string."""

    def normalize_final_status(self, step_result: StepResult) -> str:
        return ""


class _RunStepRaisesAdapter(_PassingAdapter):
    """Mock adapter whose run_step always raises."""

    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        raise RuntimeError("Agent CLI unavailable")


# ---------------------------------------------------------------------------
# probe_token_reporting tests
# ---------------------------------------------------------------------------


class TestProbeTokenReporting:
    def test_passing_adapter_returns_true(self) -> None:
        passed, message = probe_token_reporting(_PassingAdapter())
        assert passed is True
        assert message  # non-empty

    def test_raising_adapter_returns_false(self) -> None:
        passed, message = probe_token_reporting(_FailingTokenAdapter())
        assert passed is False
        assert "exception" in message.lower()

    def test_empty_evidence_returns_false(self) -> None:
        passed, message = probe_token_reporting(_EmptyEvidenceTokenAdapter())
        assert passed is False
        assert "evidence_snippet" in message

    def test_negative_input_tokens_returns_false(self) -> None:
        passed, message = probe_token_reporting(_NegativeTokenAdapter())
        assert passed is False
        assert "negative" in message.lower()

    def test_message_contains_token_counts_on_success(self) -> None:
        passed, message = probe_token_reporting(_PassingAdapter())
        assert passed is True
        assert "input=" in message
        assert "output=" in message
        assert "total=" in message


# ---------------------------------------------------------------------------
# probe_no_tool_step tests
# ---------------------------------------------------------------------------


class TestProbeNoToolStep:
    def test_passing_adapter_returns_true(self) -> None:
        passed, message = probe_no_tool_step(_PassingAdapter())
        assert passed is True

    def test_run_step_raises_returns_false(self) -> None:
        passed, message = probe_no_tool_step(_RunStepRaisesAdapter())
        assert passed is False
        assert "exception" in message.lower()

    def test_message_is_non_empty(self) -> None:
        _, message = probe_no_tool_step(_PassingAdapter())
        assert message


# ---------------------------------------------------------------------------
# probe_forced_tool tests
# ---------------------------------------------------------------------------


class TestProbeForcedTool:
    def test_passing_adapter_returns_true(self) -> None:
        passed, message = probe_forced_tool(_PassingAdapter())
        assert passed is True

    def test_no_tool_invocations_returns_false(self) -> None:
        passed, message = probe_forced_tool(_NoToolInvocationAdapter())
        assert passed is False
        assert "tool_invocations" in message

    def test_run_step_raises_returns_false(self) -> None:
        passed, message = probe_forced_tool(_RunStepRaisesAdapter())
        assert passed is False
        assert "exception" in message.lower()

    def test_message_contains_invocation_count(self) -> None:
        passed, message = probe_forced_tool(_PassingAdapter())
        assert passed is True
        assert "1" in message  # at least "1 tool invocation"


# ---------------------------------------------------------------------------
# probe_blocked_tool tests
# ---------------------------------------------------------------------------


class TestProbeBlockedTool:
    def test_passing_adapter_returns_true(self) -> None:
        passed, message = probe_blocked_tool(_PassingAdapter())
        assert passed is True

    def test_permissive_adapter_returns_false(self) -> None:
        passed, message = probe_blocked_tool(_BlockedToolPermissiveAdapter())
        assert passed is False
        assert "blocked" in message.lower()

    def test_raising_adapter_returns_true(self) -> None:
        # An exception is an acceptable enforcement signal.
        passed, _ = probe_blocked_tool(_RunStepRaisesAdapter())
        assert passed is True


# ---------------------------------------------------------------------------
# probe_completion tests
# ---------------------------------------------------------------------------


class TestProbeCompletion:
    def test_passing_adapter_returns_true(self) -> None:
        passed, message = probe_completion(_PassingAdapter())
        assert passed is True

    def test_empty_status_returns_false(self) -> None:
        passed, message = probe_completion(_EmptyStatusAdapter())
        assert passed is False
        assert "empty" in message.lower()

    def test_run_step_raises_returns_false(self) -> None:
        passed, message = probe_completion(_RunStepRaisesAdapter())
        assert passed is False
        assert "exception" in message.lower()

    def test_message_contains_final_status(self) -> None:
        passed, message = probe_completion(_PassingAdapter())
        assert passed is True
        assert "final_status=" in message


# ---------------------------------------------------------------------------
# run_qualification tests
# ---------------------------------------------------------------------------


class TestRunQualification:
    def test_all_passing_adapter_is_qualified(self) -> None:
        record = run_qualification(_PassingAdapter(), agent_id="test-agent", adapter_version="1.0")

        assert isinstance(record, QualificationRecord)
        assert record.qualified is True
        assert record.agent_id == "test-agent"
        assert record.adapter_version == "1.0"

    def test_all_passing_adapter_has_no_failure_reason(self) -> None:
        record = run_qualification(_PassingAdapter(), agent_id="test-agent", adapter_version="1.0")
        assert record.failure_reason is None

    def test_all_passing_adapter_has_all_supports_true(self) -> None:
        record = run_qualification(_PassingAdapter(), agent_id="test-agent", adapter_version="1.0")
        assert record.reported_token_support is True
        assert record.forced_tool_support is True
        assert record.trace_support is True
        assert record.run_completion_support is True

    def test_failing_token_adapter_is_not_qualified(self) -> None:
        record = run_qualification(
            _FailingTokenAdapter(), agent_id="bad-agent", adapter_version="0.1"
        )
        assert record.qualified is False

    def test_failing_token_adapter_has_failure_reason(self) -> None:
        record = run_qualification(
            _FailingTokenAdapter(), agent_id="bad-agent", adapter_version="0.1"
        )
        assert record.failure_reason is not None
        assert "probe_token_reporting" in record.failure_reason

    def test_failing_token_adapter_reported_token_support_is_false(self) -> None:
        record = run_qualification(
            _FailingTokenAdapter(), agent_id="bad-agent", adapter_version="0.1"
        )
        assert record.reported_token_support is False

    def test_failure_reason_names_first_failing_probe(self) -> None:
        """The failure_reason must reference the name of the first failing probe."""
        record = run_qualification(
            _FailingTokenAdapter(), agent_id="bad-agent", adapter_version="0.1"
        )
        # probe_token_reporting is the first probe in the ordered list.
        assert "probe_token_reporting" in (record.failure_reason or "")

    def test_record_includes_agent_id_and_version(self) -> None:
        record = run_qualification(
            _PassingAdapter(), agent_id="claude", adapter_version="2.3.0"
        )
        assert record.agent_id == "claude"
        assert record.adapter_version == "2.3.0"

    def test_evidence_paths_is_list(self) -> None:
        record = run_qualification(_PassingAdapter(), agent_id="x", adapter_version="1")
        assert isinstance(record.evidence_paths, list)

    def test_permissive_blocked_tool_adapter_is_not_qualified(self) -> None:
        """An adapter that ignores blocked tools should not qualify."""
        record = run_qualification(
            _BlockedToolPermissiveAdapter(), agent_id="bad-agent", adapter_version="0.1"
        )
        assert record.qualified is False

    def test_run_step_raises_adapter_is_not_qualified(self) -> None:
        record = run_qualification(
            _RunStepRaisesAdapter(), agent_id="crash-agent", adapter_version="0.0"
        )
        # run_step raises, so no-tool probe and forced-tool probe fail; blocked probe passes.
        assert record.qualified is False
