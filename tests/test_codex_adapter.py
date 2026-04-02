"""Tests for agents/codex/adapter.py and agents/codex/parser.py."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agents.base import QualificationResult, ReportedTokens, StepResult
from agents.codex.adapter import CodexAdapter
from agents.codex.parser import (
    extract_tokens_from_output,
    parse_codex_output,
)

_CODEX_AVAILABLE = shutil.which("codex") is not None

# Fast model for integration tests — correctness doesn't matter, only adapter plumbing.
_FAST_MODEL = "gpt-5.4-mini"

# ---------------------------------------------------------------------------
# Fixture data: JSON Lines output
# ---------------------------------------------------------------------------

_JSONL_TURN_COMPLETED = json.dumps(
    {
        "type": "turn.completed",
        "usage": {
            "input_tokens": 12806,
            "cached_input_tokens": 3456,
            "output_tokens": 66,
        },
    }
)

_JSONL_AGENT_MESSAGE = json.dumps(
    {
        "type": "item.completed",
        "item": {"id": "item_1", "type": "agent_message", "text": "hello"},
    }
)

_JSONL_THREAD_STARTED = json.dumps(
    {"type": "thread.started", "thread_id": "019d44f4-4f93-7d63-b515-928f7f68dc5d"}
)

_JSONL_TURN_STARTED = json.dumps({"type": "turn.started"})

FIXTURE_JSONL_OUTPUT = "\n".join(
    [
        _JSONL_THREAD_STARTED,
        _JSONL_TURN_STARTED,
        _JSONL_AGENT_MESSAGE,
        _JSONL_TURN_COMPLETED,
    ]
)

# Plain-text output fixture (no --json flag)
FIXTURE_PLAINTEXT_OUTPUT = """\
OpenAI Codex v0.117.0 (research preview)
--------
workdir: /tmp
model: gpt-5.4
provider: openai
--------
user
say hello
codex
hello
tokens used
9,428
hello
"""

# Plain-text output without token summary (failure case)
FIXTURE_PLAINTEXT_NO_TOKENS = """\
OpenAI Codex v0.117.0 (research preview)
user
say hello
codex
hello
"""


# ---------------------------------------------------------------------------
# Adapter instantiation
# ---------------------------------------------------------------------------


class TestCodexAdapterInstantiation:
    def test_default_binary_path(self) -> None:
        """CodexAdapter uses 'codex' as the default binary path."""
        adapter = CodexAdapter(model=_FAST_MODEL)
        assert adapter._binary_path == "codex"

    def test_custom_binary_path(self) -> None:
        """CodexAdapter accepts a custom binary path."""
        adapter = CodexAdapter(binary_path="/opt/homebrew/bin/codex")
        assert adapter._binary_path == "/opt/homebrew/bin/codex"

    def test_is_agent_adapter_subclass(self) -> None:
        """CodexAdapter is a concrete subclass of AgentAdapter."""
        from agents.base import AgentAdapter

        assert issubclass(CodexAdapter, AgentAdapter)

    def test_instantiation_with_nonexistent_binary(self) -> None:
        """CodexAdapter can be instantiated even with a missing binary."""
        adapter = CodexAdapter(binary_path="definitely_not_a_real_binary_xyz")
        assert adapter._available is False


# ---------------------------------------------------------------------------
# parse_codex_output – JSON Lines mode
# ---------------------------------------------------------------------------


class TestParseCodexOutputJsonl:
    def test_mode_is_json(self) -> None:
        result = parse_codex_output(FIXTURE_JSONL_OUTPUT)
        assert result["mode"] == "json"

    def test_input_tokens_extracted(self) -> None:
        result = parse_codex_output(FIXTURE_JSONL_OUTPUT)
        assert result["input_tokens"] == 12806

    def test_output_tokens_extracted(self) -> None:
        result = parse_codex_output(FIXTURE_JSONL_OUTPUT)
        assert result["output_tokens"] == 66

    def test_total_tokens_derived(self) -> None:
        """total_tokens is derived as input + output when not explicit."""
        result = parse_codex_output(FIXTURE_JSONL_OUTPUT)
        assert result["total_tokens"] == 12806 + 66

    def test_cached_input_tokens_extracted(self) -> None:
        result = parse_codex_output(FIXTURE_JSONL_OUTPUT)
        assert result["cached_input_tokens"] == 3456

    def test_evidence_snippet_contains_turn_completed(self) -> None:
        result = parse_codex_output(FIXTURE_JSONL_OUTPUT)
        assert "turn.completed" in result["evidence_snippet"]

    def test_events_list_populated(self) -> None:
        result = parse_codex_output(FIXTURE_JSONL_OUTPUT)
        assert len(result["events"]) == 4

    def test_agent_text_extracted(self) -> None:
        result = parse_codex_output(FIXTURE_JSONL_OUTPUT)
        assert result["agent_text"] == "hello"

    def test_empty_jsonl(self) -> None:
        """Empty output yields None token values and empty events."""
        result = parse_codex_output("")
        assert result["mode"] == "plaintext"
        assert result["total_tokens"] is None

    def test_jsonl_with_explicit_total_tokens(self) -> None:
        """When turn.completed includes total_tokens, it is used directly."""
        event = {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
        }
        output = json.dumps(event)
        result = parse_codex_output(output)
        assert result["total_tokens"] == 150

    def test_multiple_turn_completed_uses_last(self) -> None:
        """When multiple turn.completed events exist, the last is used."""
        first = json.dumps(
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}}
        )
        second = json.dumps(
            {"type": "turn.completed", "usage": {"input_tokens": 200, "output_tokens": 80}}
        )
        result = parse_codex_output(f"{first}\n{second}")
        assert result["input_tokens"] == 200
        assert result["output_tokens"] == 80


# ---------------------------------------------------------------------------
# parse_codex_output – plain-text mode
# ---------------------------------------------------------------------------


class TestParseCodexOutputPlaintext:
    def test_mode_is_plaintext(self) -> None:
        result = parse_codex_output(FIXTURE_PLAINTEXT_OUTPUT)
        assert result["mode"] == "plaintext"

    def test_total_tokens_extracted(self) -> None:
        """Plain-text 'tokens used\\n9,428' → total_tokens=9428."""
        result = parse_codex_output(FIXTURE_PLAINTEXT_OUTPUT)
        assert result["total_tokens"] == 9428

    def test_input_output_tokens_zero_in_plaintext(self) -> None:
        """Plain-text mode reports 0 for input and output (not broken out)."""
        result = parse_codex_output(FIXTURE_PLAINTEXT_OUTPUT)
        assert result["input_tokens"] == 0
        assert result["output_tokens"] == 0

    def test_evidence_snippet_present(self) -> None:
        result = parse_codex_output(FIXTURE_PLAINTEXT_OUTPUT)
        assert result["evidence_snippet"] is not None
        assert "tokens used" in result["evidence_snippet"].lower()

    def test_agent_text_extracted(self) -> None:
        result = parse_codex_output(FIXTURE_PLAINTEXT_OUTPUT)
        assert "hello" in result["agent_text"]

    def test_no_tokens_yields_none(self) -> None:
        """Output without a token summary yields None for total_tokens."""
        result = parse_codex_output(FIXTURE_PLAINTEXT_NO_TOKENS)
        assert result["total_tokens"] is None

    def test_events_empty_in_plaintext_mode(self) -> None:
        result = parse_codex_output(FIXTURE_PLAINTEXT_OUTPUT)
        assert result["events"] == []


# ---------------------------------------------------------------------------
# extract_tokens_from_output
# ---------------------------------------------------------------------------


class TestExtractTokensFromOutput:
    def test_jsonl_returns_correct_tuple(self) -> None:
        inp, out, total, snippet = extract_tokens_from_output(FIXTURE_JSONL_OUTPUT)
        assert inp == 12806
        assert out == 66
        assert total == 12806 + 66
        assert "turn.completed" in snippet

    def test_plaintext_returns_correct_tuple(self) -> None:
        inp, out, total, snippet = extract_tokens_from_output(FIXTURE_PLAINTEXT_OUTPUT)
        assert inp == 0
        assert out == 0
        assert total == 9428
        assert snippet != ""

    def test_no_tokens_raises_value_error(self) -> None:
        """Raises ValueError when no token info is found."""
        with pytest.raises(ValueError, match="No token counts found"):
            extract_tokens_from_output(FIXTURE_PLAINTEXT_NO_TOKENS)

    def test_returns_four_tuple(self) -> None:
        result = extract_tokens_from_output(FIXTURE_JSONL_OUTPUT)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# normalize_final_status
# ---------------------------------------------------------------------------


class TestNormalizeFinalStatus:
    def _make_result(self, exit_status: int, timed_out: bool = False) -> StepResult:
        return StepResult(
            stdout="",
            stderr="",
            exit_status=exit_status,
            step_metadata={"timed_out": timed_out},
            trace_metadata={},
        )

    def test_exit_zero_is_completed(self) -> None:
        adapter = CodexAdapter(model=_FAST_MODEL)
        assert adapter.normalize_final_status(self._make_result(0)) == "completed"

    def test_exit_one_is_failed(self) -> None:
        adapter = CodexAdapter(model=_FAST_MODEL)
        assert adapter.normalize_final_status(self._make_result(1)) == "failed"

    def test_exit_two_is_failed(self) -> None:
        adapter = CodexAdapter(model=_FAST_MODEL)
        assert adapter.normalize_final_status(self._make_result(2)) == "failed"

    def test_exit_124_is_timeout(self) -> None:
        """Exit code 124 (GNU timeout) maps to 'timeout'."""
        adapter = CodexAdapter(model=_FAST_MODEL)
        assert adapter.normalize_final_status(self._make_result(124)) == "timeout"

    def test_exit_143_is_timeout(self) -> None:
        """Exit code 143 (SIGTERM) maps to 'timeout'."""
        adapter = CodexAdapter(model=_FAST_MODEL)
        assert adapter.normalize_final_status(self._make_result(143)) == "timeout"

    def test_timed_out_flag_overrides_exit_code(self) -> None:
        """timed_out=True in step_metadata always yields 'timeout'."""
        adapter = CodexAdapter(model=_FAST_MODEL)
        result = self._make_result(0, timed_out=True)
        assert adapter.normalize_final_status(result) == "timeout"

    def test_unknown_exit_code_is_failed(self) -> None:
        """Unmapped exit codes default to 'failed'."""
        adapter = CodexAdapter(model=_FAST_MODEL)
        assert adapter.normalize_final_status(self._make_result(99)) == "failed"

    def test_exit_127_is_failed(self) -> None:
        """Exit 127 (command not found) maps to 'failed'."""
        adapter = CodexAdapter(model=_FAST_MODEL)
        assert adapter.normalize_final_status(self._make_result(127)) == "failed"


# ---------------------------------------------------------------------------
# extract_reported_tokens (via adapter)
# ---------------------------------------------------------------------------


class TestExtractReportedTokens:
    def _make_result_with_stdout(self, stdout: str) -> StepResult:
        return StepResult(
            stdout=stdout,
            stderr="",
            exit_status=0,
            step_metadata={},
            trace_metadata={},
        )

    def test_returns_reported_tokens_instance(self) -> None:
        adapter = CodexAdapter(model=_FAST_MODEL)
        result = self._make_result_with_stdout(FIXTURE_JSONL_OUTPUT)
        tokens = adapter.extract_reported_tokens(result)
        assert isinstance(tokens, ReportedTokens)

    def test_input_tokens_correct(self) -> None:
        adapter = CodexAdapter(model=_FAST_MODEL)
        result = self._make_result_with_stdout(FIXTURE_JSONL_OUTPUT)
        tokens = adapter.extract_reported_tokens(result)
        assert tokens.input_tokens == 12806

    def test_output_tokens_correct(self) -> None:
        adapter = CodexAdapter(model=_FAST_MODEL)
        result = self._make_result_with_stdout(FIXTURE_JSONL_OUTPUT)
        tokens = adapter.extract_reported_tokens(result)
        assert tokens.output_tokens == 66

    def test_total_tokens_correct(self) -> None:
        adapter = CodexAdapter(model=_FAST_MODEL)
        result = self._make_result_with_stdout(FIXTURE_JSONL_OUTPUT)
        tokens = adapter.extract_reported_tokens(result)
        assert tokens.total_tokens == 12806 + 66

    def test_evidence_snippet_nonempty(self) -> None:
        adapter = CodexAdapter(model=_FAST_MODEL)
        result = self._make_result_with_stdout(FIXTURE_JSONL_OUTPUT)
        tokens = adapter.extract_reported_tokens(result)
        assert tokens.evidence_snippet != ""

    def test_raises_on_empty_output(self) -> None:
        adapter = CodexAdapter(model=_FAST_MODEL)
        result = self._make_result_with_stdout(FIXTURE_PLAINTEXT_NO_TOKENS)
        with pytest.raises(ValueError):
            adapter.extract_reported_tokens(result)


# ---------------------------------------------------------------------------
# probe() – unavailable binary (no real binary required)
# ---------------------------------------------------------------------------


class TestProbeUnavailable:
    def test_probe_unavailable_binary_returns_not_qualified(self) -> None:
        adapter = CodexAdapter(binary_path="definitely_not_a_real_binary_xyz")
        result = adapter.probe()
        assert isinstance(result, QualificationResult)
        assert result.qualified is False
        assert result.failure_reason is not None


# ---------------------------------------------------------------------------
# Integration — shared fixtures (one binary call per fixture, module scope)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _codex_probe_result() -> QualificationResult:
    """Single probe() call shared across all probe integration tests."""
    adapter = CodexAdapter(model=_FAST_MODEL)
    return adapter.probe()


@pytest.fixture(scope="module")
def _codex_run_step_result(tmp_path_factory: pytest.TempPathFactory) -> StepResult:
    """Single run_step() call shared across all run_step integration tests."""
    adapter = CodexAdapter(model=_FAST_MODEL)
    workspace = tmp_path_factory.mktemp("codex_ws")
    return adapter.run_step(
        prompt="Reply with the single word: hello",
        step_env={},
        workspace=workspace,
        timeout=120.0,
    )


# ---------------------------------------------------------------------------
# Integration / real binary tests (skipped when binary absent)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_adapter_available() -> None:
    """CodexAdapter._available is True when the binary exists on PATH."""
    adapter = CodexAdapter(model=_FAST_MODEL)
    assert adapter._available is True


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_run_step_returns_step_result(_codex_run_step_result: StepResult) -> None:
    """run_step() invokes the real codex binary and returns a StepResult."""
    assert isinstance(_codex_run_step_result, StepResult)
    assert _codex_run_step_result.exit_status == 0


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_run_step_captures_stdout(_codex_run_step_result: StepResult) -> None:
    """run_step() captures non-empty stdout from the real codex invocation."""
    assert isinstance(_codex_run_step_result.stdout, str)
    assert len(_codex_run_step_result.stdout) > 0


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_run_step_step_metadata_contains_binary_path(
    _codex_run_step_result: StepResult,
) -> None:
    """run_step() records the binary path in step_metadata."""
    assert "binary_path" in _codex_run_step_result.step_metadata
    assert _codex_run_step_result.step_metadata["binary_path"] == "codex"


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_run_step_trace_metadata_contains_events(
    _codex_run_step_result: StepResult,
) -> None:
    """run_step() populates trace_metadata['events'] from JSON Lines output."""
    assert isinstance(_codex_run_step_result.trace_metadata["events"], list)
    assert len(_codex_run_step_result.trace_metadata["events"]) > 0


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_extract_reported_tokens_from_real_run(
    _codex_run_step_result: StepResult,
) -> None:
    """extract_reported_tokens() returns valid counts from a real codex run."""
    adapter = CodexAdapter(model=_FAST_MODEL)
    tokens = adapter.extract_reported_tokens(_codex_run_step_result)
    assert isinstance(tokens, ReportedTokens)
    assert tokens.total_tokens > 0


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_extract_reported_tokens_evidence_snippet_nonempty(
    _codex_run_step_result: StepResult,
) -> None:
    """extract_reported_tokens() includes a non-empty evidence snippet."""
    adapter = CodexAdapter(model=_FAST_MODEL)
    tokens = adapter.extract_reported_tokens(_codex_run_step_result)
    assert tokens.evidence_snippet != ""


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_normalize_final_status_on_real_success(
    _codex_run_step_result: StepResult,
) -> None:
    """normalize_final_status() returns 'completed' for a successful real run."""
    adapter = CodexAdapter(model=_FAST_MODEL)
    assert adapter.normalize_final_status(_codex_run_step_result) == "completed"


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_probe_returns_qualification_result(
    _codex_probe_result: QualificationResult,
) -> None:
    """probe() returns a QualificationResult when the real binary is present."""
    assert isinstance(_codex_probe_result, QualificationResult)


@pytest.mark.integration
@pytest.mark.skipif(not _CODEX_AVAILABLE, reason="codex binary not installed")
def test_probe_qualified_with_real_binary(
    _codex_probe_result: QualificationResult,
) -> None:
    """probe() passes all qualification gates against the real codex binary."""
    assert _codex_probe_result.qualified is True
    assert _codex_probe_result.reported_token_support is True
    assert _codex_probe_result.trace_support is True
    assert _codex_probe_result.run_completion_support is True
