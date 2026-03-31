"""benchmarks.harness.step_executor — step environment construction and enforcement.

Owns:
* per-step PATH construction from allowed tool wrapper binaries
* baseline variant tool-removal logic
* validation of required/blocked tool usage against recorded invocations
* StepExecutor class that ties the above together
"""

from __future__ import annotations

import os
from pathlib import Path

from benchmarks.harness.models import TaskStep

# System directories that must always be present for basic shell operation.
# The agent needs sh, env, python, etc. to function.  We preserve any PATH
# entry from the host environment that is NOT a tool-wrapper directory.
_ESSENTIAL_SYSTEM_DIRS = [
    "/bin",
    "/usr/bin",
    "/usr/local/bin",
    "/sbin",
    "/usr/sbin",
]


def _system_path_entries(base_env: dict[str, str] | None) -> list[str]:
    """Return PATH entries that look like system directories.

    We keep any entry from the base environment PATH that does not appear to be
    a project-managed wrapper directory.  We also always include the hard-coded
    essential directories so that a minimal shell is available even when
    base_env contains nothing useful.
    """
    source_path = (base_env or {}).get("PATH", os.environ.get("PATH", ""))
    entries: list[str] = []
    seen: set[str] = set()

    for entry in source_path.split(os.pathsep):
        entry = entry.strip()
        if entry and entry not in seen:
            seen.add(entry)
            entries.append(entry)

    for d in _ESSENTIAL_SYSTEM_DIRS:
        if d not in seen:
            seen.add(d)
            entries.append(d)

    return entries


def create_step_environment(
    step: TaskStep,
    tool_wrappers: dict[str, Path],
    variant: str,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the environment dict for a single benchmark step.

    The returned PATH exposes only the wrapper binaries whose tool names
    appear in ``step.allowed_tools``.  If ``variant`` is ``"baseline"``,
    the wrapper for ``step.required_tool`` is excluded, enforcing the
    baseline condition where the tool under test is absent.

    All other environment variables are copied from ``base_env`` (or the
    real process environment when ``base_env`` is ``None``).

    Args:
        step: The :class:`TaskStep` being executed.
        tool_wrappers: Mapping of tool name to the **directory** (or binary
            path) for that tool's wrapper.  Each value should be the parent
            directory that the binary lives in, so it can be added to PATH.
        variant: Either ``"baseline"`` or ``"tool_variant"``.
        base_env: Optional base environment to start from.  Defaults to the
            current process environment when ``None``.

    Returns:
        A complete ``dict[str, str]`` environment suitable for passing to
        ``subprocess.run(..., env=env)``.
    """
    source_env: dict[str, str] = dict(base_env) if base_env is not None else dict(os.environ)

    # Collect the directories that should appear in PATH for this step.
    path_dirs: list[str] = []
    seen_dirs: set[str] = set()

    def _add_dir(d: str) -> None:
        if d and d not in seen_dirs:
            seen_dirs.add(d)
            path_dirs.append(d)

    # Add allowed tool wrapper directories, subject to baseline exclusion.
    for tool_name in step.allowed_tools:
        if tool_name not in tool_wrappers:
            continue
        if variant == "baseline" and tool_name == step.required_tool:
            # Baseline: remove the tool under test from PATH.
            continue
        wrapper_path = tool_wrappers[tool_name]
        # Support both "path to binary" and "path to directory".
        wrapper_dir = str(wrapper_path.parent if wrapper_path.is_file() else wrapper_path)
        _add_dir(wrapper_dir)

    # Append system path entries so essential commands remain available.
    for sys_dir in _system_path_entries(base_env):
        _add_dir(sys_dir)

    result_env = dict(source_env)
    result_env["PATH"] = os.pathsep.join(path_dirs)
    return result_env


def validate_step_enforcement(
    step: TaskStep,
    tool_invocations: list[dict],
    variant: str,
) -> tuple[bool, str]:
    """Validate that tool usage in ``tool_invocations`` matches step rules.

    Checks:
    1. If ``step.required_tool`` is set and ``variant`` is ``"tool_variant"``,
       at least one invocation of that tool must be present.
    2. No invocation of any tool listed in ``step.blocked_tools`` may be
       present.

    Args:
        step: The :class:`TaskStep` whose rules should be enforced.
        tool_invocations: List of invocation records.  Each record is expected
            to have a ``"tool_id"`` key with the name of the invoked tool.
        variant: Either ``"baseline"`` or ``"tool_variant"``.

    Returns:
        A ``(valid, reason)`` tuple.  ``valid`` is ``True`` when all rules
        pass.  When ``valid`` is ``False``, ``reason`` contains a human-
        readable explanation.
    """
    invoked_tools: set[str] = {rec.get("tool_id", "") for rec in tool_invocations}

    # Rule 1: required tool must appear in tool_variant runs.
    if variant == "tool_variant" and step.required_tool:
        if step.required_tool not in invoked_tools:
            return (
                False,
                f"required tool '{step.required_tool}' was not used in step '{step.step_id}'",
            )

    # Rule 2: blocked tools must not appear.
    for blocked in step.blocked_tools:
        if blocked in invoked_tools:
            return (
                False,
                f"blocked tool '{blocked}' was used in step '{step.step_id}'",
            )

    return (True, "")


class StepExecutor:
    """Coordinates environment preparation and enforcement validation for steps.

    Args:
        tool_wrappers: Mapping of tool name to the wrapper binary/directory
            path.  Passed through to :func:`create_step_environment`.
    """

    def __init__(self, tool_wrappers: dict[str, Path]) -> None:
        self._tool_wrappers = tool_wrappers

    def prepare_step(self, step: TaskStep, variant: str) -> dict[str, str]:
        """Return the step environment for the given step and variant.

        Args:
            step: The :class:`TaskStep` to prepare.
            variant: Either ``"baseline"`` or ``"tool_variant"``.

        Returns:
            Environment dict with a constrained PATH.
        """
        return create_step_environment(step, self._tool_wrappers, variant)

    def validate_step(
        self,
        step: TaskStep,
        invocations: list[dict],
        variant: str,
    ) -> tuple[bool, str]:
        """Validate tool usage for a completed step.

        Args:
            step: The :class:`TaskStep` whose rules should be enforced.
            invocations: List of invocation records from the step trace.
            variant: Either ``"baseline"`` or ``"tool_variant"``.

        Returns:
            A ``(valid, reason)`` tuple.
        """
        return validate_step_enforcement(step, invocations, variant)
