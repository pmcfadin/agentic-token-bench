"""Tests for benchmarks.harness.step_executor."""

from __future__ import annotations

import os
from pathlib import Path

from benchmarks.harness.models import CompletionContract, TaskStep
from benchmarks.harness.step_executor import (
    StepExecutor,
    create_step_environment,
    validate_step_enforcement,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step(
    step_id: str = "discover",
    required_tool: str | None = "ripgrep",
    allowed_tools: list[str] | None = None,
    blocked_tools: list[str] | None = None,
) -> TaskStep:
    return TaskStep(
        step_id=step_id,
        name=step_id,
        objective="test objective",
        required_tool=required_tool,
        allowed_tools=allowed_tools if allowed_tools is not None else ["ripgrep"],
        blocked_tools=blocked_tools if blocked_tools is not None else ["fastmod", "comby"],
        completion_contract=CompletionContract(kind="structured_answer", fields=["result"]),
        artifact_requirements=["step_trace"],
    )


def _make_wrappers(tmp_path: Path, names: list[str]) -> dict[str, Path]:
    """Create dummy wrapper binaries and return the tool_wrappers mapping."""
    wrappers: dict[str, Path] = {}
    for name in names:
        tool_dir = tmp_path / name
        tool_dir.mkdir(parents=True, exist_ok=True)
        binary = tool_dir / name
        binary.write_text("#!/bin/sh\nexec $0_real \"$@\"\n")
        binary.chmod(0o755)
        wrappers[name] = binary
    return wrappers


# ---------------------------------------------------------------------------
# create_step_environment — PATH construction
# ---------------------------------------------------------------------------


class TestCreateStepEnvironmentPath:
    def test_allowed_tool_wrapper_dir_in_path(self, tmp_path: Path) -> None:
        """Wrapper directory for an allowed tool appears in PATH."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep"])
        step = _make_step(allowed_tools=["ripgrep"])
        env = create_step_environment(step, wrappers, "tool_variant")
        path_dirs = env["PATH"].split(os.pathsep)
        expected_dir = str(wrappers["ripgrep"].parent)
        assert expected_dir in path_dirs

    def test_non_allowed_tool_not_in_path(self, tmp_path: Path) -> None:
        """Wrapper directory for a tool NOT in allowed_tools is absent from PATH."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep", "fastmod"])
        step = _make_step(allowed_tools=["ripgrep"], blocked_tools=["fastmod"])
        env = create_step_environment(step, wrappers, "tool_variant")
        path_dirs = env["PATH"].split(os.pathsep)
        fastmod_dir = str(wrappers["fastmod"].parent)
        assert fastmod_dir not in path_dirs

    def test_system_dirs_always_present(self, tmp_path: Path) -> None:
        """Essential system directories are included so the shell stays functional."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep"])
        step = _make_step(allowed_tools=["ripgrep"])
        env = create_step_environment(
            step, wrappers, "tool_variant", base_env={"PATH": ""}
        )
        path_dirs = env["PATH"].split(os.pathsep)
        # At least one essential system dir should be present.
        assert any(d in path_dirs for d in ["/bin", "/usr/bin", "/usr/local/bin"])

    def test_only_allowed_wrappers_from_tool_set(self, tmp_path: Path) -> None:
        """PATH includes exactly the allowed wrapper dirs among the known tools."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep", "fastmod", "comby"])
        step = _make_step(
            allowed_tools=["ripgrep", "fastmod"],
            blocked_tools=["comby"],
        )
        env = create_step_environment(step, wrappers, "tool_variant")
        path_dirs = env["PATH"].split(os.pathsep)
        assert str(wrappers["ripgrep"].parent) in path_dirs
        assert str(wrappers["fastmod"].parent) in path_dirs
        assert str(wrappers["comby"].parent) not in path_dirs

    def test_non_path_env_vars_are_preserved(self, tmp_path: Path) -> None:
        """Environment variables other than PATH are passed through unchanged."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep"])
        step = _make_step(allowed_tools=["ripgrep"])
        base = {"PATH": "/usr/bin", "HOME": "/home/runner", "LANG": "en_US.UTF-8"}
        env = create_step_environment(step, wrappers, "tool_variant", base_env=base)
        assert env["HOME"] == "/home/runner"
        assert env["LANG"] == "en_US.UTF-8"


# ---------------------------------------------------------------------------
# create_step_environment — baseline variant removes tool under test
# ---------------------------------------------------------------------------


class TestCreateStepEnvironmentBaseline:
    def test_baseline_removes_required_tool(self, tmp_path: Path) -> None:
        """In baseline variant the required_tool wrapper dir is absent from PATH."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep"])
        step = _make_step(required_tool="ripgrep", allowed_tools=["ripgrep"])
        env = create_step_environment(step, wrappers, "baseline")
        path_dirs = env["PATH"].split(os.pathsep)
        assert str(wrappers["ripgrep"].parent) not in path_dirs

    def test_baseline_keeps_other_allowed_tools(self, tmp_path: Path) -> None:
        """In baseline variant, other allowed tools (not the required one) remain."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep", "fastmod"])
        step = _make_step(
            required_tool="ripgrep",
            allowed_tools=["ripgrep", "fastmod"],
            blocked_tools=[],
        )
        env = create_step_environment(step, wrappers, "baseline")
        path_dirs = env["PATH"].split(os.pathsep)
        assert str(wrappers["ripgrep"].parent) not in path_dirs
        assert str(wrappers["fastmod"].parent) in path_dirs

    def test_tool_variant_keeps_required_tool(self, tmp_path: Path) -> None:
        """In tool_variant the required_tool wrapper dir IS in PATH."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep"])
        step = _make_step(required_tool="ripgrep", allowed_tools=["ripgrep"])
        env = create_step_environment(step, wrappers, "tool_variant")
        path_dirs = env["PATH"].split(os.pathsep)
        assert str(wrappers["ripgrep"].parent) in path_dirs

    def test_baseline_with_no_required_tool(self, tmp_path: Path) -> None:
        """Baseline variant with required_tool=None keeps all allowed tools."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep"])
        step = _make_step(required_tool=None, allowed_tools=["ripgrep"])
        env = create_step_environment(step, wrappers, "baseline")
        path_dirs = env["PATH"].split(os.pathsep)
        assert str(wrappers["ripgrep"].parent) in path_dirs


# ---------------------------------------------------------------------------
# validate_step_enforcement
# ---------------------------------------------------------------------------


class TestValidateStepEnforcement:
    def test_passes_when_required_tool_used(self) -> None:
        """Validation passes when the required tool appears in invocations."""
        step = _make_step(required_tool="ripgrep", blocked_tools=[])
        invocations = [{"tool_id": "ripgrep", "exit_status": 0}]
        valid, reason = validate_step_enforcement(step, invocations, "tool_variant")
        assert valid is True
        assert reason == ""

    def test_fails_when_required_tool_missing(self) -> None:
        """Validation fails when required tool is absent from invocations."""
        step = _make_step(required_tool="ripgrep", blocked_tools=[])
        invocations: list[dict] = []
        valid, reason = validate_step_enforcement(step, invocations, "tool_variant")
        assert valid is False
        assert "ripgrep" in reason

    def test_fails_when_blocked_tool_used(self) -> None:
        """Validation fails when a blocked tool appears in invocations."""
        step = _make_step(required_tool="ripgrep", blocked_tools=["fastmod"])
        invocations = [
            {"tool_id": "ripgrep", "exit_status": 0},
            {"tool_id": "fastmod", "exit_status": 0},
        ]
        valid, reason = validate_step_enforcement(step, invocations, "tool_variant")
        assert valid is False
        assert "fastmod" in reason

    def test_baseline_does_not_require_required_tool(self) -> None:
        """In baseline variant the required_tool need not appear."""
        step = _make_step(required_tool="ripgrep", blocked_tools=[])
        invocations: list[dict] = []
        valid, reason = validate_step_enforcement(step, invocations, "baseline")
        assert valid is True
        assert reason == ""

    def test_passes_with_no_required_tool_and_no_blocked_usage(self) -> None:
        """Passes when required_tool is None and no blocked tools were called."""
        step = _make_step(required_tool=None, blocked_tools=["fastmod"])
        invocations = [{"tool_id": "ripgrep", "exit_status": 0}]
        valid, reason = validate_step_enforcement(step, invocations, "tool_variant")
        assert valid is True

    def test_fails_with_no_required_tool_but_blocked_tool_used(self) -> None:
        """Fails when a blocked tool appears even if required_tool is None."""
        step = _make_step(required_tool=None, blocked_tools=["fastmod"])
        invocations = [{"tool_id": "fastmod", "exit_status": 0}]
        valid, reason = validate_step_enforcement(step, invocations, "tool_variant")
        assert valid is False
        assert "fastmod" in reason

    def test_multiple_invocations_only_one_required(self) -> None:
        """One successful required-tool invocation is enough to pass."""
        step = _make_step(required_tool="ripgrep", blocked_tools=[])
        invocations = [
            {"tool_id": "ripgrep", "exit_status": 0},
            {"tool_id": "ripgrep", "exit_status": 0},
        ]
        valid, _ = validate_step_enforcement(step, invocations, "tool_variant")
        assert valid is True


# ---------------------------------------------------------------------------
# StepExecutor class
# ---------------------------------------------------------------------------


class TestStepExecutor:
    def test_prepare_step_returns_env_dict(self, tmp_path: Path) -> None:
        """prepare_step returns a dict with a PATH key."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep"])
        executor = StepExecutor(wrappers)
        step = _make_step(allowed_tools=["ripgrep"])
        env = executor.prepare_step(step, "tool_variant")
        assert isinstance(env, dict)
        assert "PATH" in env

    def test_prepare_step_baseline_excludes_required_tool(self, tmp_path: Path) -> None:
        """prepare_step baseline variant omits the required_tool wrapper dir."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep"])
        executor = StepExecutor(wrappers)
        step = _make_step(required_tool="ripgrep", allowed_tools=["ripgrep"])
        env = executor.prepare_step(step, "baseline")
        path_dirs = env["PATH"].split(os.pathsep)
        assert str(wrappers["ripgrep"].parent) not in path_dirs

    def test_validate_step_delegates_correctly(self) -> None:
        """validate_step returns (False, reason) when required tool is absent."""
        executor = StepExecutor({})
        step = _make_step(required_tool="ripgrep", blocked_tools=[])
        valid, reason = executor.validate_step(step, [], "tool_variant")
        assert valid is False
        assert "ripgrep" in reason

    def test_validate_step_passes_when_rules_met(self, tmp_path: Path) -> None:
        """validate_step returns (True, '') when all rules are satisfied."""
        wrappers = _make_wrappers(tmp_path, ["ripgrep"])
        executor = StepExecutor(wrappers)
        step = _make_step(required_tool="ripgrep", blocked_tools=["fastmod"])
        invocations = [{"tool_id": "ripgrep", "exit_status": 0}]
        valid, reason = executor.validate_step(step, invocations, "tool_variant")
        assert valid is True
        assert reason == ""
