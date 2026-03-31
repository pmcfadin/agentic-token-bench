"""Tests for benchmarks.harness.prompts.

Loads the real cassandra-ripgrep-01.yaml manifest to exercise the rendering
functions against genuine task data.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from benchmarks.harness.models import TaskManifest
from benchmarks.harness.prompts import (
    render_prompt_pack,
    render_step_prompt,
    render_task_context,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MANIFEST_PATH = (
    Path(__file__).parent.parent
    / "benchmarks"
    / "tasks"
    / "cassandra"
    / "official"
    / "cassandra-ripgrep-01.yaml"
)


@pytest.fixture(scope="module")
def task() -> TaskManifest:
    """Load the real cassandra-ripgrep-01 manifest once per test module."""
    raw = yaml.safe_load(_MANIFEST_PATH.read_text())
    return TaskManifest.model_validate(raw)


@pytest.fixture(scope="module")
def discover_step(task: TaskManifest):
    """Return the 'discover' step from the loaded manifest."""
    return next(s for s in task.steps if s.step_id == "discover")


@pytest.fixture(scope="module")
def summarize_step(task: TaskManifest):
    """Return the 'summarize' step from the loaded manifest."""
    return next(s for s in task.steps if s.step_id == "summarize")


# ---------------------------------------------------------------------------
# render_task_context
# ---------------------------------------------------------------------------


class TestRenderTaskContext:
    def test_contains_repo_name(self, task: TaskManifest) -> None:
        ctx = render_task_context(task)
        assert "cassandra" in ctx

    def test_contains_pinned_commit(self, task: TaskManifest) -> None:
        ctx = render_task_context(task)
        assert task.pinned_commit in ctx

    def test_contains_objective(self, task: TaskManifest) -> None:
        ctx = render_task_context(task)
        # Objective should appear (at least a fragment of it)
        assert "read repair" in ctx.lower()

    def test_contains_task_description(self, task: TaskManifest) -> None:
        ctx = render_task_context(task)
        assert "task description" in ctx.lower() or "cassandra" in ctx.lower()

    def test_contains_working_dir(self, task: TaskManifest) -> None:
        ctx = render_task_context(task)
        assert "/cassandra" in ctx


# ---------------------------------------------------------------------------
# render_step_prompt — section presence
# ---------------------------------------------------------------------------


class TestRenderStepPromptSections:
    def test_contains_task_objective(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert "Objective" in prompt

    def test_contains_step_objective(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert discover_step.step_id in prompt

    def test_contains_tool_rules_section(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert "Tool Rules" in prompt

    def test_contains_completion_contract_section(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert "Completion Contract" in prompt

    def test_contains_artifact_requirements_section(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert "Artifact Requirements" in prompt

    def test_contains_validation_expectation_section(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert "Validation" in prompt

    def test_contains_output_format_section(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert "Output Format" in prompt

    def test_contains_working_directory_section(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert "Working Directory" in prompt

    def test_contains_phase_list(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert "Phases" in prompt
        # Both step ids should appear in the phase list
        assert "discover" in prompt
        assert "summarize" in prompt

    def test_completion_contract_fields_present(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        for field in discover_step.completion_contract.fields:
            assert field in prompt

    def test_repo_commit_in_prompt(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert task.pinned_commit in prompt


# ---------------------------------------------------------------------------
# render_step_prompt — tool_variant includes required_tool
# ---------------------------------------------------------------------------


class TestRenderStepPromptToolVariant:
    def test_required_tool_present_in_tool_variant(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert discover_step.required_tool in prompt

    def test_variant_label_is_tool_variant(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        assert "tool_variant" in prompt

    def test_allowed_tools_listed(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        for tool in discover_step.allowed_tools:
            assert tool in prompt

    def test_blocked_tools_listed(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "tool_variant")
        # At least one blocked tool should appear
        assert any(tool in prompt for tool in discover_step.blocked_tools)


# ---------------------------------------------------------------------------
# render_step_prompt — baseline removes required_tool
# ---------------------------------------------------------------------------


class TestRenderStepPromptBaseline:
    def test_baseline_label_present(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "baseline")
        assert "baseline" in prompt

    def test_required_tool_not_enforced_in_baseline(self, task, discover_step) -> None:
        """In baseline the required tool must not appear as an enforced requirement."""
        prompt = render_step_prompt(task, discover_step, "baseline")
        # The phrase "Required tool  : ripgrep" should NOT appear in baseline
        # (it is replaced with a "none" notice)
        assert "Required tool  : ripgrep" not in prompt

    def test_baseline_states_tool_is_removed(self, task, discover_step) -> None:
        prompt = render_step_prompt(task, discover_step, "baseline")
        assert "removed" in prompt.lower() or "none" in prompt.lower()

    def test_summarize_step_no_required_tool_baseline(self, task, summarize_step) -> None:
        """Summarize step has required_tool=None; baseline prompt should still render."""
        prompt = render_step_prompt(task, summarize_step, "baseline")
        assert "Completion Contract" in prompt
        assert "Tool Rules" in prompt

    def test_summarize_step_tool_variant_shows_none(self, task, summarize_step) -> None:
        """Summarize step required_tool is null; tool_variant renders 'none'."""
        prompt = render_step_prompt(task, summarize_step, "tool_variant")
        assert "Required tool  : none" in prompt


# ---------------------------------------------------------------------------
# render_prompt_pack
# ---------------------------------------------------------------------------


class TestRenderPromptPack:
    def test_returns_list(self, task) -> None:
        pack = render_prompt_pack(task, "tool_variant")
        assert isinstance(pack, list)

    def test_correct_number_of_steps(self, task) -> None:
        pack = render_prompt_pack(task, "tool_variant")
        assert len(pack) == len(task.steps)

    def test_each_entry_has_step_id_and_prompt(self, task) -> None:
        pack = render_prompt_pack(task, "tool_variant")
        for entry in pack:
            assert "step_id" in entry
            assert "prompt" in entry
            assert isinstance(entry["step_id"], str)
            assert isinstance(entry["prompt"], str)

    def test_step_ids_match_manifest(self, task) -> None:
        pack = render_prompt_pack(task, "tool_variant")
        manifest_ids = [s.step_id for s in task.steps]
        pack_ids = [entry["step_id"] for entry in pack]
        assert pack_ids == manifest_ids

    def test_baseline_pack_correct_count(self, task) -> None:
        pack = render_prompt_pack(task, "baseline")
        assert len(pack) == len(task.steps)

    def test_baseline_pack_omits_required_tool(self, task) -> None:
        """Every step in the baseline pack must not enforce the required_tool."""
        pack = render_prompt_pack(task, "baseline")
        for entry in pack:
            # The explicit "Required tool  : ripgrep" line must not appear
            assert "Required tool  : ripgrep" not in entry["prompt"]

    def test_tool_variant_pack_enforces_required_tool(self, task) -> None:
        """The discover step in tool_variant pack must show ripgrep as required."""
        pack = render_prompt_pack(task, "tool_variant")
        discover_entry = next(e for e in pack if e["step_id"] == "discover")
        assert "Required tool  : ripgrep" in discover_entry["prompt"]

    def test_prompts_are_non_empty_strings(self, task) -> None:
        pack = render_prompt_pack(task, "tool_variant")
        for entry in pack:
            assert len(entry["prompt"].strip()) > 0
