"""Tests for QmdWrapper in tools/qmd/wrapper.py."""

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.base import InvocationRecord, InvocationResult, ToolManifest, ToolWrapper
from tools.qmd.wrapper import QmdWrapper

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WRAPPER = QmdWrapper()
_QMD_AVAILABLE = _WRAPPER.is_available()

requires_qmd = pytest.mark.skipif(
    not _QMD_AVAILABLE,
    reason="qmd binary not installed",
)


# ---------------------------------------------------------------------------
# Manifest  (never requires the binary)
# ---------------------------------------------------------------------------


class TestQmdManifest:
    def test_manifest_returns_tool_manifest(self) -> None:
        wrapper = QmdWrapper()
        result = wrapper.manifest()
        assert isinstance(result, ToolManifest)

    def test_manifest_id(self) -> None:
        assert QmdWrapper().manifest().id == "qmd"

    def test_manifest_category(self) -> None:
        assert QmdWrapper().manifest().category == "retrieval"

    def test_manifest_risk_level(self) -> None:
        assert QmdWrapper().manifest().risk_level == "low"

    def test_manifest_waste_classes_contain_retrieval_waste(self) -> None:
        assert "retrieval_waste" in QmdWrapper().manifest().waste_classes

    def test_manifest_is_consistent_across_calls(self) -> None:
        wrapper = QmdWrapper()
        assert wrapper.manifest().id == wrapper.manifest().id


# ---------------------------------------------------------------------------
# is_available  (never requires the binary)
# ---------------------------------------------------------------------------


class TestIsAvailable:
    def test_is_available_returns_bool(self) -> None:
        wrapper = QmdWrapper()
        assert isinstance(wrapper.is_available(), bool)

    def test_nonexistent_binary_is_not_available(self) -> None:
        wrapper = QmdWrapper(binary_path="/no/such/binary/qmd-xyz")
        assert wrapper.is_available() is False

    def test_default_binary_availability_matches_shutil(self) -> None:
        wrapper = QmdWrapper()
        assert wrapper.is_available() == (shutil.which("qmd") is not None)


# ---------------------------------------------------------------------------
# invoke  (requires qmd)
# ---------------------------------------------------------------------------


class TestInvokeWithQmd:
    @requires_qmd
    def test_invoke_returns_invocation_result(self, tmp_path: Path) -> None:
        wrapper = QmdWrapper()
        result = wrapper.invoke(["--version"], cwd=tmp_path)
        assert isinstance(result, InvocationResult)

    @requires_qmd
    def test_invoke_exit_status_is_int(self, tmp_path: Path) -> None:
        wrapper = QmdWrapper()
        result = wrapper.invoke(["--version"], cwd=tmp_path)
        assert isinstance(result.exit_status, int)

    @requires_qmd
    def test_invoke_duration_is_positive(self, tmp_path: Path) -> None:
        wrapper = QmdWrapper()
        result = wrapper.invoke(["--version"], cwd=tmp_path)
        assert result.duration_ms > 0

    @requires_qmd
    def test_invoke_accepts_env_override(self, tmp_path: Path) -> None:
        import os

        wrapper = QmdWrapper()
        result = wrapper.invoke(
            ["--version"],
            cwd=tmp_path,
            env=os.environ.copy(),
        )
        assert isinstance(result, InvocationResult)

    def test_invoke_bad_binary_raises(self, tmp_path: Path) -> None:
        wrapper = QmdWrapper(binary_path="/no/such/binary/qmd-xyz")
        with pytest.raises(FileNotFoundError):
            wrapper.invoke(["--version"], cwd=tmp_path)


# ---------------------------------------------------------------------------
# record_invocation  (never requires the binary)
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
        wrapper = QmdWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, ["a", "b"], step_id="s1", run_id="r1")
        assert isinstance(record, InvocationRecord)

    def test_record_invocation_tool_id_matches_manifest(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, ["a", "b"], step_id="s1", run_id="r1")
        assert record.tool_id == wrapper.manifest().id

    def test_record_invocation_tool_id_is_qmd(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, [], step_id="s", run_id="r")
        assert record.tool_id == "qmd"

    def test_record_invocation_step_id(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, [], step_id="step-42", run_id="run-1")
        assert record.step_id == "step-42"

    def test_record_invocation_run_id(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, [], step_id="s", run_id="run-abc")
        assert record.run_id == "run-abc"

    def test_record_invocation_exit_status_matches_result(self) -> None:
        wrapper = QmdWrapper()
        result = InvocationResult(stdout="", stderr="", exit_status=1, duration_ms=5.0)
        record = wrapper.record_invocation(result, [], step_id="s", run_id="r")
        assert record.exit_status == 1

    def test_record_invocation_duration_matches_result(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, [], step_id="s", run_id="r")
        assert record.duration_ms == result.duration_ms

    def test_record_invocation_args_hash_is_sha256(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        args = ["x", "y"]
        record = wrapper.record_invocation(result, args, step_id="s", run_id="r")
        expected = hashlib.sha256(" ".join(args).encode()).hexdigest()
        assert record.args_hash == expected

    def test_record_invocation_args_hash_is_hex_string(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, ["x", "y"], step_id="s", run_id="r")
        assert isinstance(record.args_hash, str)
        int(record.args_hash, 16)  # must be valid hex

    def test_record_invocation_args_hash_differs_for_different_args(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        r1 = wrapper.record_invocation(result, ["a", "b"], step_id="s", run_id="r")
        r2 = wrapper.record_invocation(result, ["c", "d"], step_id="s", run_id="r")
        assert r1.args_hash != r2.args_hash

    def test_record_invocation_timestamp_is_timezone_aware(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        record = wrapper.record_invocation(result, [], step_id="s", run_id="r")
        assert record.timestamp.tzinfo is not None

    def test_record_invocation_timestamp_is_recent(self) -> None:
        wrapper = QmdWrapper()
        result = self._make_result()
        before = datetime.now(tz=timezone.utc)
        record = wrapper.record_invocation(result, [], step_id="s", run_id="r")
        after = datetime.now(tz=timezone.utc)
        assert before <= record.timestamp <= after


# ---------------------------------------------------------------------------
# ToolWrapper ABC conformance
# ---------------------------------------------------------------------------


class TestToolWrapperConformance:
    def test_qmd_wrapper_is_tool_wrapper(self) -> None:
        assert isinstance(QmdWrapper(), ToolWrapper)

    def test_qmd_wrapper_custom_binary_path(self) -> None:
        wrapper = QmdWrapper(binary_path="/usr/local/bin/qmd")
        assert wrapper._binary_path == "/usr/local/bin/qmd"
