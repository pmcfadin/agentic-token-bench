"""Tests for agents/claude/adapter.py and agents/claude/parser.py."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from agents.claude.adapter import ClaudeAdapter, _TIMEOUT_EXIT_CODE
from agents.claude.parser import extract_tokens_from_output, parse_claude_json_output

# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

_CLAUDE_BINARY = "/Applications/cmux.app/Contents/Resources/bin/claude"
_CLAUDE_AVAILABLE = shutil.which(_CLAUDE_BINARY) is not None or Path(_CLAUDE_BINARY).exists()

# Realistic JSON output captured from ``claude -p ... --output-format json``.
_SAMPLE_JSON_OUTPUT = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 2716,
        "duration_api_ms": 2293,
        "num_turns": 1,
        "result": "ok",
        "stop_reason": "end_turn",
        "session_id": "85c23744-855e-42d9-a88f-8b1dbf010695",
        "total_cost_usd": 0.08118924999999999,
        "usage": {
            "input_tokens": 3,
            "cache_creation_input_tokens": 12447,
            "cache_read_input_tokens": 6561,
            "output_tokens": 4,
            "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
            "service_tier": "standard",
        },
        "modelUsage": {
            "claude-opus-4-6[1m]": {
                "inputTokens": 3,
                "outputTokens": 4,
                "cacheReadInputTokens": 6561,
                "cacheCreationInputTokens": 12447,
                "webSearchRequests": 0,
                "costUSD": 0.08118924999999999,
            }
        },
        "permission_denials": [],
    }
)

_SAMPLE_JSON_NO_USAGE = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "result": "something",
    }
)

_SAMPLE_JSON_ZERO_TOKENS = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "result": "empty",
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
        },
    }
)


# ---------------------------------------------------------------------------
# parse_claude_json_output
# ---------------------------------------------------------------------------


def test_parse_valid_json_returns_dict() -> None:
    result = parse_claude_json_output(_SAMPLE_JSON_OUTPUT)
    assert isinstance(result, dict)


def test_parse_valid_json_type_field() -> None:
    result = parse_claude_json_output(_SAMPLE_JSON_OUTPUT)
    assert result["type"] == "result"


def test_parse_valid_json_usage_present() -> None:
    result = parse_claude_json_output(_SAMPLE_JSON_OUTPUT)
    assert "usage" in result


def test_parse_empty_string_returns_empty_dict() -> None:
    result = parse_claude_json_output("")
    assert result == {}


def test_parse_whitespace_only_returns_empty_dict() -> None:
    result = parse_claude_json_output("   \n  ")
    assert result == {}


def test_parse_invalid_json_returns_empty_dict() -> None:
    result = parse_claude_json_output("not valid json {{{")
    assert result == {}


def test_parse_json_without_usage_field() -> None:
    result = parse_claude_json_output(_SAMPLE_JSON_NO_USAGE)
    assert result["type"] == "result"
    assert "usage" not in result


# ---------------------------------------------------------------------------
# extract_tokens_from_output
# ---------------------------------------------------------------------------


def test_extract_tokens_returns_four_tuple() -> None:
    result = extract_tokens_from_output(_SAMPLE_JSON_OUTPUT)
    assert len(result) == 4


def test_extract_tokens_input_count() -> None:
    input_tokens, _, _, _ = extract_tokens_from_output(_SAMPLE_JSON_OUTPUT)
    assert input_tokens == 3


def test_extract_tokens_output_count() -> None:
    _, output_tokens, _, _ = extract_tokens_from_output(_SAMPLE_JSON_OUTPUT)
    assert output_tokens == 4


def test_extract_tokens_total_is_input_plus_output() -> None:
    input_tokens, output_tokens, total_tokens, _ = extract_tokens_from_output(
        _SAMPLE_JSON_OUTPUT
    )
    assert total_tokens == input_tokens + output_tokens


def test_extract_tokens_evidence_is_non_empty_string() -> None:
    _, _, _, evidence = extract_tokens_from_output(_SAMPLE_JSON_OUTPUT)
    assert isinstance(evidence, str)
    assert len(evidence) > 0


def test_extract_tokens_evidence_contains_token_data() -> None:
    _, _, _, evidence = extract_tokens_from_output(_SAMPLE_JSON_OUTPUT)
    # Evidence should be JSON-parseable and contain token counts.
    parsed_evidence = json.loads(evidence)
    assert "input_tokens" in parsed_evidence
    assert "output_tokens" in parsed_evidence


def test_extract_tokens_empty_output_returns_zeros() -> None:
    input_tokens, output_tokens, total_tokens, evidence = extract_tokens_from_output("")
    assert input_tokens == 0
    assert output_tokens == 0
    assert total_tokens == 0
    assert evidence == ""


def test_extract_tokens_no_usage_block_returns_zeros() -> None:
    input_tokens, output_tokens, total_tokens, evidence = extract_tokens_from_output(
        _SAMPLE_JSON_NO_USAGE
    )
    assert input_tokens == 0
    assert output_tokens == 0
    assert total_tokens == 0
    assert evidence == ""


def test_extract_tokens_zero_usage_values() -> None:
    input_tokens, output_tokens, total_tokens, _ = extract_tokens_from_output(
        _SAMPLE_JSON_ZERO_TOKENS
    )
    assert input_tokens == 0
    assert output_tokens == 0
    assert total_tokens == 0


# ---------------------------------------------------------------------------
# ClaudeAdapter — instantiation
# ---------------------------------------------------------------------------


def test_claude_adapter_can_be_instantiated_default() -> None:
    adapter = ClaudeAdapter()
    assert isinstance(adapter, ClaudeAdapter)


def test_claude_adapter_is_agent_adapter_subclass() -> None:
    adapter = ClaudeAdapter()
    assert isinstance(adapter, AgentAdapter)


def test_claude_adapter_custom_binary_path() -> None:
    adapter = ClaudeAdapter(binary_path="/custom/path/to/claude")
    assert adapter._binary_path == "/custom/path/to/claude"


def test_claude_adapter_default_binary_path() -> None:
    adapter = ClaudeAdapter()
    assert adapter._binary_path == "claude"


# ---------------------------------------------------------------------------
# ClaudeAdapter.normalize_final_status
# ---------------------------------------------------------------------------


def _make_step_result(exit_status: int, stdout: str = "", stderr: str = "") -> StepResult:
    return StepResult(
        stdout=stdout,
        stderr=stderr,
        exit_status=exit_status,
        step_metadata={},
        trace_metadata={},
    )


def test_normalize_exit_0_is_completed() -> None:
    adapter = ClaudeAdapter()
    result = _make_step_result(exit_status=0)
    assert adapter.normalize_final_status(result) == "completed"


def test_normalize_exit_1_is_failed() -> None:
    adapter = ClaudeAdapter()
    result = _make_step_result(exit_status=1)
    assert adapter.normalize_final_status(result) == "failed"


def test_normalize_exit_2_is_failed() -> None:
    adapter = ClaudeAdapter()
    result = _make_step_result(exit_status=2)
    assert adapter.normalize_final_status(result) == "failed"


def test_normalize_timeout_exit_code_is_timeout() -> None:
    adapter = ClaudeAdapter()
    result = _make_step_result(exit_status=_TIMEOUT_EXIT_CODE)
    assert adapter.normalize_final_status(result) == "timeout"


def test_normalize_timeout_exit_code_value_is_124() -> None:
    assert _TIMEOUT_EXIT_CODE == 124


def test_normalize_nonzero_non_timeout_is_failed() -> None:
    adapter = ClaudeAdapter()
    for code in (3, 10, 127, 255):
        result = _make_step_result(exit_status=code)
        assert adapter.normalize_final_status(result) == "failed", f"Expected failed for {code}"


# ---------------------------------------------------------------------------
# ClaudeAdapter.extract_reported_tokens
# ---------------------------------------------------------------------------


def test_extract_reported_tokens_returns_reported_tokens_instance() -> None:
    adapter = ClaudeAdapter()
    sr = _make_step_result(exit_status=0, stdout=_SAMPLE_JSON_OUTPUT)
    tokens = adapter.extract_reported_tokens(sr)
    assert isinstance(tokens, ReportedTokens)


def test_extract_reported_tokens_input_tokens() -> None:
    adapter = ClaudeAdapter()
    sr = _make_step_result(exit_status=0, stdout=_SAMPLE_JSON_OUTPUT)
    tokens = adapter.extract_reported_tokens(sr)
    assert tokens.input_tokens == 3


def test_extract_reported_tokens_output_tokens() -> None:
    adapter = ClaudeAdapter()
    sr = _make_step_result(exit_status=0, stdout=_SAMPLE_JSON_OUTPUT)
    tokens = adapter.extract_reported_tokens(sr)
    assert tokens.output_tokens == 4


def test_extract_reported_tokens_total_tokens() -> None:
    adapter = ClaudeAdapter()
    sr = _make_step_result(exit_status=0, stdout=_SAMPLE_JSON_OUTPUT)
    tokens = adapter.extract_reported_tokens(sr)
    assert tokens.total_tokens == 7


def test_extract_reported_tokens_evidence_snippet_non_empty() -> None:
    adapter = ClaudeAdapter()
    sr = _make_step_result(exit_status=0, stdout=_SAMPLE_JSON_OUTPUT)
    tokens = adapter.extract_reported_tokens(sr)
    assert isinstance(tokens.evidence_snippet, str)
    assert len(tokens.evidence_snippet) > 0


def test_extract_reported_tokens_empty_stdout_returns_zeros() -> None:
    adapter = ClaudeAdapter()
    sr = _make_step_result(exit_status=0, stdout="")
    tokens = adapter.extract_reported_tokens(sr)
    assert tokens.input_tokens == 0
    assert tokens.output_tokens == 0
    assert tokens.total_tokens == 0


# ---------------------------------------------------------------------------
# ClaudeAdapter.run_step — mocked subprocess
# ---------------------------------------------------------------------------


def _make_completed_proc(stdout: str = _SAMPLE_JSON_OUTPUT, returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.stderr = ""
    proc.returncode = returncode
    return proc


def test_run_step_returns_step_result(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        sr = adapter.run_step("do something", {"PATH": "/usr/bin"}, tmp_path, 30.0)
    assert isinstance(sr, StepResult)


def test_run_step_stdout_captured(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        sr = adapter.run_step("do something", {}, tmp_path, 30.0)
    assert sr.stdout == _SAMPLE_JSON_OUTPUT


def test_run_step_exit_status_zero(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        sr = adapter.run_step("task", {}, tmp_path, 30.0)
    assert sr.exit_status == 0


def test_run_step_exit_status_nonzero(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    proc = _make_completed_proc(stdout="", returncode=1)
    with patch("agents.claude.adapter.subprocess.run", return_value=proc):
        sr = adapter.run_step("task", {}, tmp_path, 30.0)
    assert sr.exit_status == 1


def test_run_step_step_metadata_has_timed_out_false(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        sr = adapter.run_step("task", {}, tmp_path, 30.0)
    assert sr.step_metadata["timed_out"] is False


def test_run_step_step_metadata_has_duration_ms(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        sr = adapter.run_step("task", {}, tmp_path, 30.0)
    assert "duration_ms" in sr.step_metadata
    assert sr.step_metadata["duration_ms"] >= 0


def test_run_step_step_metadata_captures_stop_reason(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        sr = adapter.run_step("task", {}, tmp_path, 30.0)
    assert sr.step_metadata.get("stop_reason") == "end_turn"


def test_run_step_trace_metadata_has_usage(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        sr = adapter.run_step("task", {}, tmp_path, 30.0)
    assert "usage" in sr.trace_metadata


def test_run_step_timeout_sets_timeout_exit_code(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    exc = subprocess.TimeoutExpired(cmd=["claude"], timeout=30.0)
    exc.stdout = None
    exc.stderr = None
    with patch("agents.claude.adapter.subprocess.run", side_effect=exc):
        sr = adapter.run_step("task", {}, tmp_path, 30.0)
    assert sr.exit_status == _TIMEOUT_EXIT_CODE


def test_run_step_timeout_sets_timed_out_flag(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    exc = subprocess.TimeoutExpired(cmd=["claude"], timeout=30.0)
    exc.stdout = None
    exc.stderr = None
    with patch("agents.claude.adapter.subprocess.run", side_effect=exc):
        sr = adapter.run_step("task", {}, tmp_path, 30.0)
    assert sr.step_metadata["timed_out"] is True


def test_run_step_timeout_status_is_timeout(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    exc = subprocess.TimeoutExpired(cmd=["claude"], timeout=30.0)
    exc.stdout = None
    exc.stderr = None
    with patch("agents.claude.adapter.subprocess.run", side_effect=exc):
        sr = adapter.run_step("task", {}, tmp_path, 30.0)
    assert adapter.normalize_final_status(sr) == "timeout"


def test_run_step_invokes_binary_with_output_format_json(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()) as m:
        adapter.run_step("task prompt", {}, tmp_path, 30.0)
    call_args = m.call_args
    cmd = call_args[0][0]  # first positional arg is the command list
    assert "--output-format" in cmd
    assert "json" in cmd


def test_run_step_passes_prompt_to_cli(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()) as m:
        adapter.run_step("my special prompt", {}, tmp_path, 30.0)
    cmd = m.call_args[0][0]
    assert "my special prompt" in cmd


def test_run_step_passes_env_to_subprocess(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    env = {"PATH": "/constrained/bin", "MY_VAR": "1"}
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()) as m:
        adapter.run_step("task", env, tmp_path, 30.0)
    assert m.call_args.kwargs["env"] == env


def test_run_step_passes_workspace_as_cwd(tmp_path: Path) -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()) as m:
        adapter.run_step("task", {}, tmp_path, 30.0)
    assert m.call_args.kwargs["cwd"] == tmp_path


# ---------------------------------------------------------------------------
# ClaudeAdapter.probe — mocked subprocess
# ---------------------------------------------------------------------------


def test_probe_returns_qualification_result() -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        result = adapter.probe()
    assert isinstance(result, QualificationResult)


def test_probe_qualified_when_tokens_extracted() -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        result = adapter.probe()
    assert result.qualified is True


def test_probe_all_gates_true_on_success() -> None:
    adapter = ClaudeAdapter()
    with patch("agents.claude.adapter.subprocess.run", return_value=_make_completed_proc()):
        result = adapter.probe()
    assert result.reported_token_support is True
    assert result.forced_tool_support is True
    assert result.trace_support is True
    assert result.run_completion_support is True


def test_probe_not_qualified_when_binary_missing() -> None:
    adapter = ClaudeAdapter(binary_path="/nonexistent/claude")
    with patch(
        "agents.claude.adapter.subprocess.run", side_effect=FileNotFoundError("not found")
    ):
        result = adapter.probe()
    assert result.qualified is False
    assert result.reported_token_support is False


def test_probe_failure_reason_set_on_file_not_found() -> None:
    adapter = ClaudeAdapter(binary_path="/nonexistent/claude")
    with patch(
        "agents.claude.adapter.subprocess.run", side_effect=FileNotFoundError("not found")
    ):
        result = adapter.probe()
    assert result.failure_reason is not None
    assert "not found" in result.failure_reason.lower()


def test_probe_not_qualified_when_nonzero_exit() -> None:
    adapter = ClaudeAdapter()
    proc = _make_completed_proc(stdout="", returncode=1)
    proc.stderr = "some error"
    with patch("agents.claude.adapter.subprocess.run", return_value=proc):
        result = adapter.probe()
    assert result.qualified is False


def test_probe_not_qualified_when_no_token_data() -> None:
    adapter = ClaudeAdapter()
    proc = _make_completed_proc(stdout=_SAMPLE_JSON_NO_USAGE, returncode=0)
    with patch("agents.claude.adapter.subprocess.run", return_value=proc):
        result = adapter.probe()
    assert result.qualified is False
    assert result.reported_token_support is False


def test_probe_not_qualified_on_timeout() -> None:
    adapter = ClaudeAdapter()
    exc = subprocess.TimeoutExpired(cmd=["claude"], timeout=60.0)
    with patch("agents.claude.adapter.subprocess.run", side_effect=exc):
        result = adapter.probe()
    assert result.qualified is False
    assert "timed out" in (result.failure_reason or "").lower()


# ---------------------------------------------------------------------------
# Integration — real binary (skipped unless available)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="Claude binary not installed")
def test_probe_with_real_binary() -> None:
    """Integration test: probe() against the real claude binary."""
    adapter = ClaudeAdapter(binary_path=_CLAUDE_BINARY)
    result = adapter.probe()
    assert isinstance(result, QualificationResult)
    assert result.qualified is True


@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="Claude binary not installed")
def test_run_step_with_real_binary(tmp_path: Path) -> None:
    """Integration test: run_step() against the real claude binary.

    Passes the current process environment so that the subprocess can locate
    its own runtime dependencies (node, etc.) on PATH.
    """
    import os

    adapter = ClaudeAdapter(binary_path=_CLAUDE_BINARY)
    sr = adapter.run_step(
        prompt="Reply with the single word 'ok' and nothing else.",
        step_env=dict(os.environ),
        workspace=tmp_path,
        timeout=60.0,
    )
    assert isinstance(sr, StepResult)
    assert sr.exit_status == 0
    tokens = adapter.extract_reported_tokens(sr)
    assert tokens.total_tokens > 0
