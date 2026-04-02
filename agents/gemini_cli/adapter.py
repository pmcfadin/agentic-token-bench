"""gemini_cli agent adapter.

Wraps the Gemini CLI binary (``gemini``) so it can participate in official
benchmark runs.  Invokes the binary in non-interactive mode with
``--output-format stream-json`` to obtain structured token statistics.
"""

import subprocess
from pathlib import Path

from agents.base import (
    AgentAdapter,
    QualificationResult,
    ReportedTokens,
    StepResult,
)
from agents.gemini_cli.parser import extract_tokens_from_output


_PROBE_PROMPT = "Say the word HELLO and nothing else."


class GeminiCliAdapter(AgentAdapter):
    """AgentAdapter implementation for the Gemini CLI.

    Args:
        binary_path: Path to the ``gemini`` binary.  Defaults to ``"gemini"``
            (resolved via PATH).  Pass an absolute path (e.g.
            ``"/opt/homebrew/bin/gemini"``) for reproducibility.
    """

    def __init__(self, binary_path: str = "gemini", model: str | None = None) -> None:
        self.binary_path = binary_path
        self._model = model

    # ------------------------------------------------------------------
    # AgentAdapter interface
    # ------------------------------------------------------------------

    def probe(self) -> QualificationResult:
        """Run basic qualification probes against the Gemini CLI binary.

        Gate 1 – Binary invocable: the binary must exit without a hard error
        on a minimal prompt.
        Gate 2 – Token reporting: ``extract_tokens_from_output`` must return
        non-zero counts.

        Returns:
            QualificationResult with ``qualified=True`` only if both gates
            pass.
        """
        try:
            result = self.run_step(
                prompt=_PROBE_PROMPT,
                step_env={},
                workspace=Path("."),
                timeout=120.0,
            )
        except Exception as exc:
            return QualificationResult(
                qualified=False,
                reported_token_support=False,
                forced_tool_support=False,
                trace_support=False,
                run_completion_support=False,
                failure_reason=f"Binary invocation failed: {exc}",
            )

        # Gate 1: binary must complete (exit 0 or at least produce output).
        invocable = result.exit_status == 0 or bool(result.stdout)

        # Gate 2: token extraction.
        combined = result.stdout + "\n" + result.stderr
        inp, out, tot, evidence = extract_tokens_from_output(combined)
        token_support = bool(inp or out or tot)

        qualified = invocable and token_support
        failure_reason: str | None = None
        if not qualified:
            parts: list[str] = []
            if not invocable:
                parts.append("binary not invocable (exit status non-zero, no stdout)")
            if not token_support:
                parts.append("token counts not found in output")
            failure_reason = "; ".join(parts)

        evidence_paths: list[str] | None = None
        if evidence:
            evidence_paths = [evidence[:200]]

        return QualificationResult(
            qualified=qualified,
            reported_token_support=token_support,
            # forced_tool and trace support require deeper probes; mark as
            # False here since this is the basic qualification only.
            forced_tool_support=False,
            trace_support=token_support,  # stream-json provides a trace
            run_completion_support=invocable,
            failure_reason=failure_reason,
            evidence_paths=evidence_paths,
        )

    def run_step(
        self,
        prompt: str,
        step_env: dict[str, str],
        workspace: Path,
        timeout: float,
    ) -> StepResult:
        """Invoke the Gemini CLI with the given prompt and capture output.

        Uses ``--output-format stream-json`` for structured token reporting.

        Args:
            prompt: Fully rendered prompt for this step.
            step_env: Environment variables for the subprocess.  An empty
                dict inherits the current process environment.
            workspace: Working directory for the gemini subprocess.
            timeout: Wall-clock seconds before the subprocess is killed.

        Returns:
            StepResult with stdout, stderr, exit_status, and metadata.
        """
        cmd = [
            self.binary_path,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
        ]
        if self._model:
            cmd += ["--model", self._model]

        env: dict[str, str] | None = step_env if step_env else None

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(workspace),
                env=env,
                timeout=timeout,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            exit_status = proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return StepResult(
                stdout=stdout,
                stderr=stderr,
                exit_status=-1,
                step_metadata={"timeout": True, "timeout_seconds": timeout},
                trace_metadata={},
            )

        # Parse stream-json to build metadata.
        from agents.gemini_cli.parser import parse_gemini_output

        combined = stdout + "\n" + stderr
        parsed = parse_gemini_output(combined)
        stats = parsed.get("stats", {})

        step_metadata: dict = {
            "status": parsed.get("status", "unknown"),
            "timeout": False,
        }
        if stats:
            step_metadata["stats"] = stats

        return StepResult(
            stdout=stdout,
            stderr=stderr,
            exit_status=exit_status,
            step_metadata=step_metadata,
            trace_metadata={"parsed_output": parsed},
        )

    def extract_reported_tokens(self, step_result: StepResult) -> ReportedTokens:
        """Extract token counts from a Gemini CLI StepResult.

        Searches both stdout and stderr for the stream-json ``result`` line
        containing token statistics.

        Args:
            step_result: The StepResult produced by ``run_step()``.

        Returns:
            ReportedTokens populated from the ``stats`` block in the result
            line.  All counts are 0 if no token data was found.
        """
        combined = step_result.stdout + "\n" + step_result.stderr
        inp, out, tot, evidence = extract_tokens_from_output(combined)
        return ReportedTokens(
            input_tokens=inp,
            output_tokens=out,
            total_tokens=tot,
            evidence_snippet=evidence,
        )

    def normalize_final_status(self, step_result: StepResult) -> str:
        """Normalize Gemini CLI exit state to a standard benchmark status.

        Mapping:
            - ``exit_status == 0``   → ``"completed"``
            - ``exit_status == -1``  → ``"timeout"``  (set by run_step on TimeoutExpired)
            - Any other non-zero    → ``"failed"``

        Args:
            step_result: The StepResult produced by ``run_step()``.

        Returns:
            One of ``"completed"``, ``"timeout"``, or ``"failed"``.
        """
        if step_result.exit_status == 0:
            return "completed"
        if step_result.exit_status == -1 or step_result.step_metadata.get("timeout"):
            return "timeout"
        return "failed"
