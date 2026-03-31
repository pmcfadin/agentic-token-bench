"""Claude agent adapter.

Wraps the ``claude`` CLI (Claude Code) to participate in the benchmark
harness.  Uses ``--output-format json`` for structured token reporting.

Reference binary path: /Applications/cmux.app/Contents/Resources/bin/claude
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from agents.base import AgentAdapter, QualificationResult, ReportedTokens, StepResult
from agents.claude.parser import extract_tokens_from_output, parse_claude_json_output

# Sentinel timeout exit code used internally when subprocess.TimeoutExpired fires.
_TIMEOUT_EXIT_CODE = 124  # same convention as GNU timeout(1)


class ClaudeAdapter(AgentAdapter):
    """Adapter for the Claude Code CLI (``claude``).

    Args:
        binary_path: Path to the ``claude`` binary.  Defaults to ``"claude"``
            so that a binary on PATH is used automatically.  Pass the full
            absolute path when the binary is not on PATH.
    """

    def __init__(self, binary_path: str = "claude") -> None:
        self._binary_path = binary_path

    # ------------------------------------------------------------------
    # AgentAdapter abstract method implementations
    # ------------------------------------------------------------------

    def probe(self) -> QualificationResult:
        """Run a minimal qualification probe against the Claude CLI.

        Executes a trivial prompt with ``--output-format json`` and verifies
        that token counts can be extracted from the output.  Sets all four
        qualification gate flags based on what is observable from this single
        invocation.

        Returns:
            QualificationResult with ``qualified=True`` only when token
            extraction succeeds and the process exits cleanly.
        """
        probe_prompt = "Reply with the single word 'ok' and nothing else."
        try:
            proc = subprocess.run(
                [self._binary_path, "-p", probe_prompt, "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=60.0,
            )
        except FileNotFoundError:
            return QualificationResult(
                qualified=False,
                reported_token_support=False,
                forced_tool_support=False,
                trace_support=False,
                run_completion_support=False,
                failure_reason=f"Claude binary not found at '{self._binary_path}'",
            )
        except subprocess.TimeoutExpired:
            return QualificationResult(
                qualified=False,
                reported_token_support=False,
                forced_tool_support=False,
                trace_support=False,
                run_completion_support=False,
                failure_reason="Probe timed out after 60 seconds",
            )

        if proc.returncode != 0:
            return QualificationResult(
                qualified=False,
                reported_token_support=False,
                forced_tool_support=False,
                trace_support=False,
                run_completion_support=False,
                failure_reason=(
                    f"Probe exited with code {proc.returncode}. "
                    f"stderr: {proc.stderr[:200]}"
                ),
            )

        input_tokens, output_tokens, total_tokens, evidence = extract_tokens_from_output(
            proc.stdout
        )
        token_support = total_tokens > 0 and bool(evidence)

        if not token_support:
            return QualificationResult(
                qualified=False,
                reported_token_support=False,
                forced_tool_support=False,
                trace_support=False,
                run_completion_support=False,
                failure_reason="Could not extract token counts from probe output",
            )

        return QualificationResult(
            qualified=True,
            reported_token_support=True,
            # Claude respects --allowedTools for forced-tool steps.
            forced_tool_support=True,
            # JSON output contains structured run metadata.
            trace_support=True,
            # Process exits cleanly with all output captured.
            run_completion_support=True,
        )

    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        """Execute a single benchmark step via the Claude CLI.

        Invokes ``claude -p <prompt> --output-format json`` with the
        constrained ``step_env`` and the benchmark workspace as cwd.  Stdout
        and stderr are captured in full.

        Args:
            prompt: Fully rendered prompt for this step.
            step_env: Environment variables for the subprocess (typically a
                constrained PATH).
            workspace: Working directory for the claude subprocess.
            timeout: Maximum wall-clock seconds allowed.

        Returns:
            StepResult with raw stdout/stderr/exit_status and metadata parsed
            from the JSON output (if available).
        """
        cmd = [self._binary_path, "-p", prompt, "--output-format", "json"]
        start = time.perf_counter()
        timed_out = False

        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace,
                env=step_env or None,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            exit_status = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(
                exc.stdout, bytes
            ) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(
                exc.stderr, bytes
            ) else (exc.stderr or "")
            exit_status = _TIMEOUT_EXIT_CODE
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0

        parsed = parse_claude_json_output(stdout)

        step_metadata: dict = {
            "timed_out": timed_out,
            "duration_ms": duration_ms,
        }
        if parsed:
            for key in ("type", "subtype", "stop_reason", "num_turns", "session_id"):
                if key in parsed:
                    step_metadata[key] = parsed[key]

        trace_metadata: dict = {}
        if "usage" in parsed:
            trace_metadata["usage"] = parsed["usage"]
        if "modelUsage" in parsed:
            trace_metadata["modelUsage"] = parsed["modelUsage"]

        return StepResult(
            stdout=stdout,
            stderr=stderr,
            exit_status=exit_status,
            step_metadata=step_metadata,
            trace_metadata=trace_metadata,
        )

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        """Extract reported token counts from a ClaudeAdapter StepResult.

        Parses ``step_result.stdout`` (which contains the JSON payload from
        ``--output-format json``) to find ``usage.input_tokens`` and
        ``usage.output_tokens``.

        Args:
            step_result: Output of a prior ``run_step()`` call.

        Returns:
            ReportedTokens.  All counts are 0 when the JSON is absent or
            malformed.
        """
        input_tokens, output_tokens, total_tokens, evidence = extract_tokens_from_output(
            step_result.stdout
        )
        return ReportedTokens(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            evidence_snippet=evidence,
        )

    def normalize_final_status(self, step_result: StepResult) -> str:
        """Map a Claude CLI exit code to a canonical benchmark status string.

        Mapping:
        - ``0``  → ``"completed"``
        - ``124`` (timeout sentinel) → ``"timeout"``
        - any other non-zero → ``"failed"``

        Args:
            step_result: Output of a prior ``run_step()`` call.

        Returns:
            One of ``"completed"``, ``"failed"``, or ``"timeout"``.
        """
        if step_result.exit_status == 0:
            return "completed"
        if step_result.exit_status == _TIMEOUT_EXIT_CODE:
            return "timeout"
        return "failed"
