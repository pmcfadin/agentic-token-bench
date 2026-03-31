"""Tool wrapper interface.

Every benchmarked tool must implement this interface to participate
in official runs with traced invocations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml


@dataclass
class ToolManifest:
    """Declares a tool's identity and capabilities."""

    id: str
    name: str
    version: str
    category: str
    description: str
    supported_languages: list[str] = field(default_factory=list)
    waste_classes: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    risk_level: str = "low"


@dataclass
class InvocationRecord:
    """Structured record of a single tool invocation."""

    tool_id: str
    timestamp: datetime
    args_hash: str
    exit_status: int
    duration_ms: float
    step_id: str
    run_id: str


@dataclass
class InvocationResult:
    """Result from invoking a tool."""

    stdout: str
    stderr: str
    exit_status: int
    duration_ms: float


def load_manifest(path: Path) -> ToolManifest:
    """Read a manifest.yaml file and return a ToolManifest.

    Args:
        path: Path to a ``manifest.yaml`` file.

    Returns:
        A populated :class:`ToolManifest` instance.

    Raises:
        FileNotFoundError: If *path* does not exist.
        KeyError: If a required field is missing from the YAML document.
    """
    raw = yaml.safe_load(path.read_text())
    return ToolManifest(
        id=raw["id"],
        name=raw["name"],
        version=raw["version"],
        category=raw["category"],
        description=raw["description"],
        supported_languages=raw.get("supported_languages", []),
        waste_classes=raw.get("waste_classes", []),
        dependencies=raw.get("dependencies", []),
        risk_level=raw.get("risk_level", "low"),
    )


class ToolWrapper(ABC):
    """Base class for tool wrappers."""

    @abstractmethod
    def manifest(self) -> ToolManifest:
        """Return this tool's manifest."""
        ...

    @abstractmethod
    def invoke(
        self,
        args: list[str],
        cwd: Path,
        env: dict[str, str] | None = None,
        timeout: float = 120.0,
    ) -> InvocationResult:
        """Invoke the tool with the given arguments.

        The wrapper must pass through stdout/stderr faithfully
        and record the invocation for tracing.

        Args:
            args: Command-line arguments for the tool.
            cwd: Working directory for execution.
            env: Optional environment overrides.
            timeout: Maximum seconds for this invocation.
        """
        ...

    @abstractmethod
    def record_invocation(
        self,
        result: InvocationResult,
        args: list[str],
        step_id: str,
        run_id: str,
    ) -> InvocationRecord:
        """Create a structured invocation record for the trace."""
        ...
