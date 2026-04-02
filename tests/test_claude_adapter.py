"""Tests for agents/claude/adapter.py and agents/claude/parser.py."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from agents.claude.adapter import ClaudeAdapter, _TIMEOUT_EXIT_CODE
from agents.claude.parser import extract_tokens_from_output, parse_claude_json_output

# ---------------------------------------------------------------------------
# Availability detection
# ---------------------------------------------------------------------------

_CLAUDE_BINARY = "/Applications/cmux.app/Contents/Resources/bin/claude"
_CLAUDE_AVAILABLE = shutil.which("claude") is not None or Path(_CLAUDE_BINARY).exists()

# Fast model for integration tests — correctness doesn't matter, only adapter plumbing.
_FAST_MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Fixture data — synthetic JSON strings for unit-testing parser logic
# ---------------------------------------------------------------------------

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
# parse_claude_json_output — unit tests (pure parser logic, no CLI)
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
# extract_tokens_from_output — unit tests (pure parser logic, no CLI)
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
# ClaudeAdapter — instantiation (no CLI invocation)
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
# ClaudeAdapter.normalize_final_status — unit tests (no CLI invocation)
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
# ClaudeAdapter.extract_reported_tokens — unit tests (synthetic StepResult)
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
# Integration — shared fixtures (one binary call per fixture, module scope)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _claude_probe_result() -> QualificationResult:
    """Single probe() call shared across all probe integration tests."""
    adapter = ClaudeAdapter(binary_path=_CLAUDE_BINARY, model=_FAST_MODEL)
    return adapter.probe()


@pytest.fixture(scope="module")
def _claude_run_step_result(tmp_path_factory: pytest.TempPathFactory) -> StepResult:
    """Single run_step() call shared across all run_step integration tests."""
    adapter = ClaudeAdapter(binary_path=_CLAUDE_BINARY, model=_FAST_MODEL)
    workspace = tmp_path_factory.mktemp("claude_ws")
    return adapter.run_step(
        prompt="Reply with the single word 'ok' and nothing else.",
        step_env=dict(os.environ),
        workspace=workspace,
        timeout=60.0,
    )


# ---------------------------------------------------------------------------
# Integration — probe tests (use shared _claude_probe_result)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_probe_with_real_binary_returns_qualification_result(
    _claude_probe_result: QualificationResult,
) -> None:
    assert isinstance(_claude_probe_result, QualificationResult)


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_probe_with_real_binary_is_qualified(
    _claude_probe_result: QualificationResult,
) -> None:
    assert _claude_probe_result.qualified is True


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_probe_with_real_binary_all_gates_true(
    _claude_probe_result: QualificationResult,
) -> None:
    assert _claude_probe_result.reported_token_support is True
    assert _claude_probe_result.forced_tool_support is True
    assert _claude_probe_result.trace_support is True
    assert _claude_probe_result.run_completion_support is True


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_probe_nonexistent_binary_not_qualified() -> None:
    """probe() returns qualified=False and sets a failure_reason when the binary is absent."""
    adapter = ClaudeAdapter(binary_path="/nonexistent/claude")
    result = adapter.probe()
    assert result.qualified is False
    assert result.reported_token_support is False
    assert result.failure_reason is not None
    assert "not found" in result.failure_reason.lower()


# ---------------------------------------------------------------------------
# Integration — run_step tests (use shared _claude_run_step_result)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_run_step_returns_step_result(_claude_run_step_result: StepResult) -> None:
    assert isinstance(_claude_run_step_result, StepResult)


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_run_step_exits_zero(_claude_run_step_result: StepResult) -> None:
    assert _claude_run_step_result.exit_status == 0


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_run_step_stdout_contains_json(_claude_run_step_result: StepResult) -> None:
    parsed = json.loads(_claude_run_step_result.stdout)
    assert parsed.get("type") == "result"


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_run_step_step_metadata_timed_out_false(_claude_run_step_result: StepResult) -> None:
    assert _claude_run_step_result.step_metadata["timed_out"] is False


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_run_step_step_metadata_has_duration_ms(_claude_run_step_result: StepResult) -> None:
    assert "duration_ms" in _claude_run_step_result.step_metadata
    assert _claude_run_step_result.step_metadata["duration_ms"] >= 0


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_run_step_extract_reported_tokens_nonzero(_claude_run_step_result: StepResult) -> None:
    adapter = ClaudeAdapter(binary_path=_CLAUDE_BINARY, model=_FAST_MODEL)
    tokens = adapter.extract_reported_tokens(_claude_run_step_result)
    assert isinstance(tokens, ReportedTokens)
    assert tokens.total_tokens > 0


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_run_step_extract_reported_tokens_has_evidence(_claude_run_step_result: StepResult) -> None:
    adapter = ClaudeAdapter(binary_path=_CLAUDE_BINARY, model=_FAST_MODEL)
    tokens = adapter.extract_reported_tokens(_claude_run_step_result)
    assert isinstance(tokens.evidence_snippet, str)
    assert len(tokens.evidence_snippet) > 0


@pytest.mark.integration
@pytest.mark.skipif(not _CLAUDE_AVAILABLE, reason="claude binary not installed")
def test_run_step_normalize_final_status_completed(_claude_run_step_result: StepResult) -> None:
    adapter = ClaudeAdapter(binary_path=_CLAUDE_BINARY, model=_FAST_MODEL)
    assert adapter.normalize_final_status(_claude_run_step_result) == "completed"
