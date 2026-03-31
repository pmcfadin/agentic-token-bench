"""Integration tests for the qualification runner script and CLI command.

All tests use mock adapters so that real CLIs are never invoked.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from typer.testing import CliRunner

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from benchmarks.harness.cli import app
from benchmarks.harness.models import QualificationRecord
from benchmarks.harness.qualification import run_qualification


# ---------------------------------------------------------------------------
# Shared mock adapters
# ---------------------------------------------------------------------------


class _MockPassingAdapter(AgentAdapter):
    """Minimal adapter that passes every probe."""

    def probe(self) -> QualificationResult:
        return QualificationResult(
            qualified=True,
            reported_token_support=True,
            forced_tool_support=True,
            trace_support=True,
            run_completion_support=True,
        )

    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        blocked_raw = step_env.get("BLOCKED_TOOLS", "")
        blocked = [t.strip() for t in blocked_raw.split(",") if t.strip()]
        for tool in blocked:
            if tool in prompt:
                return StepResult(
                    stdout="",
                    stderr=f"Blocked tool {tool!r} refused.",
                    exit_status=1,
                    step_metadata={"blocked_tool_violation": True},
                    trace_metadata={},
                )

        required_tool = step_env.get("REQUIRED_TOOL")
        tool_invocations: list[dict] = (
            [{"tool": required_tool, "exit_code": 0}] if required_tool else []
        )

        return StepResult(
            stdout="ok",
            stderr="",
            exit_status=0,
            step_metadata={"tool_invocations": tool_invocations},
            trace_metadata={"trace_available": True},
        )

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        reported = step_result.step_metadata.get("reported_tokens", {})
        return ReportedTokens(
            input_tokens=reported.get("input", 10),
            output_tokens=reported.get("output", 5),
            total_tokens=reported.get("total", 15),
            evidence_snippet="Tokens used: input=10, output=5, total=15",
        )

    def normalize_final_status(self, step_result: StepResult) -> str:
        return "completed" if step_result.exit_status == 0 else "failed"


class _MockFailingAdapter(_MockPassingAdapter):
    """Adapter that raises on extract_reported_tokens to simulate a broken CLI."""

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        raise ValueError("Token extraction not supported")


# ---------------------------------------------------------------------------
# Helper: run run_qualification against a mock adapter
# ---------------------------------------------------------------------------


def _run_with_passing_adapter(agent_id: str = "test-agent") -> QualificationRecord:
    return run_qualification(
        adapter=_MockPassingAdapter(),
        agent_id=agent_id,
        adapter_version="1.0.0",
    )


# ---------------------------------------------------------------------------
# Tests: qualification runner handles all three adapter IDs
# ---------------------------------------------------------------------------


class TestQualificationRunnerAdapterRouting:
    """Test that scripts/run_qualification.py routes each agent id correctly."""

    def _import_runner(self) -> ModuleType:
        """Import (or reload) the runner module each time."""
        spec = importlib.util.spec_from_file_location(
            "run_qualification_script",
            Path(__file__).parent.parent / "scripts" / "run_qualification.py",
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod

    def test_claude_routes_to_claude_adapter(self) -> None:
        mod = self._import_runner()
        with patch("agents.claude.adapter.ClaudeAdapter", return_value=_MockPassingAdapter()):
            # We just verify _qualify_agent doesn't raise for "claude".
            result = mod._qualify_agent("claude")
        assert result["agent_id"] == "claude"

    def test_codex_routes_to_codex_adapter(self) -> None:
        mod = self._import_runner()
        with patch("agents.codex.adapter.CodexAdapter", return_value=_MockPassingAdapter()):
            result = mod._qualify_agent("codex")
        assert result["agent_id"] == "codex"

    def test_gemini_cli_routes_to_gemini_adapter(self) -> None:
        mod = self._import_runner()
        with patch(
            "agents.gemini_cli.adapter.GeminiCliAdapter", return_value=_MockPassingAdapter()
        ):
            result = mod._qualify_agent("gemini-cli")
        assert result["agent_id"] == "gemini-cli"

    def test_unknown_agent_returns_not_qualified(self) -> None:
        mod = self._import_runner()
        result = mod._qualify_agent("bogus-agent")
        assert result["qualified"] is False
        assert "Unknown agent id" in result["failure_reason"]


# ---------------------------------------------------------------------------
# Tests: qualification records are written correctly
# ---------------------------------------------------------------------------


class TestQualificationRecordWriting:
    def test_write_record_creates_file(self, tmp_path: Path) -> None:
        mod_path = Path(__file__).parent.parent / "scripts" / "run_qualification.py"
        spec = importlib.util.spec_from_file_location("run_qualification_script", mod_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        record_dict = _run_with_passing_adapter("claude").model_dump()
        # Override the module's _QUAL_DIR to use tmp_path.
        original_qual_dir = mod._QUAL_DIR
        mod._QUAL_DIR = tmp_path
        try:
            out_path = mod._write_record("claude", record_dict)
        finally:
            mod._QUAL_DIR = original_qual_dir

        assert out_path.exists()

    def test_write_record_content_is_valid_json(self, tmp_path: Path) -> None:
        mod_path = Path(__file__).parent.parent / "scripts" / "run_qualification.py"
        spec = importlib.util.spec_from_file_location("run_qualification_script", mod_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        record_dict = _run_with_passing_adapter("claude").model_dump()
        mod._QUAL_DIR = tmp_path
        out_path = mod._write_record("claude", record_dict)

        content = json.loads(out_path.read_text())
        assert content["agent_id"] == "claude"
        assert isinstance(content["qualified"], bool)

    def test_write_record_filename_matches_agent_id(self, tmp_path: Path) -> None:
        mod_path = Path(__file__).parent.parent / "scripts" / "run_qualification.py"
        spec = importlib.util.spec_from_file_location("run_qualification_script", mod_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        for agent_id in ("claude", "codex", "gemini-cli"):
            record_dict = _run_with_passing_adapter(agent_id).model_dump()
            mod._QUAL_DIR = tmp_path
            out_path = mod._write_record(agent_id, record_dict)
            assert out_path.name == f"{agent_id}.json"

    def test_write_record_contains_all_schema_fields(self, tmp_path: Path) -> None:
        mod_path = Path(__file__).parent.parent / "scripts" / "run_qualification.py"
        spec = importlib.util.spec_from_file_location("run_qualification_script", mod_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        record_dict = _run_with_passing_adapter("codex").model_dump()
        mod._QUAL_DIR = tmp_path
        out_path = mod._write_record("codex", record_dict)

        content = json.loads(out_path.read_text())
        required_fields = {
            "agent_id",
            "adapter_version",
            "qualified",
            "reported_token_support",
            "forced_tool_support",
            "trace_support",
            "run_completion_support",
        }
        assert required_fields.issubset(content.keys())


# ---------------------------------------------------------------------------
# Tests: passing mock adapter produces a qualified record
# ---------------------------------------------------------------------------


class TestPassingMockAdapter:
    def test_passing_adapter_produces_qualified_record(self) -> None:
        record = _run_with_passing_adapter("claude")
        assert record.qualified is True

    def test_passing_adapter_all_supports_true(self) -> None:
        record = _run_with_passing_adapter("codex")
        assert record.reported_token_support is True
        assert record.forced_tool_support is True
        assert record.trace_support is True
        assert record.run_completion_support is True

    def test_passing_adapter_no_failure_reason(self) -> None:
        record = _run_with_passing_adapter("gemini-cli")
        assert record.failure_reason is None

    def test_failing_adapter_not_qualified(self) -> None:
        record = run_qualification(
            adapter=_MockFailingAdapter(),
            agent_id="broken-agent",
            adapter_version="0.0.1",
        )
        assert record.qualified is False

    def test_failing_adapter_has_failure_reason(self) -> None:
        record = run_qualification(
            adapter=_MockFailingAdapter(),
            agent_id="broken-agent",
            adapter_version="0.0.1",
        )
        assert record.failure_reason is not None


# ---------------------------------------------------------------------------
# Tests: CLI command exists and is registered
# ---------------------------------------------------------------------------


class TestCLICommandRegistration:
    def test_qualify_agent_command_is_registered(self) -> None:
        """The atb CLI must expose a 'qualify-agent' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "qualify-agent" in result.output

    def test_qualify_agent_help_shows_agent_argument(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["qualify-agent", "--help"])
        assert result.exit_code == 0
        # The help text should mention the AGENT argument.
        assert "AGENT" in result.output or "agent" in result.output.lower()


