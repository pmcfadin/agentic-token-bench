"""Tests for CombyWrapper."""

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.base import InvocationRecord, InvocationResult, ToolManifest, ToolWrapper
from tools.comby.wrapper import CombyWrapper

_COMBY_AVAILABLE = shutil.which("comby") is not None


# ---------------------------------------------------------------------------
# Manifest — no binary needed
# ---------------------------------------------------------------------------


def test_manifest_returns_tool_manifest() -> None:
    wrapper = CombyWrapper()
    m = wrapper.manifest()
    assert isinstance(m, ToolManifest)


def test_manifest_id_is_comby() -> None:
    wrapper = CombyWrapper()
    assert wrapper.manifest().id == "comby"


def test_manifest_name_is_comby() -> None:
    wrapper = CombyWrapper()
    assert wrapper.manifest().name == "Comby"


def test_manifest_category_is_transformation() -> None:
    wrapper = CombyWrapper()
    assert wrapper.manifest().category == "transformation"


def test_manifest_has_transformation_waste_class() -> None:
    wrapper = CombyWrapper()
    assert "transformation_waste" in wrapper.manifest().waste_classes


def test_manifest_risk_level_is_medium() -> None:
    wrapper = CombyWrapper()
    assert wrapper.manifest().risk_level == "medium"


# ---------------------------------------------------------------------------
# is_available — no binary needed
# ---------------------------------------------------------------------------


def test_is_available_false_for_nonexistent_binary() -> None:
    wrapper = CombyWrapper(binary_path="definitely_not_a_real_binary_xyz")
    assert wrapper.is_available() is False


def test_is_available_reflects_shutil_which() -> None:
    wrapper = CombyWrapper()
    assert wrapper.is_available() is _COMBY_AVAILABLE


@pytest.mark.skipif(_COMBY_AVAILABLE, reason="comby is installed; testing unavailable path only")
def test_is_available_false_when_binary_absent() -> None:
    wrapper = CombyWrapper()
    assert wrapper.is_available() is False


# ---------------------------------------------------------------------------
# ABC conformance — no binary needed
# ---------------------------------------------------------------------------


def test_comby_wrapper_is_subclass_of_tool_wrapper() -> None:
    assert issubclass(CombyWrapper, ToolWrapper)


def test_comby_wrapper_is_instantiable() -> None:
    wrapper = CombyWrapper()
    assert wrapper is not None


def test_comby_wrapper_implements_all_abstract_methods() -> None:
    wrapper = CombyWrapper()
    assert callable(wrapper.manifest)
    assert callable(wrapper.invoke)
    assert callable(wrapper.record_invocation)
    assert callable(wrapper.is_available)


# ---------------------------------------------------------------------------
# record_invocation — no binary needed
# ---------------------------------------------------------------------------


def _make_result(exit_status: int = 0, duration_ms: float = 42.0) -> InvocationResult:
    return InvocationResult(
        stdout="output",
        stderr="",
        exit_status=exit_status,
        duration_ms=duration_ms,
    )


def test_record_invocation_returns_invocation_record() -> None:
    wrapper = CombyWrapper()
    result = _make_result()
    record = wrapper.record_invocation(result, ["match", "replace", "file.py"], "step-1", "run-abc")
    assert isinstance(record, InvocationRecord)


def test_record_invocation_tool_id_is_comby() -> None:
    wrapper = CombyWrapper()
    result = _make_result()
    record = wrapper.record_invocation(result, ["-match", "foo"], "step-1", "run-abc")
    assert record.tool_id == "comby"


def test_record_invocation_step_and_run_id() -> None:
    wrapper = CombyWrapper()
    result = _make_result()
    record = wrapper.record_invocation(result, ["foo", "bar"], "step-99", "run-xyz")
    assert record.step_id == "step-99"
    assert record.run_id == "run-xyz"


def test_record_invocation_exit_status_matches_result() -> None:
    wrapper = CombyWrapper()
    result = _make_result(exit_status=1)
    record = wrapper.record_invocation(result, ["foo"], "s", "r")
    assert record.exit_status == 1


def test_record_invocation_duration_matches_result() -> None:
    wrapper = CombyWrapper()
    result = _make_result(duration_ms=99.5)
    record = wrapper.record_invocation(result, ["foo"], "s", "r")
    assert record.duration_ms == 99.5


def test_record_invocation_args_hash_is_sha256() -> None:
    wrapper = CombyWrapper()
    args = ["match_template", "rewrite_template", "file.py"]
    result = _make_result()
    record = wrapper.record_invocation(result, args, "s", "r")
    expected_hash = hashlib.sha256(" ".join(args).encode()).hexdigest()
    assert record.args_hash == expected_hash


def test_record_invocation_timestamp_is_timezone_aware() -> None:
    wrapper = CombyWrapper()
    result = _make_result()
    record = wrapper.record_invocation(result, ["foo"], "s", "r")
    assert record.timestamp.tzinfo is not None


def test_record_invocation_timestamp_is_utc() -> None:
    wrapper = CombyWrapper()
    result = _make_result()
    before = datetime.now(tz=timezone.utc)
    record = wrapper.record_invocation(result, ["foo"], "s", "r")
    after = datetime.now(tz=timezone.utc)
    assert before <= record.timestamp <= after


# ---------------------------------------------------------------------------
# invoke — binary-dependent tests (skipped when comby not installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _COMBY_AVAILABLE, reason="comby binary not installed")
def test_invoke_returns_invocation_result(tmp_path: Path) -> None:
    wrapper = CombyWrapper()
    result = wrapper.invoke(["--help"], cwd=tmp_path)
    assert isinstance(result, InvocationResult)


@pytest.mark.skipif(not _COMBY_AVAILABLE, reason="comby binary not installed")
def test_invoke_duration_ms_is_positive(tmp_path: Path) -> None:
    wrapper = CombyWrapper()
    result = wrapper.invoke(["--help"], cwd=tmp_path)
    assert result.duration_ms > 0.0
