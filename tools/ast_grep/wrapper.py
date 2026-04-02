"""ast-grep tool wrapper."""

import hashlib
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from tools.base import InvocationRecord, InvocationResult, ToolManifest, ToolWrapper, load_manifest

_MANIFEST_PATH = Path(__file__).parent / "manifest.yaml"


class AstGrepWrapper(ToolWrapper):
    """Wrapper around the ast-grep (sg) binary."""

    def __init__(self, binary_path: str = "ast-grep") -> None:
        self._binary_path = binary_path
        if binary_path == "ast-grep":
            # Support both canonical names for the ast-grep binary.
            self._available = (
                shutil.which("ast-grep") is not None
                or shutil.which("sg") is not None
            )
        else:
            self._available = shutil.which(binary_path) is not None

    def manifest(self) -> ToolManifest:
        """Return the ToolManifest loaded from manifest.yaml."""
        return load_manifest(_MANIFEST_PATH)

    def invoke(
        self,
        args: list[str],
        cwd: Path,
        env: dict[str, str] | None = None,
        timeout: float = 120.0,
    ) -> InvocationResult:
        """Run ast-grep with the given args and return an InvocationResult."""
        cmd = [self._binary_path, *args]
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0

        return InvocationResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_status=proc.returncode,
            duration_ms=duration_ms,
        )

    def record_invocation(
        self,
        result: InvocationResult,
        args: list[str],
        step_id: str,
        run_id: str,
    ) -> InvocationRecord:
        """Create an InvocationRecord for the given result and args."""
        args_hash = hashlib.sha256(" ".join(args).encode()).hexdigest()
        return InvocationRecord(
            tool_id=self.manifest().id,
            timestamp=datetime.now(tz=timezone.utc),
            args_hash=args_hash,
            exit_status=result.exit_status,
            duration_ms=result.duration_ms,
            step_id=step_id,
            run_id=run_id,
        )

    def is_available(self) -> bool:
        """Return True if the ast-grep or sg binary is found on PATH."""
        return self._available
