"""Tests for RtkWrapper."""

import hashlib
import shutil
from pathlib import Path

import pytest

from tools.base import InvocationRecord, InvocationResult, ToolManifest
from tools.rtk.wrapper import RtkWrapper

_RTK_AVAILABLE = shutil.which("rtk") is not None


# ---------------------------------------------------------------------------
# Manifest — these tests do not require the binary
# ---------------------------------------------------------------------------


def test_manifest_returns_tool_manifest() -> None:
    wrapper = RtkWrapper()
    m = wrapper.manifest()
    assert isinstance(m, ToolManifest)


def test_manifest_id_is_rtk() -> None:
    wrapper = RtkWrapper()
    assert wrapper.manifest().id == "rtk"


def test_manifest_category_is_output_compression() -> None:
    wrapper = RtkWrapper()
    assert wrapper.manifest().category == "output_compression"


def test_manifest_has_execution_output_waste_class() -> None:
    wrapper = RtkWrapper()
    assert "execution_output_waste" in wrapper.manifest().waste_classes


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


def test_is_available_false_for_nonexistent_binary() -> None:
    wrapper = RtkWrapper(binary_path="definitely_not_a_real_binary_xyz")
    assert wrapper.is_available() is False


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_is_available_true_for_real_binary() -> None:
    wrapper = RtkWrapper()
    assert wrapper.is_available() is True


# ---------------------------------------------------------------------------
# invoke — requires rtk binary
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_invoke_returns_invocation_result(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    assert isinstance(result, InvocationResult)


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_invoke_version_exit_status_zero(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    assert result.exit_status == 0


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_invoke_duration_ms_is_positive(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    assert result.duration_ms > 0.0


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_invoke_wraps_subcommand(tmp_path: Path) -> None:
    """rtk wraps other commands — args like ['gain'] become 'rtk gain'."""
    wrapper = RtkWrapper()
    result = wrapper.invoke(["gain"], cwd=tmp_path)
    assert isinstance(result, InvocationResult)


# ---------------------------------------------------------------------------
# record_invocation — requires rtk binary for a real result
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_record_invocation_returns_invocation_record(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["--version"], "step-1", "run-abc")
    assert isinstance(record, InvocationRecord)


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_record_invocation_tool_id(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["--version"], "step-1", "run-abc")
    assert record.tool_id == "rtk"


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_record_invocation_step_and_run_id(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["--version"], "step-99", "run-xyz")
    assert record.step_id == "step-99"
    assert record.run_id == "run-xyz"


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_record_invocation_exit_status_matches_result(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["--version"], "s", "r")
    assert record.exit_status == result.exit_status


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_record_invocation_duration_matches_result(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["--version"], "s", "r")
    assert record.duration_ms == result.duration_ms


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_record_invocation_args_hash_is_sha256(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    args = ["--version"]
    result = wrapper.invoke(args, cwd=tmp_path)
    record = wrapper.record_invocation(result, args, "s", "r")
    expected_hash = hashlib.sha256(" ".join(args).encode()).hexdigest()
    assert record.args_hash == expected_hash


@pytest.mark.skipif(not _RTK_AVAILABLE, reason="rtk binary not installed")
def test_record_invocation_timestamp_is_timezone_aware(tmp_path: Path) -> None:
    wrapper = RtkWrapper()
    result = wrapper.invoke(["--version"], cwd=tmp_path)
    record = wrapper.record_invocation(result, ["--version"], "s", "r")
    assert record.timestamp.tzinfo is not None