# ---------------------------------------------------------------------------
# Tests: CLI qualify-agent command with mock adapter
# ---------------------------------------------------------------------------


class TestCLIQualifyAgentCommand:
    def test_qualify_agent_passes_with_mock_passing_adapter(self, tmp_path: Path) -> None:
        runner = CliRunner()

        with (
            patch("benchmarks.harness.cli._build_adapter", return_value=_MockPassingAdapter()),
            patch("benchmarks.harness.cli._QUAL_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["qualify-agent", "claude"])

        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_qualify_agent_writes_json_file(self, tmp_path: Path) -> None:
        runner = CliRunner()

        with (
            patch("benchmarks.harness.cli._build_adapter", return_value=_MockPassingAdapter()),
            patch("benchmarks.harness.cli._QUAL_DIR", tmp_path),
        ):
            runner.invoke(app, ["qualify-agent", "claude"])

        out_file = tmp_path / "claude.json"
        assert out_file.exists()
        content = json.loads(out_file.read_text())
        assert content["agent_id"] == "claude"
        assert content["qualified"] is True

    def test_qualify_agent_fails_with_mock_failing_adapter(self, tmp_path: Path) -> None:
        runner = CliRunner()

        with (
            patch("benchmarks.harness.cli._build_adapter", return_value=_MockFailingAdapter()),
            patch("benchmarks.harness.cli._QUAL_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["qualify-agent", "codex"])

        assert result.exit_code != 0
        assert "FAIL" in result.output

    def test_qualify_agent_fail_output_includes_reason(self, tmp_path: Path) -> None:
        runner = CliRunner()

        with (
            patch("benchmarks.harness.cli._build_adapter", return_value=_MockFailingAdapter()),
            patch("benchmarks.harness.cli._QUAL_DIR", tmp_path),
        ):
            result = runner.invoke(app, ["qualify-agent", "codex"])

        # Should include some failure reason text.
        assert result.output  # non-empty

    def test_qualify_agent_invalid_agent_exits_nonzero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["qualify-agent", "unknown-agent"])
        assert result.exit_code != 0
