"""Tests for AstGrepWrapper."""

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from tools.base import InvocationRecord, InvocationResult, ToolManifest, ToolWrapper
from tools.ast_grep.wrapper import AstGrepWrapper

_AST_GREP_AVAILABLE = shutil.which("ast-grep") is not None or shutil.which("sg") is not None


# ---------------------------------------------------------------------------
# ABC conformance
# ---------------------------------------------------------------------------


def test_abc_conformance() -> None:
    wrapper = AstGrepWrapper()
    assert isinstance(wrapper, ToolWrapper)


# ---------------------------------------------------------------------------
# Manifest (always runs)
# ---------------------------------------------------------------------------


def test_manifest_returns_tool_manifest() -> None:
    wrapper = AstGrepWrapper()
    m = wrapper.manifest()
    assert isinstance(m, ToolManifest)


def test_manifest_id_is_ast_grep() -> None:
    wrapper = AstGrepWrapper()
    assert wrapper.manifest().id == "ast-grep"


def test_manifest_category_is_transformation() -> None:
    wrapper = AstGrepWrapper()
    assert wrapper.manifest().category == "transformation"


def test_manifest_has_transformation_waste_class() -> None:
    wrapper = AstGrepWrapper()
    assert "transformation_waste" in wrapper.manifest().waste_classes


def test_manifest_supported_languages_nonempty() -> None:
    wrapper = AstGrepWrapper()
    assert len(wrapper.manifest().supported_languages) > 0


# ---------------------------------------------------------------------------
# is_available (always runs)
# ---------------------------------------------------------------------------


def test_is_available_returns_bool() -> None:
    wrapper = AstGrepWrapper()
    assert isinstance(wrapper.is_available(), bool)


def test_is_available_false_when_binary_not_installed() -> None:
    # ast-grep is not installed on this machine
    wrapper = AstGrepWrapper()
    assert wrapper.is_available() is False


def test_is_available_false_for_nonexistent_binary() -> None:
    wrapper = AstGrepWrapper(binary_path="definitely_not_a_real_binary_xyz")
    assert wrapper.is_available() is False


# ---------------------------------------------------------------------------
# record_invocation with mock data (always runs)
# ---------------------------------------------------------------------------


def _make_mock_result(exit_status: int = 0, duration_ms: float = 42.0) -> InvocationResult:
    return InvocationResult(
        stdout="mock stdout",
        stderr="",
        exit_status=exit_status,
        duration_ms=duration_ms,
    )


def test_record_invocation_returns_invocation_record() -> None:
    wrapper = AstGrepWrapper()
    result = _make_mock_result()
    record = wrapper.record_invocation(result, ["run", "--pattern", "foo"], "step-1", "run-abc")
    assert isinstance(record, InvocationRecord)


def test_record_invocation_tool_id() -> None:
    wrapper = AstGrepWrapper()
    result = _make_mock_result()
    record = wrapper.record_invocation(result, ["run", "--pattern", "foo"], "step-1", "run-abc")
    assert record.tool_id == "ast-grep"


def test_record_invocation_step_and_run_id() -> None:
    wrapper = AstGrepWrapper()
    result = _make_mock_result()
    record = wrapper.record_invocation(result, ["run"], "step-99", "run-xyz")
    assert record.step_id == "step-99"
    assert record.run_id == "run-xyz"


def test_record_invocation_exit_status_matches_result() -> None:
    wrapper = AstGrepWrapper()
    result = _make_mock_result(exit_status=1)
    record = wrapper.record_invocation(result, ["run"], "s", "r")
    assert record.exit_status == 1


def test_record_invocation_duration_matches_result() -> None:
    wrapper = AstGrepWrapper()
    result = _make_mock_result(duration_ms=99.5)
    record = wrapper.record_invocation(result, ["run"], "s", "r")
    assert record.duration_ms == 99.5


def test_record_invocation_args_hash_is_sha256() -> None:
    wrapper = AstGrepWrapper()
    args = ["run", "--pattern", "console.log($A)"]
    result = _make_mock_result()
    record = wrapper.record_invocation(result, args, "s", "r")
    expected_hash = hashlib.sha256(" ".join(args).encode()).hexdigest()
    assert record.args_hash == expected_hash


def test_record_invocation_timestamp_is_timezone_aware() -> None:
    wrapper = AstGrepWrapper()
    result = _make_mock_result()
    record = wrapper.record_invocation(result, ["run"], "s", "r")
    assert record.timestamp.tzinfo is not None


def test_record_invocation_timestamp_is_datetime() -> None:
    wrapper = AstGrepWrapper()
    result = _make_mock_result()
    record = wrapper.record_invocation(result, ["run"], "s", "r")
    assert isinstance(record.timestamp, datetime)


# ---------------------------------------------------------------------------
# invoke — binary-dependent tests (skipped when binary not installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _AST_GREP_AVAILABLE, reason="ast-grep binary not installed")
def test_invoke_returns_invocation_result(tmp_path: Path) -> None:
    wrapper = AstGrepWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    assert isinstance(result, InvocationResult)


@pytest.mark.skipif(not _AST_GREP_AVAILABLE, reason="ast-grep binary not installed")
def test_invoke_duration_ms_is_positive(tmp_path: Path) -> None:
    wrapper = AstGrepWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    assert result.duration_ms > 0.0


@pytest.mark.skipif(not _AST_GREP_AVAILABLE, reason="ast-grep binary not installed")
def test_is_available_true_for_real_binary() -> None:
    wrapper = AstGrepWrapper()
    assert wrapper.is_available() is True
