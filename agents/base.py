"""Agent adapter interface.

Every agent CLI must implement this interface to participate
in official benchmark runs.

Reference: docs/plans/2026-03-31-v1-build-plan-design.md, "Agent Adapter Contract"
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StepResult:
    """Result from a single benchmark step execution.

    Attributes:
        stdout: Raw standard output captured from the agent process.
        stderr: Raw standard error captured from the agent process.
        exit_status: Process exit code returned by the agent CLI.
        step_metadata: Agent-specific metadata about step completion
            (e.g. finish reason, tool call counts).
        trace_metadata: Trace-level metadata emitted by the agent, if
            available (e.g. structured event logs, timing data).
    """

    stdout: str
    stderr: str
    exit_status: int
    step_metadata: dict
    trace_metadata: dict


@dataclass
class ReportedTokens:
    """Token counts reported by the agent CLI, extracted from its output.

    Official benchmark runs require reported values only.  Estimated token
    counts are not permitted in official scorecards.

    Attributes:
        input_tokens: Reported input token count for the step.
        output_tokens: Reported output token count for the step.
        total_tokens: Reported total token count for the step.
        evidence_snippet: Raw text from agent output that contains the
            reported counts, used to verify extraction correctness.
    """

    input_tokens: int
    output_tokens: int
    total_tokens: int
    evidence_snippet: str


@dataclass
class QualificationResult:
    """Result of running the qualification probe suite against an agent.

    An agent must pass all four gates before it appears in official
    scorecards.  See the "Agent Qualification Protocol" section of the
    implementation plan for the full gate definitions.

    Attributes:
        qualified: True only if all four qualification gates passed.
        reported_token_support: True if the CLI exposes stable reported
            token counts that can be extracted programmatically.
        forced_tool_support: True if the agent can operate inside a
            constrained step environment where required tools appear in
            the trace when mandated.
        trace_support: True if the run emits enough observable output to
            reconstruct tool usage and step progress.
        run_completion_support: True if the harness can capture start,
            finish, tokens, artifacts, validation output, and final status
            without manual intervention.
        failure_reason: Human-readable explanation when ``qualified`` is
            False.  None when qualified.
        evidence_paths: Paths to artifact files that support the
            qualification decision (e.g. token_evidence.txt, trace logs).
            None when no evidence was collected.
    """

    qualified: bool
    reported_token_support: bool
    forced_tool_support: bool
    trace_support: bool
    run_completion_support: bool
    failure_reason: str | None = None
    evidence_paths: list[str] | None = None


class AgentAdapter(ABC):
    """Abstract base class for agent CLI adapters.

    Every supported agent (``claude``, ``codex``, ``gemini-cli``) must
    provide a concrete subclass that implements all four abstract methods.
    No CLI enters the official benchmark until its adapter passes the full
    qualification protocol via ``probe()``.

    Subclasses must implement:
        - ``probe()``
        - ``run_step()``
        - ``extract_reported_tokens()``
        - ``normalize_final_status()``
    """

    @abstractmethod
    def probe(self) -> QualificationResult:
        """Run the full qualification probe suite for this agent.

        Executes the five standard qualification probes:
        - token reporting probe
        - simple no-tool step probe
        - forced single-tool step probe
        - blocked-tool failure probe
        - completion and artifact probe

        Returns:
            QualificationResult with ``qualified=True`` only if all four
            gates (reported-token, forced-tool, audit-trace,
            run-completeness) pass.
        """
        ...

    @abstractmethod
    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        """Execute a single benchmark step and return its raw outputs.

        The harness calls this method once per task step.  The adapter is
        responsible for invoking the agent CLI with the constrained
        environment and capturing all output faithfully.

        Args:
            prompt: Fully rendered prompt for this step, including task
                objective, per-step tool rules, and completion contract.
            step_env: Environment variables for the agent subprocess,
                including a constrained PATH that exposes only allowed
                tool wrappers for this step.
            workspace: Path to the isolated Cassandra workspace directory
                for this run.
            timeout: Maximum wall-clock seconds the adapter may allow
                before terminating the agent process.

        Returns:
            StepResult containing raw stdout, stderr, exit status, and
            any available step or trace metadata.
        """
        ...

    @abstractmethod
    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        """Extract reported token counts from agent output.

        Parses the agent's stdout or stderr to find the token counts that
        the CLI reports at the end of a run.  Must return actual values
        reported by the agent, never estimates or proxies.

        If token counts cannot be extracted reliably, the adapter does not
        qualify for official runs and ``probe()`` should reflect that.

        Args:
            step_result: The StepResult produced by ``run_step()``.

        Returns:
            ReportedTokens with input_tokens, output_tokens, total_tokens,
            and an evidence_snippet from the raw agent output.
        """
        ...

    @abstractmethod
    def normalize_final_status(self, step_result: StepResult) -> str:
        """Normalize the agent's final status to a standard benchmark string.

        Converts agent-specific exit codes and status indicators into the
        canonical benchmark status vocabulary so that the run record and
        scorecard use consistent values across all adapters.

        Args:
            step_result: The StepResult produced by ``run_step()``.

        Returns:
            A normalized status string (e.g. ``"completed"``,
            ``"failed"``, ``"timeout"``).
        """
        ...
