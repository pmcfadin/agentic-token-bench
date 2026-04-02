"""Canonical prompt rendering for the agentic-token-bench harness.

This module owns the canonical instruction pack and all agent-neutral prompt
rendering.  See docs/plans/2026-03-31-v1-build-plan-design.md, section
"Canonical Prompt Pack", for the requirements these functions satisfy.

Public API
----------
render_task_context(task)                -> str
render_step_prompt(task, step, variant) -> str
render_prompt_pack(task, variant)       -> list[dict]
render_quality_eval_prompt(...)         -> str
"""

from __future__ import annotations

from benchmarks.harness.models import TaskManifest, TaskStep

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CASSANDRA_WORKING_DIR = "/cassandra"  # expected mount / checkout path

_SECTION_SEP = "\n" + "-" * 60 + "\n"


def _section(title: str, body: str) -> str:
    """Return a labelled section block."""
    return f"## {title}\n\n{body.strip()}"


def _tool_list(tools: list[str], fallback: str = "none") -> str:
    if not tools:
        return fallback
    return ", ".join(tools)


# ---------------------------------------------------------------------------
# render_task_context
# ---------------------------------------------------------------------------


def render_task_context(task: TaskManifest) -> str:
    """Render the task-level context block.

    Includes repository name, pinned commit, task objective, and task
    description.  This block is shared across all steps and variants for the
    same task.

    Parameters
    ----------
    task:
        The loaded task manifest.

    Returns
    -------
    str
        A formatted multi-line string suitable for inclusion at the top of any
        step prompt.
    """
    lines: list[str] = []

    lines.append(_section("Repository Context", (
        f"Repository : {task.repo}\n"
        f"Commit     : {task.pinned_commit}\n"
        f"Working dir: {_CASSANDRA_WORKING_DIR}"
    )))

    lines.append(_section("Task", (
        f"ID         : {task.task_id}\n"
        f"Title      : {task.title}\n"
        f"Family     : {task.family}"
    )))

    lines.append(_section("Objective", task.objective.strip()))

    lines.append(_section("Task Description", task.task_description.strip()))

    return ("\n\n").join(lines)


# ---------------------------------------------------------------------------
# render_step_prompt
# ---------------------------------------------------------------------------


