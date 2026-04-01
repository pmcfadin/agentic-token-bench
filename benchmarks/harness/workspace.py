"""benchmarks.harness.workspace — Cassandra checkout, isolation, and cleanup for benchmark runs.

See docs/plans/2026-03-31-v1-build-plan-design.md for responsibilities.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml


def ensure_cache(repo_url: str, cache_dir: Path) -> Path:
    """Clone or update a bare cached repo at cache_dir / <repo-slug>.

    Returns the path to the cached bare clone.
    """
    # Derive a slug from the URL, e.g. "cassandra" from ".../cassandra.git"
    slug = repo_url.rstrip("/").rstrip(".git").rsplit("/", 1)[-1].removesuffix(".git")
    cached = cache_dir / slug

    if cached.exists():
        # Update the existing cache — use the URL directly since bare clones
        # may not have a configured remote.
        subprocess.run(
            ["git", "fetch", repo_url, "+refs/heads/*:refs/heads/*"],
            cwd=cached,
            check=True,
            capture_output=True,
        )
    else:
        cache_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--bare", repo_url, str(cached)],
            check=True,
            capture_output=True,
        )

    return cached


class WorkspaceManager:
    """Manages isolated workspace directories for benchmark runs."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        """
        Parameters
        ----------
        cache_dir:
            Optional directory that holds cached bare clones.  When provided,
            clones use ``--reference`` to reuse objects and avoid a full network
            fetch per run.
        """
        self.cache_dir = cache_dir

    def load_repo_config(self, config_path: Path) -> dict:
        """Load and return a repo.yaml configuration file as a plain dict."""
        with config_path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def prepare(
        self,
        repo_url: str,
        commit: str,
        run_id: str,
        base_dir: Path | None = None,
    ) -> Path:
        """Clone the repository at *commit* into a fresh isolated directory.

        Parameters
        ----------
        repo_url:
            Remote URL of the git repository.
        commit:
            The exact commit SHA (or tag/branch that resolves to one) to check out.
        run_id:
            Unique identifier for the run; used as the workspace directory name.
        base_dir:
            Parent directory for the workspace.  If *None* a system temp
            directory is created and used.

        Returns
        -------
        Path
            Absolute path to the prepared workspace directory.
        """
        if base_dir is None:
            base_dir = Path(tempfile.mkdtemp(prefix="atb-"))
        else:
            base_dir.mkdir(parents=True, exist_ok=True)

        workspace = base_dir / run_id
        workspace.mkdir(parents=True, exist_ok=True)

        clone_args = ["git", "clone"]

        if self.cache_dir is not None:
            # Fast path: reuse local object store via --reference
            cached = ensure_cache(repo_url, self.cache_dir)
            clone_args += ["--reference", str(cached)]

        clone_args += ["--depth", "1", repo_url, str(workspace / "repo")]

        subprocess.run(clone_args, check=True, capture_output=True)

        repo_dir = workspace / "repo"

        # Fetch the pinned commit in case --depth 1 didn't land on it
        subprocess.run(
            ["git", "fetch", "--depth", "1", "origin", commit],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "checkout", commit],
            cwd=repo_dir,
            check=True,
            capture_output=True,
        )

        return repo_dir

    def cleanup(self, workspace_path: Path) -> None:
        """Remove the workspace directory tree created by :meth:`prepare`."""
        if workspace_path.exists():
            shutil.rmtree(workspace_path)
