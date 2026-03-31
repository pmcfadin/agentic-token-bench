"""Tests for agents/base.py: AgentAdapter ABC and supporting dataclasses."""

from pathlib import Path

import pytest

from agents.base import (
    AgentAdapter,
    QualificationResult,
    ReportedTokens,
    StepResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FullAdapter(AgentAdapter):
    """Minimal concrete adapter that implements all abstract methods."""

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
        return StepResult(
            stdout="ok",
            stderr="",
            exit_status=0,
            step_metadata={"prompt_len": len(prompt)},
            trace_metadata={},
        )

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        return ReportedTokens(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            evidence_snippet="Tokens used: 150",
        )

    def normalize_final_status(self, step_result: StepResult) -> str:
        return "completed" if step_result.exit_status == 0 else "failed"


# ---------------------------------------------------------------------------
# Abstractness tests
# ---------------------------------------------------------------------------


def test_agent_adapter_cannot_be_instantiated_directly() -> None:
    """AgentAdapter is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        AgentAdapter()  # type: ignore[abstract]


def test_subclass_missing_probe_raises_type_error() -> None:
    """A subclass that omits probe() cannot be instantiated."""

    class _MissingProbe(AgentAdapter):
        def run_step(self, prompt, step_env, workspace, timeout):
            ...

        def extract_reported_tokens(self, step_result):
            ...

        def normalize_final_status(self, step_result):
            ...

    with pytest.raises(TypeError):
        _MissingProbe()  # type: ignore[abstract]


def test_subclass_missing_run_step_raises_type_error() -> None:
    """A subclass that omits run_step() cannot be instantiated."""

    class _MissingRunStep(AgentAdapter):
        def probe(self):
            ...

        def extract_reported_tokens(self, step_result):
            ...

        def normalize_final_status(self, step_result):
            ...

    with pytest.raises(TypeError):
        _MissingRunStep()  # type: ignore[abstract]


def test_subclass_missing_extract_reported_tokens_raises_type_error() -> None:
    """A subclass that omits extract_reported_tokens() cannot be instantiated."""

    class _MissingExtract(AgentAdapter):
        def probe(self):
            ...

        def run_step(self, prompt, step_env, workspace, timeout):
            ...

        def normalize_final_status(self, step_result):
            ...

    with pytest.raises(TypeError):
        _MissingExtract()  # type: ignore[abstract]


def test_subclass_missing_normalize_final_status_raises_type_error() -> None:
    """A subclass that omits normalize_final_status() cannot be instantiated."""

    class _MissingNormalize(AgentAdapter):
        def probe(self):
            ...

        def run_step(self, prompt, step_env, workspace, timeout):
            ...

        def extract_reported_tokens(self, step_result):
            ...

    with pytest.raises(TypeError):
        _MissingNormalize()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Concrete mock adapter – instantiation and method calls
# ---------------------------------------------------------------------------


def test_full_adapter_can_be_instantiated() -> None:
    """A concrete adapter implementing all methods can be instantiated."""
    adapter = _FullAdapter()
    assert isinstance(adapter, AgentAdapter)


def test_probe_returns_qualification_result() -> None:
    """probe() returns a QualificationResult."""
    adapter = _FullAdapter()
    result = adapter.probe()
    assert isinstance(result, QualificationResult)


def test_probe_qualified_flag() -> None:
    """The mock adapter's probe() returns qualified=True."""
    adapter = _FullAdapter()
    result = adapter.probe()
    assert result.qualified is True


def test_run_step_returns_step_result() -> None:
    """run_step() returns a StepResult."""
    adapter = _FullAdapter()
    result = adapter.run_step(
        prompt="do something",
        step_env={"PATH": "/usr/bin"},
        workspace=Path("/tmp/workspace"),
        timeout=30.0,
    )
    assert isinstance(result, StepResult)


def test_run_step_passes_prompt_to_metadata() -> None:
    """run_step() captures prompt length in step_metadata."""
    adapter = _FullAdapter()
    prompt = "find the config"
    result = adapter.run_step(
        prompt=prompt,
        step_env={},
        workspace=Path("/tmp/ws"),
        timeout=60.0,
    )
    assert result.step_metadata["prompt_len"] == len(prompt)


def test_extract_reported_tokens_returns_reported_tokens() -> None:
    """extract_reported_tokens() returns a ReportedTokens instance."""
    adapter = _FullAdapter()
    step_result = StepResult(
        stdout="Tokens used: 150",
        stderr="",
        exit_status=0,
        step_metadata={},
        trace_metadata={},
    )
    tokens = adapter.extract_reported_tokens(step_result)
    assert isinstance(tokens, ReportedTokens)


def test_extract_reported_tokens_values() -> None:
    """extract_reported_tokens() returns the expected token counts."""
    adapter = _FullAdapter()
    step_result = StepResult(
        stdout="", stderr="", exit_status=0, step_metadata={}, trace_metadata={}
    )
    tokens = adapter.extract_reported_tokens(step_result)
    assert tokens.input_tokens == 100
    assert tokens.output_tokens == 50
    assert tokens.total_tokens == 150
    assert tokens.evidence_snippet == "Tokens used: 150"


def test_normalize_final_status_success() -> None:
    """normalize_final_status() returns 'completed' for exit_status 0."""
    adapter = _FullAdapter()
    step_result = StepResult(
        stdout="", stderr="", exit_status=0, step_metadata={}, trace_metadata={}
    )
    assert adapter.normalize_final_status(step_result) == "completed"


def test_normalize_final_status_failure() -> None:
    """normalize_final_status() returns 'failed' for non-zero exit_status."""
    adapter = _FullAdapter()
    step_result = StepResult(
        stdout="", stderr="error", exit_status=1, step_metadata={}, trace_metadata={}
    )
    assert adapter.normalize_final_status(step_result) == "failed"


# ---------------------------------------------------------------------------
# StepResult dataclass construction
# ---------------------------------------------------------------------------


def test_step_result_construction_minimal() -> None:
    """StepResult can be constructed with all required fields."""
    sr = StepResult(
        stdout="output",
        stderr="",
        exit_status=0,
        step_metadata={},
        trace_metadata={},
    )
    assert sr.stdout == "output"
    assert sr.stderr == ""
    assert sr.exit_status == 0
    assert sr.step_metadata == {}
    assert sr.trace_metadata == {}


def test_step_result_construction_with_metadata() -> None:
    """StepResult stores non-empty metadata dicts faithfully."""
    sr = StepResult(
        stdout="hello",
        stderr="warn",
        exit_status=2,
        step_metadata={"finish_reason": "stop"},
        trace_metadata={"tool_calls": 3},
    )
    assert sr.step_metadata["finish_reason"] == "stop"
    assert sr.trace_metadata["tool_calls"] == 3


# ---------------------------------------------------------------------------
# ReportedTokens dataclass construction
# ---------------------------------------------------------------------------


def test_reported_tokens_construction() -> None:
    """ReportedTokens stores all four required fields."""
    rt = ReportedTokens(
        input_tokens=200,
        output_tokens=80,
        total_tokens=280,
        evidence_snippet="input: 200 output: 80 total: 280",
    )
    assert rt.input_tokens == 200
    assert rt.output_tokens == 80
    assert rt.total_tokens == 280
    assert "280" in rt.evidence_snippet


def test_reported_tokens_zero_values_allowed() -> None:
    """ReportedTokens accepts zero counts (edge case for empty runs)."""
    rt = ReportedTokens(
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        evidence_snippet="",
    )
    assert rt.total_tokens == 0


# ---------------------------------------------------------------------------
# QualificationResult dataclass construction
# ---------------------------------------------------------------------------


def test_qualification_result_fully_qualified() -> None:
    """QualificationResult with all gates True and no failure info."""
    qr = QualificationResult(
        qualified=True,
        reported_token_support=True,
        forced_tool_support=True,
        trace_support=True,
        run_completion_support=True,
    )
    assert qr.qualified is True
    assert qr.failure_reason is None
    assert qr.evidence_paths is None


def test_qualification_result_not_qualified_with_reason() -> None:
    """QualificationResult can record a failure reason and evidence paths."""
    qr = QualificationResult(
        qualified=False,
        reported_token_support=False,
        forced_tool_support=True,
        trace_support=True,
        run_completion_support=True,
        failure_reason="Token extraction failed: no token summary in stdout",
        evidence_paths=["/tmp/run/stdout.log"],
    )
    assert qr.qualified is False
    assert qr.reported_token_support is False
    assert "Token extraction failed" in (qr.failure_reason or "")
    assert qr.evidence_paths == ["/tmp/run/stdout.log"]


def test_qualification_result_optional_fields_default_to_none() -> None:
    """failure_reason and evidence_paths default to None when omitted."""
    qr = QualificationResult(
        qualified=True,
        reported_token_support=True,
        forced_tool_support=True,
        trace_support=True,
        run_completion_support=True,
    )
    assert qr.failure_reason is None
    assert qr.evidence_paths is None


def test_qualification_result_partial_failure() -> None:
    """A result with mixed gate values is not qualified."""
    qr = QualificationResult(
        qualified=False,
        reported_token_support=True,
        forced_tool_support=False,
        trace_support=True,
        run_completion_support=False,
        failure_reason="forced_tool_support and run_completion_support failed",
    )
    assert qr.qualified is False
    assert qr.forced_tool_support is False
    assert qr.run_completion_support is False
