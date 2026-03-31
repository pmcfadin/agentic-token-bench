"""Tests for agents/gemini_cli/adapter.py and agents/gemini_cli/parser.py."""

import os
import shutil
from pathlib import Path

import pytest

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from agents.gemini_cli.adapter import GeminiCliAdapter
from agents.gemini_cli.parser import extract_tokens_from_output, parse_gemini_output


# ---------------------------------------------------------------------------
# Fixture data — representative gemini stream-json output
# ---------------------------------------------------------------------------

_STREAM_JSON_SUCCESS = (
    '{"type":"init","timestamp":"2026-03-31T10:00:00.000Z","session_id":"abc123","model":"auto-gemini-3"}\n'
    '{"type":"message","timestamp":"2026-03-31T10:00:01.000Z","role":"user","content":"Say hello"}\n'
    '{"type":"message","timestamp":"2026-03-31T10:00:02.000Z","role":"assistant","content":"Hello!","delta":true}\n'
    '{"type":"result","timestamp":"2026-03-31T10:00:02.100Z","status":"success",'
    '"stats":{"total_tokens":1234,"input_tokens":1000,"output_tokens":234,"cached":0,'
    '"input":1000,"duration_ms":1000,"tool_calls":0}}\n'
)

_STREAM_JSON_NO_TOKENS = (
    '{"type":"init","timestamp":"2026-03-31T10:00:00.000Z","session_id":"abc123","model":"auto-gemini-3"}\n'
    '{"type":"message","timestamp":"2026-03-31T10:00:01.000Z","role":"user","content":"Hi"}\n'
    '{"type":"message","timestamp":"2026-03-31T10:00:02.000Z","role":"assistant","content":"Hi there!","delta":true}\n'
)

_PLAIN_TEXT_OUTPUT = "Hello, world!"

_PLAIN_TEXT_WITH_TOKENS = (
    "Hello, world!\n"
    "input_tokens: 100 output_tokens: 50 total_tokens: 150\n"
)


# ---------------------------------------------------------------------------
# Availability detection
# ---------------------------------------------------------------------------

_GEMINI_BINARY = shutil.which("gemini") or "/opt/homebrew/bin/gemini"
_GEMINI_AVAILABLE = bool(
    shutil.which("gemini")
    or (os.path.isfile("/opt/homebrew/bin/gemini") and os.access("/opt/homebrew/bin/gemini", os.X_OK))
)


# ---------------------------------------------------------------------------
# Adapter instantiation
# ---------------------------------------------------------------------------


def test_adapter_instantiation_default_binary() -> None:
    """GeminiCliAdapter can be instantiated with the default binary path."""
    adapter = GeminiCliAdapter()
    assert adapter.binary_path == "gemini"


def test_adapter_instantiation_custom_binary() -> None:
    """GeminiCliAdapter stores a custom binary path."""
    adapter = GeminiCliAdapter(binary_path="/opt/homebrew/bin/gemini")
    assert adapter.binary_path == "/opt/homebrew/bin/gemini"


def test_adapter_is_agent_adapter_subclass() -> None:
    """GeminiCliAdapter is a concrete subclass of AgentAdapter."""
    adapter = GeminiCliAdapter()
    assert isinstance(adapter, AgentAdapter)


# ---------------------------------------------------------------------------
# Parser: parse_gemini_output
# ---------------------------------------------------------------------------


def test_parse_stream_json_success_status() -> None:
    """parse_gemini_output extracts status=success from stream-json."""
    result = parse_gemini_output(_STREAM_JSON_SUCCESS)
    assert result["status"] == "success"


def test_parse_stream_json_stats() -> None:
    """parse_gemini_output extracts stats block from stream-json result line."""
    result = parse_gemini_output(_STREAM_JSON_SUCCESS)
    stats = result["stats"]
    assert stats["total_tokens"] == 1234
    assert stats["input_tokens"] == 1000
    assert stats["output_tokens"] == 234


def test_parse_stream_json_content() -> None:
    """parse_gemini_output concatenates assistant message content."""
    result = parse_gemini_output(_STREAM_JSON_SUCCESS)
    assert "Hello!" in result["content"]


def test_parse_stream_json_result_line_raw() -> None:
    """parse_gemini_output stores the raw result JSON line."""
    result = parse_gemini_output(_STREAM_JSON_SUCCESS)
    assert '"type":"result"' in result["result_line"]
    assert '"status":"success"' in result["result_line"]


def test_parse_stream_json_no_result_line() -> None:
    """parse_gemini_output returns empty stats when no result line is present."""
    result = parse_gemini_output(_STREAM_JSON_NO_TOKENS)
    assert result["stats"] == {}
    assert result["result_line"] == ""
    assert result["status"] == "unknown"


def test_parse_plain_text_output() -> None:
    """parse_gemini_output handles plain text output without JSON."""
    result = parse_gemini_output(_PLAIN_TEXT_OUTPUT)
    assert result["content"] == _PLAIN_TEXT_OUTPUT
    assert result["stats"] == {}
    assert result["status"] == "unknown"


