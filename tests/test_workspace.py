"""Tests for benchmarks.harness.workspace."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from benchmarks.harness.workspace import WorkspaceManager, ensure_cache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_YAML = Path(__file__).parent.parent / "benchmarks" / "repos" / "cassandra" / "repo.yaml"


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


# ---------------------------------------------------------------------------
# Fixture: tiny local git repo
# ---------------------------------------------------------------------------


@pytest.fixture()
def local_repo(tmp_path: Path) -> tuple[Path, str]:
    """Create a minimal local git repo and return (bare_origin_path, commit_sha).

    The bare origin can be used as a ``repo_url`` for :class:`WorkspaceManager`
    without any network access.
    """
    # Create a bare origin to clone from
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)

    # Create a working copy, commit a file, push to origin
    work = tmp_path / "work"
    work.mkdir()
    subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(origin)],
        cwd=work,
        check=True,
        capture_output=True,
    )

    (work / "README.md").write_text("hello")
    subprocess.run(
        [
            "git",
            "-c", "user.email=test@test.com",
            "-c", "user.name=Test",
            "add", "README.md",
        ],
        cwd=work,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-c", "user.email=test@test.com",
            "-c", "user.name=Test",
            "commit", "-m", "init",
        ],
        cwd=work,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "origin", "HEAD:refs/heads/main"],
        cwd=work,
        check=True,
        capture_output=True,
    )

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=work,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    return origin, sha


# ---------------------------------------------------------------------------
# load_repo_config
# ---------------------------------------------------------------------------


class TestLoadRepoConfig:
    def test_loads_real_cassandra_repo_yaml(self) -> None:
        mgr = WorkspaceManager()
        config = mgr.load_repo_config(_REPO_YAML)
        assert config["repo_id"] == "cassandra"
        assert config["url"].startswith("https://")
        assert "pinned_commit" in config
        assert len(config["pinned_commit"]) == 40  # full SHA

    def test_returned_value_is_dict(self) -> None:
        mgr = WorkspaceManager()
        config = mgr.load_repo_config(_REPO_YAML)
        assert isinstance(config, dict)

    def test_required_keys_present(self) -> None:
        mgr = WorkspaceManager()
        config = mgr.load_repo_config(_REPO_YAML)
        for key in ("repo_id", "name", "url", "pinned_commit", "tag"):
            assert key in config, f"missing key: {key}"

    def test_loads_arbitrary_yaml_from_tmp_path(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "repo.yaml"
        cfg_file.write_text(
            "repo_id: test-repo\nname: Test\nurl: https://example.com/repo.git\n"
            "pinned_commit: abc123\ntag: v1.0\ncheckout_dir: x\n",
            encoding="utf-8",
        )
        mgr = WorkspaceManager()
        config = mgr.load_repo_config(cfg_file)
        assert config["repo_id"] == "test-repo"
        assert config["pinned_commit"] == "abc123"


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_removes_existing_directory(self, tmp_path: Path) -> None:
        workspace = tmp_path / "run-abc" / "repo"
        workspace.mkdir(parents=True)
        (workspace / "file.txt").write_text("hello")

        mgr = WorkspaceManager()
        mgr.cleanup(workspace)

        assert not workspace.exists()

    def test_cleanup_on_nonexistent_path_does_not_raise(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager()
        mgr.cleanup(tmp_path / "does-not-exist")  # should be silent

    def test_cleanup_removes_nested_content(self, tmp_path: Path) -> None:
        workspace = tmp_path / "run-xyz"
        deep = workspace / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.txt").write_text("data")

        mgr = WorkspaceManager()
        mgr.cleanup(workspace)

        assert not workspace.exists()


# ---------------------------------------------------------------------------
# prepare — real git operations against a local repo
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _git_available(), reason="git not found")
class TestPrepare:
    """Uses a locally-initialised git repo to avoid any network calls."""

    def test_prepare_creates_repo_directory(self, tmp_path: Path, local_repo: tuple[Path, str]) -> None:
        origin, sha = local_repo
        workspace_base = tmp_path / "workspaces"

        mgr = WorkspaceManager()
        repo_dir = mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="run-001",
            base_dir=workspace_base,
        )

        assert repo_dir.exists()
        assert repo_dir.is_dir()

    def test_prepare_returns_repo_subdirectory(self, tmp_path: Path, local_repo: tuple[Path, str]) -> None:
        origin, sha = local_repo
        workspace_base = tmp_path / "workspaces"

        mgr = WorkspaceManager()
        repo_dir = mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="run-002",
            base_dir=workspace_base,
        )

        # prepare() should return <base_dir>/<run_id>/repo
        assert repo_dir == workspace_base / "run-002" / "repo"

    def test_prepare_checks_out_correct_commit(
        self, tmp_path: Path, local_repo: tuple[Path, str]
    ) -> None:
        origin, sha = local_repo
        workspace_base = tmp_path / "workspaces"

        mgr = WorkspaceManager()
        repo_dir = mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="run-003",
            base_dir=workspace_base,
        )

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == sha

    def test_prepare_creates_base_dir_if_missing(
        self, tmp_path: Path, local_repo: tuple[Path, str]
    ) -> None:
        origin, sha = local_repo
        base_dir = tmp_path / "nested" / "base"

        mgr = WorkspaceManager()
        mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="run-004",
            base_dir=base_dir,
        )

        assert base_dir.exists()

    def test_prepare_uses_temp_dir_when_base_dir_is_none(
        self, local_repo: tuple[Path, str]
    ) -> None:
        origin, sha = local_repo

        mgr = WorkspaceManager()
        repo_dir = mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="run-005",
        )

        assert repo_dir.exists()
        assert repo_dir.is_dir()

    def test_prepare_uses_reference_when_cache_dir_provided(
        self, tmp_path: Path, local_repo: tuple[Path, str]
    ) -> None:
        origin, sha = local_repo
        cache_dir = tmp_path / "cache"
        workspace_base = tmp_path / "workspaces"

        mgr = WorkspaceManager(cache_dir=cache_dir)
        repo_dir = mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="run-006",
            base_dir=workspace_base,
        )

        # The cache directory should have been populated by ensure_cache
        assert cache_dir.exists()
        # The repo should still be cloned and checked out correctly
        assert repo_dir.exists()
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == sha

    def test_cleanup_removes_prepared_workspace(
        self, tmp_path: Path, local_repo: tuple[Path, str]
    ) -> None:
        origin, sha = local_repo
        workspace_base = tmp_path / "workspaces"

        mgr = WorkspaceManager()
        repo_dir = mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="run-007",
            base_dir=workspace_base,
        )
        assert repo_dir.exists()

        mgr.cleanup(repo_dir)
        assert not repo_dir.exists()


# ---------------------------------------------------------------------------
# ensure_cache — real git operations against a local repo
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _git_available(), reason="git not found")
class TestEnsureCache:
    def test_clones_bare_when_cache_missing(
        self, tmp_path: Path, local_repo: tuple[Path, str]
    ) -> None:
        origin, _sha = local_repo
        cache_dir = tmp_path / "cache"

        result = ensure_cache(str(origin), cache_dir)

        assert result.exists()
        # A bare clone has HEAD and config files but no working tree
        assert (result / "HEAD").exists()

    def test_fetches_when_cache_exists(
        self, tmp_path: Path, local_repo: tuple[Path, str]
    ) -> None:
        origin, _sha = local_repo
        cache_dir = tmp_path / "cache"

        # First call: clones
        result_first = ensure_cache(str(origin), cache_dir)
        assert result_first.exists()

        # Second call: should fetch (not error) and return the same path
        result_second = ensure_cache(str(origin), cache_dir)
        assert result_second == result_first

    def test_slug_strips_git_suffix(
        self, tmp_path: Path, local_repo: tuple[Path, str]
    ) -> None:
        origin, _sha = local_repo
        # Rename origin dir so its name ends in .git to test suffix stripping
        origin_with_suffix = origin.parent / "myrepo.git"
        origin.rename(origin_with_suffix)
        cache_dir = tmp_path / "cache"

        result = ensure_cache(str(origin_with_suffix), cache_dir)

        assert result.name == "myrepo"
        assert result == cache_dir / "myrepo"

    def test_cache_dir_is_created_if_missing(
        self, tmp_path: Path, local_repo: tuple[Path, str]
    ) -> None:
        origin, _sha = local_repo
        cache_dir = tmp_path / "nonexistent" / "cache"

        ensure_cache(str(origin), cache_dir)

        assert cache_dir.exists()
