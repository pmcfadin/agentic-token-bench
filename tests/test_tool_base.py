"""Tests for ToolWrapper ABC and supporting dataclasses in tools.base."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.base import (
    InvocationRecord,
    InvocationResult,
    ToolManifest,
    ToolWrapper,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_SAMPLE_MANIFEST = ToolManifest(
    id="mock-tool",
    name="Mock Tool",
    version="1.0.0",
    category="discovery",
    description="A mock tool for testing purposes.",
    supported_languages=["python", "rust"],
    waste_classes=["discovery_waste"],
    dependencies=[],
    risk_level="low",
)


class MockToolWrapper(ToolWrapper):
    """Minimal concrete implementation used only in tests."""

    def manifest(self) -> ToolManifest:
        return _SAMPLE_MANIFEST

    def invoke(
        self,
        args: list[str],
        cwd: Path,
        env: dict[str, str] | None = None,
        timeout: float = 120.0,
    ) -> InvocationResult:
        return InvocationResult(
            stdout="mock output",
            stderr="",
            exit_status=0,
            duration_ms=12.5,
        )

    def record_invocation(
        self,
        result: InvocationResult,
        args: list[str],
        step_id: str,
        run_id: str,
    ) -> InvocationRecord:
        args_hash = hashlib.sha256(str(args).encode()).hexdigest()[:16]
        return InvocationRecord(
            tool_id=self.manifest().id,
            timestamp=datetime.now(tz=timezone.utc),
            args_hash=args_hash,
            exit_status=result.exit_status,
            duration_ms=result.duration_ms,
            step_id=step_id,
            run_id=run_id,
        )


# ---------------------------------------------------------------------------
# ToolWrapper abstract-class contract
# ---------------------------------------------------------------------------


class TestToolWrapperIsAbstract:
    def test_cannot_instantiate_tool_wrapper_directly(self) -> None:
        """ToolWrapper must not be instantiable — it is abstract."""
        with pytest.raises(TypeError):
            ToolWrapper()  # type: ignore[abstract]

    def test_subclass_missing_manifest_raises_type_error(self) -> None:
        """A subclass that omits manifest() cannot be instantiated."""

        class NoManifest(ToolWrapper):
            def invoke(self, args, cwd, env=None, timeout=120.0):  # type: ignore[override]
                return InvocationResult("", "", 0, 0.0)

            def record_invocation(self, result, args, step_id, run_id):  # type: ignore[override]
                return InvocationRecord("", datetime.now(), "", 0, 0.0, "", "")

        with pytest.raises(TypeError):
            NoManifest()

    def test_subclass_missing_invoke_raises_type_error(self) -> None:
        """A subclass that omits invoke() cannot be instantiated."""

        class NoInvoke(ToolWrapper):
            def manifest(self):  # type: ignore[override]
                return _SAMPLE_MANIFEST

            def record_invocation(self, result, args, step_id, run_id):  # type: ignore[override]
                return InvocationRecord("", datetime.now(), "", 0, 0.0, "", "")

        with pytest.raises(TypeError):
            NoInvoke()

    def test_subclass_missing_record_invocation_raises_type_error(self) -> None:
        """A subclass that omits record_invocation() cannot be instantiated."""

        class NoRecord(ToolWrapper):
            def manifest(self):  # type: ignore[override]
                return _SAMPLE_MANIFEST

            def invoke(self, args, cwd, env=None, timeout=120.0):  # type: ignore[override]
                return InvocationResult("", "", 0, 0.0)

        with pytest.raises(TypeError):
            NoRecord()


# ---------------------------------------------------------------------------
# MockToolWrapper — concrete subclass behaviour
# ---------------------------------------------------------------------------


class TestMockToolWrapper:
    def setup_method(self) -> None:
        self.wrapper = MockToolWrapper()

    def test_can_be_instantiated(self) -> None:
        """A fully-implemented subclass must instantiate without error."""
        assert isinstance(self.wrapper, ToolWrapper)

    def test_manifest_returns_tool_manifest(self) -> None:
        result = self.wrapper.manifest()
        assert isinstance(result, ToolManifest)
        assert result.id == "mock-tool"

    def test_invoke_returns_invocation_result(self, tmp_path: Path) -> None:
        result = self.wrapper.invoke(["--help"], cwd=tmp_path)
        assert isinstance(result, InvocationResult)
        assert result.exit_status == 0
        assert result.stdout == "mock output"

    def test_invoke_accepts_env_and_timeout(self, tmp_path: Path) -> None:
        result = self.wrapper.invoke(
            ["run"], cwd=tmp_path, env={"FOO": "bar"}, timeout=30.0
        )
        assert result.exit_status == 0

    def test_record_invocation_returns_invocation_record(self, tmp_path: Path) -> None:
        result = self.wrapper.invoke(["check"], cwd=tmp_path)
        record = self.wrapper.record_invocation(
            result, ["check"], step_id="step-1", run_id="run-abc"
        )
        assert isinstance(record, InvocationRecord)
        assert record.tool_id == "mock-tool"
        assert record.step_id == "step-1"
        assert record.run_id == "run-abc"
        assert record.exit_status == 0

    def test_record_invocation_duration_matches_result(self, tmp_path: Path) -> None:
        result = self.wrapper.invoke(["scan"], cwd=tmp_path)
        record = self.wrapper.record_invocation(
            result, ["scan"], step_id="s", run_id="r"
        )
        assert record.duration_ms == result.duration_ms


# ---------------------------------------------------------------------------
# ToolManifest dataclass
# ---------------------------------------------------------------------------


class TestToolManifest:
    def test_required_fields(self) -> None:
        m = ToolManifest(
            id="t", name="T", version="0.1", category="discovery", description="desc"
        )
        assert m.id == "t"
        assert m.name == "T"
        assert m.version == "0.1"
        assert m.category == "discovery"
        assert m.description == "desc"

    def test_optional_list_fields_default_empty(self) -> None:
        m = ToolManifest(
            id="t", name="T", version="0.1", category="retrieval", description="d"
        )
        assert m.supported_languages == []
        assert m.waste_classes == []
        assert m.dependencies == []

    def test_risk_level_defaults_to_low(self) -> None:
        m = ToolManifest(
            id="t", name="T", version="0.1", category="retrieval", description="d"
        )
        assert m.risk_level == "low"

    def test_optional_fields_accept_values(self) -> None:
        m = ToolManifest(
            id="t",
            name="T",
            version="1.0",
            category="transformation",
            description="d",
            supported_languages=["python"],
            waste_classes=["transformation_waste"],
            dependencies=["libfoo"],
            risk_level="high",
        )
        assert m.supported_languages == ["python"]
        assert m.waste_classes == ["transformation_waste"]
        assert m.dependencies == ["libfoo"]
        assert m.risk_level == "high"


# ---------------------------------------------------------------------------
# InvocationRecord dataclass
# ---------------------------------------------------------------------------


class TestInvocationRecord:
    def test_construction(self) -> None:
        ts = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
        rec = InvocationRecord(
            tool_id="ripgrep",
            timestamp=ts,
            args_hash="deadbeef",
            exit_status=0,
            duration_ms=5.3,
            step_id="step-42",
            run_id="run-001",
        )
        assert rec.tool_id == "ripgrep"
        assert rec.timestamp == ts
        assert rec.args_hash == "deadbeef"
        assert rec.exit_status == 0
        assert rec.duration_ms == 5.3
        assert rec.step_id == "step-42"
        assert rec.run_id == "run-001"

    def test_non_zero_exit_status(self) -> None:
        rec = InvocationRecord(
            tool_id="t",
            timestamp=datetime.now(tz=timezone.utc),
            args_hash="abc",
            exit_status=1,
            duration_ms=0.0,
            step_id="s",
            run_id="r",
        )
        assert rec.exit_status == 1


# ---------------------------------------------------------------------------
# InvocationResult dataclass
# ---------------------------------------------------------------------------


class TestInvocationResult:
    def test_construction(self) -> None:
        res = InvocationResult(
            stdout="hello", stderr="warn", exit_status=0, duration_ms=42.0
        )
        assert res.stdout == "hello"
        assert res.stderr == "warn"
        assert res.exit_status == 0
        assert res.duration_ms == 42.0

    def test_empty_output_fields(self) -> None:
        res = InvocationResult(stdout="", stderr="", exit_status=0, duration_ms=0.0)
        assert res.stdout == ""
        assert res.stderr == ""

    def test_non_zero_exit_status(self) -> None:
        res = InvocationResult(stdout="", stderr="err", exit_status=2, duration_ms=1.0)
        assert res.exit_status == 2
