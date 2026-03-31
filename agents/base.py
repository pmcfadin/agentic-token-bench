"""Agent adapter interface.

Every agent CLI must implement this interface to participate
in official benchmark runs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StepResult:
    """Result from a single step execution."""

    stdout: str
    stderr: str
    exit_status: int
    step_metadata: dict
    trace_metadata: dict


@dataclass
class ReportedTokens:
    """Token counts extracted from agent output."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    evidence_snippet: str


@dataclass
class QualificationResult:
    """Result of running qualification probes."""

    qualified: bool
    reported_token_support: bool
    forced_tool_support: bool
    trace_support: bool
    run_completion_support: bool
    failure_reason: str | None = None
    evidence_paths: list[str] | None = None


class AgentAdapter(ABC):
    """Base class for agent CLI adapters."""

    @abstractmethod
    def probe(self) -> QualificationResult:
        """Run qualification checks and return a qualification result."""
        ...

    @abstractmethod
    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        """Execute a single benchmark step.

        Args:
            prompt: Rendered prompt for this step.
            step_env: Environment variables including constrained PATH.
            workspace: Path to the isolated Cassandra workspace.
            timeout: Maximum seconds for this step.
        """
        ...

    @abstractmethod
    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        """Extract reported token counts from agent output.

        Must return actual reported values, not estimates.
        If extraction fails, the adapter does not qualify.
        """
        ...

    @abstractmethod
    def normalize_final_status(self, step_result: StepResult) -> str:
        """Normalize the agent's final status to a standard string."""
        ...