def test_parse_empty_output() -> None:
    """parse_gemini_output handles empty string input gracefully."""
    result = parse_gemini_output("")
    assert result["content"] == ""
    assert result["stats"] == {}
    assert result["status"] == "unknown"


# ---------------------------------------------------------------------------
# Parser: extract_tokens_from_output
# ---------------------------------------------------------------------------


def test_extract_tokens_stream_json() -> None:
    """extract_tokens_from_output extracts counts from stream-json output."""
    inp, out, tot, evidence = extract_tokens_from_output(_STREAM_JSON_SUCCESS)
    assert inp == 1000
    assert out == 234
    assert tot == 1234
    assert evidence  # non-empty evidence snippet


def test_extract_tokens_evidence_contains_result_line() -> None:
    """Evidence snippet contains the raw result JSON line."""
    _, _, _, evidence = extract_tokens_from_output(_STREAM_JSON_SUCCESS)
    assert "total_tokens" in evidence


def test_extract_tokens_no_tokens_returns_zeros() -> None:
    """extract_tokens_from_output returns zeros when no token data is present."""
    inp, out, tot, evidence = extract_tokens_from_output(_STREAM_JSON_NO_TOKENS)
    assert inp == 0
    assert out == 0
    assert tot == 0
    assert evidence == ""


def test_extract_tokens_plain_text_no_tokens() -> None:
    """extract_tokens_from_output returns zeros for plain text without token info."""
    inp, out, tot, evidence = extract_tokens_from_output(_PLAIN_TEXT_OUTPUT)
    assert inp == 0
    assert out == 0
    assert tot == 0
    assert evidence == ""


def test_extract_tokens_empty_string() -> None:
    """extract_tokens_from_output returns zeros for empty input."""
    inp, out, tot, evidence = extract_tokens_from_output("")
    assert inp == 0
    assert out == 0
    assert tot == 0
    assert evidence == ""


# ---------------------------------------------------------------------------
# normalize_final_status
# ---------------------------------------------------------------------------


def _make_step_result(exit_status: int, metadata: dict | None = None) -> StepResult:
    return StepResult(
        stdout="",
        stderr="",
        exit_status=exit_status,
        step_metadata=metadata or {},
        trace_metadata={},
    )


def test_normalize_exit_0_is_completed() -> None:
    """exit_status 0 normalizes to 'completed'."""
    adapter = GeminiCliAdapter()
    sr = _make_step_result(0)
    assert adapter.normalize_final_status(sr) == "completed"


def test_normalize_exit_minus1_is_timeout() -> None:
    """exit_status -1 normalizes to 'timeout'."""
    adapter = GeminiCliAdapter()
    sr = _make_step_result(-1, {"timeout": True, "timeout_seconds": 30.0})
    assert adapter.normalize_final_status(sr) == "timeout"


def test_normalize_exit_nonzero_is_failed() -> None:
    """Non-zero, non-(-1) exit_status normalizes to 'failed'."""
    adapter = GeminiCliAdapter()
    for code in (1, 2, 127, 255):
        sr = _make_step_result(code)
        assert adapter.normalize_final_status(sr) == "failed"


def test_normalize_timeout_flag_in_metadata() -> None:
    """timeout=True in step_metadata normalizes to 'timeout' even with exit_status -1."""
    adapter = GeminiCliAdapter()
    sr = _make_step_result(-1, {"timeout": True})
    assert adapter.normalize_final_status(sr) == "timeout"


# ---------------------------------------------------------------------------
# extract_reported_tokens — synthetic StepResult data
# ---------------------------------------------------------------------------


def test_extract_reported_tokens_from_step_result() -> None:
    """extract_reported_tokens reads token counts from StepResult.stdout."""
    adapter = GeminiCliAdapter()
    sr = StepResult(
        stdout=_STREAM_JSON_SUCCESS,
        stderr="",
        exit_status=0,
        step_metadata={},
        trace_metadata={},
    )
    tokens = adapter.extract_reported_tokens(sr)
    assert isinstance(tokens, ReportedTokens)
    assert tokens.input_tokens == 1000
    assert tokens.output_tokens == 234
    assert tokens.total_tokens == 1234
    assert tokens.evidence_snippet


def test_extract_reported_tokens_zero_when_missing() -> None:
    """extract_reported_tokens returns zero counts when output has no token data."""
    adapter = GeminiCliAdapter()
    sr = StepResult(
        stdout=_PLAIN_TEXT_OUTPUT,
        stderr="",
        exit_status=0,
        step_metadata={},
        trace_metadata={},
    )
    tokens = adapter.extract_reported_tokens(sr)
    assert tokens.input_tokens == 0
    assert tokens.output_tokens == 0
    assert tokens.total_tokens == 0
    assert tokens.evidence_snippet == ""


