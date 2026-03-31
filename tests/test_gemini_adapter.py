"""Tests for agents/gemini_cli/adapter.py and agents/gemini_cli/parser.py."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.base import QualificationResult, ReportedTokens, StepResult
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
    from agents.base import AgentAdapter

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
# extract_reported_tokens
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
# run_step — mocked subprocess
# ---------------------------------------------------------------------------


def test_run_step_success_mocked(tmp_path: Path) -> None:
    """run_step returns a StepResult when subprocess succeeds."""
    adapter = GeminiCliAdapter(binary_path="/opt/homebrew/bin/gemini")
    mock_proc = MagicMock()
    mock_proc.stdout = _STREAM_JSON_SUCCESS
    mock_proc.stderr = ""
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        result = adapter.run_step(
            prompt="Say hello",
            step_env={},
            workspace=tmp_path,
            timeout=30.0,
        )

    assert isinstance(result, StepResult)
    assert result.exit_status == 0
    assert result.stdout == _STREAM_JSON_SUCCESS
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "/opt/homebrew/bin/gemini" in call_args
    assert "-p" in call_args
    assert "Say hello" in call_args
    assert "--output-format" in call_args
    assert "stream-json" in call_args


def test_run_step_passes_prompt_in_command(tmp_path: Path) -> None:
    """run_step passes the prompt via -p flag."""
    adapter = GeminiCliAdapter()
    mock_proc = MagicMock()
    mock_proc.stdout = ""
    mock_proc.stderr = ""
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        adapter.run_step(
            prompt="my custom prompt",
            step_env={},
            workspace=tmp_path,
            timeout=10.0,
        )

    cmd = mock_run.call_args[0][0]
    idx = cmd.index("-p")
    assert cmd[idx + 1] == "my custom prompt"


def test_run_step_timeout_returns_timeout_step_result(tmp_path: Path) -> None:
    """run_step returns exit_status=-1 and timeout=True when subprocess times out."""
    adapter = GeminiCliAdapter()

    timeout_exc = subprocess.TimeoutExpired(cmd=["gemini"], timeout=5.0)
    timeout_exc.stdout = b""
    timeout_exc.stderr = b""

    with patch("subprocess.run", side_effect=timeout_exc):
        result = adapter.run_step(
            prompt="do something slow",
            step_env={},
            workspace=tmp_path,
            timeout=5.0,
        )

    assert result.exit_status == -1
    assert result.step_metadata.get("timeout") is True


def test_run_step_step_metadata_contains_status(tmp_path: Path) -> None:
    """run_step populates step_metadata with the parsed status."""
    adapter = GeminiCliAdapter()
    mock_proc = MagicMock()
    mock_proc.stdout = _STREAM_JSON_SUCCESS
    mock_proc.stderr = ""
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc):
        result = adapter.run_step(
            prompt="Say hello",
            step_env={},
            workspace=tmp_path,
            timeout=30.0,
        )

    assert result.step_metadata["status"] == "success"


def test_run_step_nonzero_exit_sets_exit_status(tmp_path: Path) -> None:
    """run_step captures non-zero exit codes from the subprocess."""
    adapter = GeminiCliAdapter()
    mock_proc = MagicMock()
    mock_proc.stdout = ""
    mock_proc.stderr = "error: something went wrong"
    mock_proc.returncode = 1

    with patch("subprocess.run", return_value=mock_proc):
        result = adapter.run_step(
            prompt="do something",
            step_env={},
            workspace=tmp_path,
            timeout=30.0,
        )

    assert result.exit_status == 1


# ---------------------------------------------------------------------------
# probe — mocked subprocess (avoids requiring the real binary)
# ---------------------------------------------------------------------------


def test_probe_returns_qualification_result_mocked(tmp_path: Path) -> None:
    """probe() returns a QualificationResult."""
    adapter = GeminiCliAdapter()
    mock_proc = MagicMock()
    mock_proc.stdout = _STREAM_JSON_SUCCESS
    mock_proc.stderr = ""
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc):
        result = adapter.probe()

    assert isinstance(result, QualificationResult)


def test_probe_qualified_when_tokens_present_mocked() -> None:
    """probe() returns qualified=True when token data is present in output."""
    adapter = GeminiCliAdapter()
    mock_proc = MagicMock()
    mock_proc.stdout = _STREAM_JSON_SUCCESS
    mock_proc.stderr = ""
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc):
        result = adapter.probe()

    assert result.qualified is True
    assert result.reported_token_support is True


def test_probe_not_qualified_when_invocation_fails() -> None:
    """probe() returns qualified=False when the binary cannot be invoked."""
    adapter = GeminiCliAdapter(binary_path="/nonexistent/gemini")

    with patch("subprocess.run", side_effect=FileNotFoundError("binary not found")):
        result = adapter.probe()

    assert result.qualified is False
    assert result.reported_token_support is False
    assert result.failure_reason is not None
    assert "Binary invocation failed" in result.failure_reason


def test_probe_not_qualified_when_no_tokens(tmp_path: Path) -> None:
    """probe() returns qualified=False when output contains no token data."""
    adapter = GeminiCliAdapter()
    mock_proc = MagicMock()
    mock_proc.stdout = _STREAM_JSON_NO_TOKENS  # no result line, no token stats
    mock_proc.stderr = ""
    mock_proc.returncode = 0

    with patch("subprocess.run", return_value=mock_proc):
        result = adapter.probe()

    assert result.qualified is False
    assert result.reported_token_support is False


# ---------------------------------------------------------------------------
# Integration smoke test — requires real binary, skipped if unavailable
# ---------------------------------------------------------------------------

GEMINI_BINARY = "/opt/homebrew/bin/gemini"


def _gemini_available() -> bool:
    """Return True if the gemini binary is available at the expected path."""
    import os

    return os.path.isfile(GEMINI_BINARY) and os.access(GEMINI_BINARY, os.X_OK)


@pytest.mark.skipif(
    not _gemini_available(),
    reason="Gemini CLI binary not available at /opt/homebrew/bin/gemini",
)
def test_probe_real_binary(tmp_path: Path) -> None:
    """Smoke test: probe() against the real Gemini CLI binary."""
    adapter = GeminiCliAdapter(binary_path=GEMINI_BINARY)
    result = adapter.probe()
    # We just verify the return type; qualification depends on the environment.
    assert isinstance(result, QualificationResult)
