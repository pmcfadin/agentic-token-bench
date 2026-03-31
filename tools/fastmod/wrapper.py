"""fastmod tool wrapper."""

import hashlib
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from tools.base import (
    InvocationRecord,
    InvocationResult,
    ToolManifest,
    ToolWrapper,
    load_manifest,
)

_MANIFEST_PATH = Path(__file__).parent / "manifest.yaml"


class FastmodWrapper(ToolWrapper):
    """Wrapper for the fastmod find-and-replace tool."""

    def __init__(self, binary_path: str = "fastmod") -> None:
        self._binary_path = binary_path

    def manifest(self) -> ToolManifest:
        """Load and return the ToolManifest from manifest.yaml."""
        return load_manifest(_MANIFEST_PATH)

    def invoke(
        self,
        args: list[str],
        cwd: Path,
        env: dict[str, str] | None = None,
        timeout: float = 120.0,
    ) -> InvocationResult:
        """Run fastmod with *args* in *cwd* and return an InvocationResult."""
        start = time.perf_counter()
        proc = subprocess.run(
            [self._binary_path, *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
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
        """Build a structured InvocationRecord from a completed invocation."""
        args_hash = hashlib.sha256(str(args).encode()).hexdigest()[:16]
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
        """Return True if the fastmod binary can be found on PATH."""
        return shutil.which(self._binary_path) is not None
