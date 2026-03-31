"""Tests for benchmarks.harness.workspace."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benchmarks.harness.workspace import WorkspaceManager, ensure_cache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPO_YAML = Path(__file__).parent.parent / "benchmarks" / "repos" / "cassandra" / "repo.yaml"


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
# prepare — mocked git calls
# ---------------------------------------------------------------------------


def _mock_run_success(*args, **kwargs) -> MagicMock:  # noqa: ARG001
    result = MagicMock()
    result.returncode = 0
    return result


class TestPrepareMocked:
    """These tests mock subprocess.run to avoid real network calls."""

    def _setup_fake_repo(self, tmp_path: Path, run_id: str) -> Path:
        """Create the repo directory that would be created by git clone."""
        repo_dir = tmp_path / run_id / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)
        return repo_dir

    def test_prepare_creates_workspace_directory(self, tmp_path: Path) -> None:
        run_id = "run-001"
        # Pre-create repo dir so the function returns the right path
        repo_dir = self._setup_fake_repo(tmp_path, run_id)

        with patch("subprocess.run", side_effect=_mock_run_success):
            mgr = WorkspaceManager()
            result = mgr.prepare(
                repo_url="https://example.com/repo.git",
                commit="abc123",
                run_id=run_id,
                base_dir=tmp_path,
            )

        assert result == repo_dir

    def test_prepare_calls_git_clone(self, tmp_path: Path) -> None:
        run_id = "run-002"
        self._setup_fake_repo(tmp_path, run_id)

        with patch("subprocess.run", side_effect=_mock_run_success) as mock_run:
            mgr = WorkspaceManager()
            mgr.prepare(
                repo_url="https://example.com/repo.git",
                commit="deadbeef",
                run_id=run_id,
                base_dir=tmp_path,
            )

        commands = [c.args[0] for c in mock_run.call_args_list]
        assert any("clone" in cmd for cmd in commands)

    def test_prepare_calls_git_fetch_and_checkout(self, tmp_path: Path) -> None:
        run_id = "run-003"
        self._setup_fake_repo(tmp_path, run_id)

        with patch("subprocess.run", side_effect=_mock_run_success) as mock_run:
            mgr = WorkspaceManager()
            mgr.prepare(
                repo_url="https://example.com/repo.git",
                commit="deadbeef",
                run_id=run_id,
                base_dir=tmp_path,
            )

        flat = [arg for c in mock_run.call_args_list for arg in c.args[0]]
        assert "fetch" in flat
        assert "checkout" in flat
        assert "deadbeef" in flat

    def test_prepare_uses_reference_when_cache_dir_provided(self, tmp_path: Path) -> None:
        run_id = "run-004"
        cache_dir = tmp_path / "cache"
        self._setup_fake_repo(tmp_path, run_id)

        # ensure_cache will look for cache_dir/repo; pre-create it
        cached_bare = cache_dir / "repo"
        cached_bare.mkdir(parents=True, exist_ok=True)

        with patch("subprocess.run", side_effect=_mock_run_success) as mock_run:
            mgr = WorkspaceManager(cache_dir=cache_dir)
            mgr.prepare(
                repo_url="https://example.com/repo.git",
                commit="abc123",
                run_id=run_id,
                base_dir=tmp_path,
            )

        flat = [arg for c in mock_run.call_args_list for arg in c.args[0]]
        assert "--reference" in flat

    def test_prepare_creates_base_dir_if_missing(self, tmp_path: Path) -> None:
        base_dir = tmp_path / "nested" / "base"
        run_id = "run-005"
        # Pre-create repo dir
        repo_dir = base_dir / run_id / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)

        with patch("subprocess.run", side_effect=_mock_run_success):
            mgr = WorkspaceManager()
            mgr.prepare(
                repo_url="https://example.com/repo.git",
                commit="abc123",
                run_id=run_id,
                base_dir=base_dir,
            )

        assert base_dir.exists()

    def test_prepare_uses_temp_dir_when_base_dir_is_none(self, tmp_path: Path) -> None:
        """When base_dir is None a temp directory is created automatically."""
        run_id = "run-006"

        temp_base = tmp_path / "tmpbase"
        repo_dir = temp_base / run_id / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch("tempfile.mkdtemp", return_value=str(temp_base)),
            patch("subprocess.run", side_effect=_mock_run_success),
        ):
            mgr = WorkspaceManager()
            result = mgr.prepare(
                repo_url="https://example.com/repo.git",
                commit="abc123",
                run_id=run_id,
            )

        assert result.is_relative_to(temp_base)


# ---------------------------------------------------------------------------
# ensure_cache — mocked git calls
# ---------------------------------------------------------------------------


class TestEnsureCache:
    def test_clones_bare_when_cache_missing(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"

        with patch("subprocess.run", side_effect=_mock_run_success) as mock_run:
            result = ensure_cache("https://example.com/myrepo.git", cache_dir)

        flat = [arg for c in mock_run.call_args_list for arg in c.args[0]]
        assert "clone" in flat
        assert "--bare" in flat
        assert result == cache_dir / "myrepo"

    def test_fetches_when_cache_exists(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cached = cache_dir / "myrepo"
        cached.mkdir(parents=True, exist_ok=True)

        with patch("subprocess.run", side_effect=_mock_run_success) as mock_run:
            result = ensure_cache("https://example.com/myrepo.git", cache_dir)

        flat = [arg for c in mock_run.call_args_list for arg in c.args[0]]
        assert "fetch" in flat
        assert "clone" not in flat
        assert result == cached

    def test_slug_strips_git_suffix(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"

        with patch("subprocess.run", side_effect=_mock_run_success):
            result = ensure_cache("https://github.com/apache/cassandra.git", cache_dir)

        assert result.name == "cassandra"
        assert result == cache_dir / "cassandra"


# ---------------------------------------------------------------------------
# Real git tests — skipped if git is not available or there is no network
# ---------------------------------------------------------------------------


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


@pytest.mark.skipif(not _git_available(), reason="git not found")
class TestPrepareWithLocalRepo:
    """Uses a locally-initialised bare git repo to avoid network calls."""

    def _make_local_repo(self, tmp_path: Path) -> tuple[Path, str]:
        """Create a minimal git repo with one commit; return (repo_url, commit_sha)."""
        origin = tmp_path / "origin.git"
        origin.mkdir()
        subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)

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
            ["git", "-c", "user.email=test@test.com", "-c", "user.name=Test",
             "commit", "--allow-empty", "-m", "init"],
            cwd=work,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=work,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-c", "user.email=test@test.com", "-c", "user.name=Test",
             "commit", "-m", "add readme"],
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

    def test_prepare_creates_repo_directory(self, tmp_path: Path) -> None:
        origin, sha = self._make_local_repo(tmp_path)
        workspace_base = tmp_path / "workspaces"

        mgr = WorkspaceManager()
        repo_dir = mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="local-run-001",
            base_dir=workspace_base,
        )

        assert repo_dir.exists()
        assert repo_dir.is_dir()

    def test_prepare_checks_out_correct_commit(self, tmp_path: Path) -> None:
        origin, sha = self._make_local_repo(tmp_path)
        workspace_base = tmp_path / "workspaces"

        mgr = WorkspaceManager()
        repo_dir = mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="local-run-002",
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

    def test_cleanup_removes_prepared_workspace(self, tmp_path: Path) -> None:
        origin, sha = self._make_local_repo(tmp_path)
        workspace_base = tmp_path / "workspaces"

        mgr = WorkspaceManager()
        repo_dir = mgr.prepare(
            repo_url=str(origin),
            commit=sha,
            run_id="local-run-003",
            base_dir=workspace_base,
        )
        assert repo_dir.exists()

        mgr.cleanup(repo_dir)
        assert not repo_dir.exists()
