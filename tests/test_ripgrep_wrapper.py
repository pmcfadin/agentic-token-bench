"""Tests for RipgrepWrapper."""

import hashlib
import shutil
from pathlib import Path

import pytest

from tools.base import InvocationRecord, InvocationResult, ToolManifest
from tools.ripgrep.wrapper import RipgrepWrapper

_RG_AVAILABLE = shutil.which("rg") is not None

pytestmark = pytest.mark.skipif(not _RG_AVAILABLE, reason="rg binary not installed")


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def test_manifest_returns_tool_manifest() -> None:
    wrapper = RipgrepWrapper()
    m = wrapper.manifest()
    assert isinstance(m, ToolManifest)


def test_manifest_id_is_ripgrep() -> None:
    wrapper = RipgrepWrapper()
    assert wrapper.manifest().id == "ripgrep"


def test_manifest_category_is_discovery() -> None:
    wrapper = RipgrepWrapper()
    assert wrapper.manifest().category == "discovery"


def test_manifest_has_discovery_waste_class() -> None:
    wrapper = RipgrepWrapper()
    assert "discovery_waste" in wrapper.manifest().waste_classes


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


def test_is_available_true_for_real_binary() -> None:
    wrapper = RipgrepWrapper()
    assert wrapper.is_available() is True


def test_is_available_false_for_nonexistent_binary() -> None:
    wrapper = RipgrepWrapper(binary_path="definitely_not_a_real_binary_xyz")
    assert wrapper.is_available() is False


# ---------------------------------------------------------------------------
# invoke — happy path
# ---------------------------------------------------------------------------


def test_invoke_returns_invocation_result(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("hello world\nfoo bar\n")
    wrapper = RipgrepWrapper()
    result = wrapper.invoke(["hello", str(target)], cwd=tmp_path)
    assert isinstance(result, InvocationResult)


def test_invoke_finds_pattern(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("hello world\nfoo bar\n")
    wrapper = RipgrepWrapper()
    result = wrapper.invoke(["hello", str(target)], cwd=tmp_path)
    assert result.exit_status == 0
    assert "hello" in result.stdout


def test_invoke_captures_stdout(tmp_path: Path) -> None:
    target = tmp_path / "code.py"
    target.write_text("def my_function():\n    pass\n")
    wrapper = RipgrepWrapper()
    result = wrapper.invoke(["my_function", str(target)], cwd=tmp_path)
    assert "my_function" in result.stdout


def test_invoke_duration_ms_is_positive(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("test content\n")
    wrapper = RipgrepWrapper()
    result = wrapper.invoke(["test", str(target)], cwd=tmp_path)
    assert result.duration_ms > 0.0


# ---------------------------------------------------------------------------
# invoke — no matches (exit code 1 is normal for rg)
# ---------------------------------------------------------------------------


def test_invoke_no_matches_exit_code_one(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("hello world\n")
    wrapper = RipgrepWrapper()
    result = wrapper.invoke(["pattern_that_does_not_exist_xyz", str(target)], cwd=tmp_path)
    assert result.exit_status == 1


def test_invoke_no_matches_stdout_empty(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("hello world\n")
    wrapper = RipgrepWrapper()
    result = wrapper.invoke(["pattern_that_does_not_exist_xyz", str(target)], cwd=tmp_path)
    assert result.stdout == ""


def test_invoke_no_matches_returns_invocation_result(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_text("hello world\n")
    wrapper = RipgrepWrapper()
    result = wrapper.invoke(["pattern_that_does_not_exist_xyz", str(target)], cwd=tmp_path)
    assert isinstance(result, InvocationResult)


# ---------------------------------------------------------------------------
# record_invocation
# ---------------------------------------------------------------------------


def test_record_invocation_returns_invocation_record(tmp_path: Path) -> None:
    wrapper = RipgrepWrapper()
    target = tmp_path / "sample.txt"
    target.write_text("test\n")
    result = wrapper.invoke(["test", str(target)], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["test", str(target)], "step-1", "run-abc")
    assert isinstance(record, InvocationRecord)


def test_record_invocation_tool_id(tmp_path: Path) -> None:
    wrapper = RipgrepWrapper()
    target = tmp_path / "sample.txt"
    target.write_text("test\n")
    result = wrapper.invoke(["test", str(target)], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["test", str(target)], "step-1", "run-abc")
    assert record.tool_id == "ripgrep"


def test_record_invocation_step_and_run_id(tmp_path: Path) -> None:
    wrapper = RipgrepWrapper()
    target = tmp_path / "sample.txt"
    target.write_text("test\n")
    result = wrapper.invoke(["test", str(target)], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["test", str(target)], "step-99", "run-xyz")
    assert record.step_id == "step-99"
    assert record.run_id == "run-xyz"


def test_record_invocation_exit_status_matches_result(tmp_path: Path) -> None:
    wrapper = RipgrepWrapper()
    target = tmp_path / "sample.txt"
    target.write_text("test\n")
    result = wrapper.invoke(["test", str(target)], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["test", str(target)], "s", "r")
    assert record.exit_status == result.exit_status


def test_record_invocation_duration_matches_result(tmp_path: Path) -> None:
    wrapper = RipgrepWrapper()
    target = tmp_path / "sample.txt"
    target.write_text("test\n")
    result = wrapper.invoke(["test", str(target)], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["test", str(target)], "s", "r")
    assert record.duration_ms == result.duration_ms


def test_record_invocation_args_hash_is_sha256(tmp_path: Path) -> None:
    wrapper = RipgrepWrapper()
    target = tmp_path / "sample.txt"
    target.write_text("test\n")
    args = ["test", str(target)]
    result = wrapper.invoke(args, cwd=tmp_path)
    record = wrapper.record_invocation(result, args, "s", "r")
    expected_hash = hashlib.sha256(" ".join(args).encode()).hexdigest()
    assert record.args_hash == expected_hash


def test_record_invocation_timestamp_is_timezone_aware(tmp_path: Path) -> None:
    wrapper = RipgrepWrapper()
    target = tmp_path / "sample.txt"
    target.write_text("test\n")
    result = wrapper.invoke(["test", str(target)], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["test", str(target)], "s", "r")
    assert record.timestamp.tzinfo is not None