def render_step_prompt(task: TaskManifest, step: TaskStep, variant: str) -> str:
    """Render the canonical prompt for a single benchmark step.

    The rendered prompt is self-contained: it includes all context the agent
    needs to execute the step correctly, including the task objective, step
    objective, tool rules (adjusted for the variant), completion contract,
    artifact requirements, and working directory.

    Parameters
    ----------
    task:
        The loaded task manifest that owns this step.
    step:
        The specific step to render a prompt for.
    variant:
        Either ``"baseline"`` or ``"tool_variant"``.  In baseline mode the
        ``required_tool`` entry is omitted from the tool-rules section.

    Returns
    -------
    str
        A fully formatted prompt string.
    """
    is_baseline = variant == "baseline"

    sections: list[str] = []

    # ------------------------------------------------------------------
    # 1. Task context (repo + commit + objective + description)
    # ------------------------------------------------------------------
    sections.append(render_task_context(task))

    # ------------------------------------------------------------------
    # 2. Phase list — show all steps with the current one highlighted
    # ------------------------------------------------------------------
    phase_lines: list[str] = []
    for s in task.steps:
        marker = ">>>" if s.step_id == step.step_id else "   "
        phase_lines.append(f"{marker} [{s.step_id}] {s.name}: {s.objective.strip()}")
    sections.append(_section("Phases", "\n".join(phase_lines)))

    # ------------------------------------------------------------------
    # 3. Current step
    # ------------------------------------------------------------------
    sections.append(_section(
        "Current Step",
        f"Step ID  : {step.step_id}\n"
        f"Name     : {step.name}\n"
        f"Objective: {step.objective.strip()}",
    ))

    # ------------------------------------------------------------------
    # 4. Tool rules (variant-aware)
    # ------------------------------------------------------------------
    allowed = _tool_list(step.allowed_tools)
    blocked = _tool_list(step.blocked_tools)

    if is_baseline:
        # Baseline: omit required_tool mention entirely
        tool_block = (
            f"Variant        : baseline\n"
            f"Allowed tools  : {allowed}\n"
            f"Blocked tools  : {blocked}\n"
            f"Required tool  : none (baseline run — tool under test is removed)"
        )
    else:
        required = step.required_tool if step.required_tool else "none"
        tool_block = (
            f"Variant        : tool_variant\n"
            f"Allowed tools  : {allowed}\n"
            f"Blocked tools  : {blocked}\n"
            f"Required tool  : {required}"
        )
    sections.append(_section("Tool Rules", tool_block))

    # ------------------------------------------------------------------
    # 5. Completion contract
    # ------------------------------------------------------------------
    contract = step.completion_contract
    fields_str = ", ".join(contract.fields) if contract.fields else "none"
    contract_block = (
        f"Kind  : {contract.kind}\n"
        f"Fields: {fields_str}"
    )
    sections.append(_section("Completion Contract", contract_block))

    # ------------------------------------------------------------------
    # 6. Artifact requirements
    # ------------------------------------------------------------------
    artifacts_str = _tool_list(step.artifact_requirements, fallback="none")
    sections.append(_section("Artifact Requirements", artifacts_str))

    # ------------------------------------------------------------------
    # 7. Validation expectation
    # ------------------------------------------------------------------
    if task.validation_commands:
        validation_str = "\n".join(f"  {cmd}" for cmd in task.validation_commands)
    else:
        validation_str = "  (none defined)"
    sections.append(_section(
        "Validation Expectation",
        "Your output will be validated automatically using:\n" + validation_str,
    ))

    # ------------------------------------------------------------------
    # 8. Output format
    # ------------------------------------------------------------------
    output_fields = "\n".join(f"  - {f}" for f in contract.fields) if contract.fields else "  (none)"
    output_block = (
        f"Produce a structured answer of kind '{contract.kind}'.\n"
        f"Include exactly the following fields:\n"
        f"{output_fields}\n\n"
        f"Do not include commentary outside the structured answer unless\n"
        f"explicitly instructed. Do not modify repository files."
    )
    sections.append(_section("Output Format", output_block))

    # ------------------------------------------------------------------
    # 9. Working directory reminder
    # ------------------------------------------------------------------
    sections.append(_section(
        "Working Directory",
        f"The Cassandra repository is available at: {_CASSANDRA_WORKING_DIR}\n"
        "All paths in your answer must be relative to the repository root.",
    ))

    return _SECTION_SEP.join(sections)


# ---------------------------------------------------------------------------
# render_prompt_pack
# ---------------------------------------------------------------------------


def render_prompt_pack(task: TaskManifest, variant: str) -> list[dict]:
    """Render the full canonical prompt pack for every step in a task.

    Parameters
    ----------
    task:
        The loaded task manifest.
    variant:
        Either ``"baseline"`` or ``"tool_variant"``.

    Returns
    -------
    list[dict]
        One entry per step.  Each entry has:

        ``step_id`` : str
            The step identifier from the manifest.
        ``prompt``  : str
            The fully rendered prompt for that step.
    """
    return [
        {"step_id": step.step_id, "prompt": render_step_prompt(task, step, variant)}
        for step in task.steps
    ]


def render_quality_eval_prompt(
    *,
    task_id: str,
    family: str,
    question: str,
    artifact_kind: str,
    artifact_content: str,
) -> str:
    """Render a compact v2 downstream quality-eval prompt."""
    return _SECTION_SEP.join(
        [
            _section(
                "Evaluation Context",
                f"Task ID      : {task_id}\nFamily       : {family}\nArtifact kind: {artifact_kind}",
            ),
            _section("Question", question.strip()),
            _section("Artifact", artifact_content.strip()),
            _section(
                "Output Format",
                "Answer the question directly and concisely. Do not mention benchmark mechanics.",
            ),
        ]
    )