# ---------------------------------------------------------------------------
# normalize_final_status on real StepResults
# ---------------------------------------------------------------------------


def test_normalize_on_synthetic_completed_step_result() -> None:
    """normalize_final_status returns 'completed' for a synthetic exit-0 StepResult."""
    adapter = GeminiCliAdapter()
    sr = StepResult(
        stdout=_STREAM_JSON_SUCCESS,
        stderr="",
        exit_status=0,
        step_metadata={"status": "success", "timeout": False},
        trace_metadata={},
    )
    assert adapter.normalize_final_status(sr) == "completed"


def test_normalize_on_synthetic_failed_step_result() -> None:
    """normalize_final_status returns 'failed' for a synthetic non-zero exit StepResult."""
    adapter = GeminiCliAdapter()
    sr = StepResult(
        stdout="",
        stderr="fatal error",
        exit_status=1,
        step_metadata={"status": "error", "timeout": False},
        trace_metadata={},
    )
    assert adapter.normalize_final_status(sr) == "failed"


def test_normalize_on_synthetic_timeout_step_result() -> None:
    """normalize_final_status returns 'timeout' for a synthetic timeout StepResult."""
    adapter = GeminiCliAdapter()
    sr = StepResult(
        stdout="",
        stderr="",
        exit_status=-1,
        step_metadata={"timeout": True, "timeout_seconds": 120.0},
        trace_metadata={},
    )
    assert adapter.normalize_final_status(sr) == "timeout"


# ---------------------------------------------------------------------------
# Integration tests — real Gemini CLI binary
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(not _GEMINI_AVAILABLE, reason="Gemini CLI binary not available")
def test_probe_real_binary_returns_qualification_result() -> None:
    """probe() against the real Gemini CLI returns a QualificationResult."""
    adapter = GeminiCliAdapter(binary_path=_GEMINI_BINARY)
    result = adapter.probe()
    assert isinstance(result, QualificationResult)


@pytest.mark.integration
@pytest.mark.skipif(not _GEMINI_AVAILABLE, reason="Gemini CLI binary not available")
def test_probe_real_binary_is_qualified() -> None:
    """probe() against the real Gemini CLI returns qualified=True with token support."""
    adapter = GeminiCliAdapter(binary_path=_GEMINI_BINARY)
    result = adapter.probe()
    assert result.qualified is True
    assert result.reported_token_support is True


@pytest.mark.integration
@pytest.mark.skipif(not _GEMINI_AVAILABLE, reason="Gemini CLI binary not available")
def test_run_step_real_binary_returns_step_result(tmp_path: Path) -> None:
    """run_step() with the real Gemini CLI returns a StepResult."""
    adapter = GeminiCliAdapter(binary_path=_GEMINI_BINARY)
    sr = adapter.run_step(
        prompt="Reply with the single word HELLO and nothing else.",
        step_env=dict(os.environ),
        workspace=tmp_path,
        timeout=120.0,
    )
    assert isinstance(sr, StepResult)


@pytest.mark.integration
@pytest.mark.skipif(not _GEMINI_AVAILABLE, reason="Gemini CLI binary not available")
def test_run_step_real_binary_exits_zero(tmp_path: Path) -> None:
    """run_step() with the real Gemini CLI exits with status 0."""
    adapter = GeminiCliAdapter(binary_path=_GEMINI_BINARY)
    sr = adapter.run_step(
        prompt="Reply with the single word HELLO and nothing else.",
        step_env=dict(os.environ),
        workspace=tmp_path,
        timeout=120.0,
    )
    assert sr.exit_status == 0


@pytest.mark.integration
@pytest.mark.skipif(not _GEMINI_AVAILABLE, reason="Gemini CLI binary not available")
def test_extract_reported_tokens_real_output(tmp_path: Path) -> None:
    """extract_reported_tokens() returns non-zero counts from real Gemini CLI output."""
    adapter = GeminiCliAdapter(binary_path=_GEMINI_BINARY)
    sr = adapter.run_step(
        prompt="Reply with the single word HELLO and nothing else.",
        step_env=dict(os.environ),
        workspace=tmp_path,
        timeout=120.0,
    )
    tokens = adapter.extract_reported_tokens(sr)
    assert isinstance(tokens, ReportedTokens)
    assert tokens.total_tokens > 0


@pytest.mark.integration
@pytest.mark.skipif(not _GEMINI_AVAILABLE, reason="Gemini CLI binary not available")
def test_normalize_final_status_real_output(tmp_path: Path) -> None:
    """normalize_final_status() returns 'completed' for a successful real run."""
    adapter = GeminiCliAdapter(binary_path=_GEMINI_BINARY)
    sr = adapter.run_step(
        prompt="Reply with the single word HELLO and nothing else.",
        step_env=dict(os.environ),
        workspace=tmp_path,
        timeout=120.0,
    )
    assert adapter.normalize_final_status(sr) == "completed"
