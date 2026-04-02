"""codex agent adapter.

Wraps ``codex exec`` (OpenAI Codex CLI) for use in the benchmark harness.
Invokes the binary in fully-autonomous, non-interactive mode and captures
stdout/stderr plus exit status.  Token counts are extracted from JSON Lines
output (``--json`` flag) which exposes per-turn ``usage`` data.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from agents.codex.parser import extract_tokens_from_output, parse_codex_output

# ---------------------------------------------------------------------------
# Exit-code → benchmark status mapping
# ---------------------------------------------------------------------------

_EXIT_CODE_STATUS: dict[int, str] = {
    0: "completed",
    1: "failed",
    2: "failed",
    124: "timeout",  # convention used by GNU coreutils ``timeout``
    125: "failed",
    126: "failed",
    127: "failed",  # command not found
    130: "failed",  # SIGINT
    143: "timeout",  # SIGTERM (commonly sent on timeout)
}


class CodexAdapter(AgentAdapter):
    """Adapter for the ``codex`` CLI (OpenAI Codex agent).

    Args:
        binary_path: Path or name of the ``codex`` binary.  Defaults to
            ``"codex"`` which resolves via ``$PATH``.
    """

    def __init__(self, binary_path: str = "codex", model: str | None = None) -> None:
        self._binary_path = binary_path
        self._model = model
        self._available: bool = shutil.which(binary_path) is not None

    # ------------------------------------------------------------------
    # AgentAdapter interface
    # ------------------------------------------------------------------

    def probe(self) -> QualificationResult:
        """Run the qualification probe suite for the Codex adapter.

        Executes a minimal prompt with ``--json`` to verify that the binary
        is reachable, that it produces parseable JSON Lines output, and that
        token counts are present in ``turn.completed`` events.

        Returns:
            QualificationResult reflecting whether all four gates passed.
        """
        if not self._available:
            return QualificationResult(
                qualified=False,
                reported_token_support=False,
                forced_tool_support=False,
                trace_support=False,
                run_completion_support=False,
                failure_reason=(
                    f"Codex binary not found: '{self._binary_path}'. "
                    "Install codex CLI and ensure it is on PATH."
                ),
            )

        # Run a minimal probe prompt.
        probe_prompt = "Reply with the single word: hello"
        try:
            result = self.run_step(
                prompt=probe_prompt,
                step_env={},
                workspace=Path("/tmp"),
                timeout=60.0,
            )
        except Exception as exc:  # noqa: BLE001
            return QualificationResult(
                qualified=False,
                reported_token_support=False,
                forced_tool_support=False,
                trace_support=False,
                run_completion_support=False,
                failure_reason=f"Probe invocation raised an exception: {exc}",
            )

        # Gate 1 – reported token support
        reported_token_support = False
        try:
            self.extract_reported_tokens(result)
            reported_token_support = True
        except (ValueError, KeyError):
            pass

        # Gate 2 – forced tool support: basic invocation completed
        forced_tool_support = result.exit_status == 0

        # Gate 3 – trace support: JSON events present in stdout
        parsed = parse_codex_output(result.stdout)
        trace_support = parsed.get("mode") == "json" and bool(parsed.get("events"))

        # Gate 4 – run completion support: turn.completed event observed
        run_completion_support = any(
            e.get("type") == "turn.completed" for e in parsed.get("events", [])
        )

        qualified = all(
            [
                reported_token_support,
                forced_tool_support,
                trace_support,
                run_completion_support,
            ]
        )

        failure_reason: str | None = None
        if not qualified:
            reasons: list[str] = []
            if not reported_token_support:
                reasons.append("token counts not found in output")
            if not forced_tool_support:
                reasons.append(f"non-zero exit status {result.exit_status}")
            if not trace_support:
                reasons.append("no JSON events in stdout")
            if not run_completion_support:
                reasons.append("turn.completed event not observed")
            failure_reason = "; ".join(reasons)

        return QualificationResult(
            qualified=qualified,
            reported_token_support=reported_token_support,
            forced_tool_support=forced_tool_support,
            trace_support=trace_support,
            run_completion_support=run_completion_support,
            failure_reason=failure_reason,
        )

    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        """Invoke ``codex exec`` with the given prompt and capture output.

        Uses ``--full-auto --json --ephemeral`` flags so the process runs
        non-interactively, emits structured JSON Lines to stdout, and does
        not persist session state to disk.

        Args:
            prompt: The rendered benchmark prompt for this step.
            step_env: Environment variables for the subprocess.  An empty
                dict causes the subprocess to inherit the current environment.
            workspace: Working directory for the agent process.
            timeout: Maximum wall-clock seconds before the process is
                terminated.

        Returns:
            StepResult with stdout, stderr, exit_status, and metadata.
        """
        cmd = [
            self._binary_path,
            "exec",
            "--full-auto",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
        ]
        if self._model:
            cmd += ["--model", self._model]
        cmd.append(prompt)

        env: dict[str, str] | None = step_env if step_env else None

        start = time.perf_counter()
        timed_out = False
        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            exit_status = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_status = 124  # GNU timeout convention
            stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0

        parsed = parse_codex_output(stdout)

        step_metadata: dict = {
            "binary_path": self._binary_path,
            "timed_out": timed_out,
            "duration_ms": duration_ms,
            "mode": parsed.get("mode"),
            "agent_text": parsed.get("agent_text", ""),
        }

        trace_metadata: dict = {
            "events": parsed.get("events", []),
            "cached_input_tokens": parsed.get("cached_input_tokens"),
        }

        return StepResult(
            stdout=stdout,
            stderr=stderr,
            exit_status=exit_status,
            step_metadata=step_metadata,
            trace_metadata=trace_metadata,
        )

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        """Parse token counts from codex JSON Lines output.

        Prefers the ``turn.completed`` ``usage`` field from JSON Lines mode.
        Falls back to plain-text ``tokens used`` parsing when the JSON flag
        was not used.

        Args:
            step_result: The StepResult produced by ``run_step()``.

        Returns:
            ReportedTokens with input, output, total counts and the raw
            evidence snippet from the agent output.

        Raises:
            ValueError: If no token information can be extracted.
        """
        inp, out, total, snippet = extract_tokens_from_output(step_result.stdout)
        return ReportedTokens(
            input_tokens=inp,
            output_tokens=out,
            total_tokens=total,
            evidence_snippet=snippet,
        )

    def normalize_final_status(self, step_result: StepResult) -> str:
        """Map a codex exit code to a canonical benchmark status string.

        Args:
            step_result: The StepResult produced by ``run_step()``.

        Returns:
            One of ``"completed"``, ``"failed"``, or ``"timeout"``.
        """
        if step_result.step_metadata.get("timed_out"):
            return "timeout"
        return _EXIT_CODE_STATUS.get(step_result.exit_status, "failed")
