"""Tests for FastmodWrapper in tools/fastmod/wrapper.py."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.base import InvocationRecord, InvocationResult, ToolManifest, ToolWrapper
from tools.fastmod.wrapper import FastmodWrapper

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WRAPPER = FastmodWrapper()
_FASTMOD_AVAILABLE = _WRAPPER.is_available()

requires_fastmod = pytest.mark.skipif(
    not _FASTMOD_AVAILABLE,
    reason="fastmod binary not installed",
)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class TestFastmodManifest:
    def test_manifest_returns_tool_manifest(self) -> None:
        wrapper = FastmodWrapper()
        result = wrapper.manifest()
        assert isinstance(result, ToolManifest)

    def test_manifest_id(self) -> None:
        assert FastmodWrapper().manifest().id == "fastmod"

    def test_manifest_category(self) -> None:
        assert FastmodWrapper().manifest().category == "transformation"

    def test_manifest_risk_level(self) -> None:
        assert FastmodWrapper().manifest().risk_level == "medium"

    def test_manifest_waste_classes_contain_transformation_waste(self) -> None:
        assert "transformation_waste" in FastmodWrapper().manifest().waste_classes

    def test_manifest_is_consistent_across_calls(self) -> None:
        wrapper = FastmodWrapper()
        assert wrapper.manifest().id == wrapper.manifest().id


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    def test_is_available_returns_bool(self) -> None:
        wrapper = FastmodWrapper()
        assert isinstance(wrapper.is_available(), bool)

    def test_nonexistent_binary_is_not_available(self) -> None:
        wrapper = FastmodWrapper(binary_path="/no/such/binary/fastmod-xyz")
        assert wrapper.is_available() is False

    def test_default_binary_availability_matches_shutil(self) -> None:
        import shutil

        wrapper = FastmodWrapper()
        assert wrapper.is_available() == (shutil.which("fastmod") is not None)


# ---------------------------------------------------------------------------
# invoke  (requires fastmod)
# ---------------------------------------------------------------------------


class TestInvokeWithFastmod:
    @requires_fastmod
    def test_invoke_returns_invocation_result(self, tmp_path: Path) -> None:
        target = tmp_path / "hello.txt"
        target.write_text("hello world\n")
        wrapper = FastmodWrapper()
        result = wrapper.invoke(["hello", "goodbye", str(tmp_path)], cwd=tmp_path)
        assert isinstance(result, InvocationResult)

    @requires_fastmod
    def test_invoke_replaces_text_in_file(self, tmp_path: Path) -> None:
        target = tmp_path / "sample.txt"
        target.write_text("foo bar foo\n")
        wrapper = FastmodWrapper()
        wrapper.invoke(["--accept-all", "foo", "baz", str(tmp_path)], cwd=tmp_path)
        assert "baz" in target.read_text()

    @requires_fastmod
    def test_invoke_exit_status_zero_on_success(self, tmp_path: Path) -> None:
        target = tmp_path / "data.txt"
        target.write_text("alpha beta\n")
        wrapper = FastmodWrapper()
        result = wrapper.invoke(["alpha", "gamma", str(tmp_path)], cwd=tmp_path)
        assert result.exit_status == 0

    @requires_fastmod
    def test_invoke_duration_is_positive(self, tmp_path: Path) -> None:
        target = tmp_path / "data.txt"
        target.write_text("x\n")
        wrapper = FastmodWrapper()
        result = wrapper.invoke(["x", "y", str(tmp_path)], cwd=tmp_path)
        assert result.duration_ms > 0

    @requires_fastmod
    def test_invoke_accepts_env_override(self, tmp_path: Path) -> None:
        import os

        target = tmp_path / "env.txt"
        target.write_text("env_test\n")
        wrapper = FastmodWrapper()
        result = wrapper.invoke(
            ["env_test", "env_replaced", str(tmp_path)],
            cwd=tmp_path,
            env=os.environ.copy(),
        )
        assert isinstance(result, InvocationResult)

    def test_invoke_bad_binary_raises(self, tmp_path: Path) -> None:
        wrapper = FastmodWrapper(binary_path="/no/such/binary/fastmod-xyz")
        with pytest.raises(FileNotFoundError):
            wrapper.invoke(["a", "b"], cwd=tmp_path)


# ---------------------------------------------------------------------------
# record_invocation
# ---------------------------------------------------------------------------


class TestRecordInvocation:
    def _make_result(self) -> InvocationResult:
        return InvocationResult(
            stdout="",
            stderr="",
            exit_status=0,
            duration_ms=42.5,
        )

    def test_record_invocation_returns_invocation_record(self) -> None:
        wrapper = FastmodWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, ["a", "b"], step_id="s1", run_id="r1")
        assert isinstance(record, InvocationRecord)

    def test_record_invocation_tool_id_matches_manifest(self) -> None:
        wrapper = FastmodWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, ["a", "b"], step_id="s1", run_id="r1")
        assert record.tool_id == wrapper.manifest().id

    def test_record_invocation_step_id(self) -> None:
        wrapper = FastmodWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, [], step_id="step-42", run_id="run-1")
        assert record.step_id == "step-42"

    def test_record_invocation_run_id(self) -> None:
        wrapper = FastmodWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, [], step_id="s", run_id="run-abc")
        assert record.run_id == "run-abc"

    def test_record_invocation_exit_status_matches_result(self) -> None:
        wrapper = FastmodWrapper()
        result = InvocationResult(stdout="", stderr="", exit_status=1, duration_ms=5.0)
        record = wrapper.record_invocation(result, [], step_id="s", run_id="r")
        assert record.exit_status == 1

    def test_record_invocation_duration_matches_result(self) -> None:
        wrapper = FastmodWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, [], step_id="s", run_id="r")
        assert record.duration_ms == result.duration_ms

    def test_record_invocation_args_hash_is_hex_string(self) -> None:
        wrapper = FastmodWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, ["x", "y"], step_id="s", run_id="r")
        assert isinstance(record.args_hash, str)
        int(record.args_hash, 16)  # must be valid hex

    def test_record_invocation_args_hash_differs_for_different_args(self) -> None:
        wrapper = FastmodWrapper()
        result = self._make_result()
        r1 = wrapper.record_invocation(result, ["a", "b"], step_id="s", run_id="r")
        r2 = wrapper.record_invocation(result, ["c", "d"], step_id="s", run_id="r")
        assert r1.args_hash != r2.args_hash

    def test_record_invocation_timestamp_is_timezone_aware(self) -> None:
        wrapper = FastmodWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, [], step_id="s", run_id="r")
        assert record.timestamp.tzinfo is not None

    def test_record_invocation_timestamp_is_recent(self) -> None:
        wrapper = FastmodWrapper()
        result = self._make_result()
        before = datetime.now(tz=timezone.utc)
        record = wrapper.record_invocation(result, [], step_id="s", run_id="r")
        after = datetime.now(tz=timezone.utc)
        assert before <= record.timestamp <= after


# ---------------------------------------------------------------------------
# ToolWrapper ABC conformance
# ---------------------------------------------------------------------------


class TestToolWrapperConformance:
    def test_fastmod_wrapper_is_tool_wrapper(self) -> None:
        assert isinstance(FastmodWrapper(), ToolWrapper)

    def test_fastmod_wrapper_custom_binary_path(self) -> None:
        wrapper = FastmodWrapper(binary_path="/usr/local/bin/fastmod")
        assert wrapper._binary_path == "/usr/local/bin/fastmod"
