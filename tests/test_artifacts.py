"""Tests for benchmarks.harness.artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.harness.artifacts import (
    create_artifact_dir,
    write_diff,
    write_prompt,
    write_run_record,
)
from benchmarks.harness.models import RunRecord, RunStatus, RunValidity, ValidationStatus, Variant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_record(run_id: str = "task1__baseline__20260331-120000") -> RunRecord:
    return RunRecord(
        run_id=run_id,
        task_id="task1",
        family="search",
        variant=Variant.baseline,
        agent_id="MockAdapter",
        adapter_version="unknown",
        repo_commit="abc123",
        status=RunStatus.passed,
        validity=RunValidity.valid,
        validation_status=ValidationStatus.passed,
        artifact_dir="",
        started_at=datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 31, 12, 0, 5, tzinfo=timezone.utc),
        elapsed_seconds=5.0,
    )


# ---------------------------------------------------------------------------
# create_artifact_dir
# ---------------------------------------------------------------------------


class TestCreateArtifactDir:
    def test_returns_path_under_results_dir(self, tmp_path: Path) -> None:
        artifact_dir = create_artifact_dir(tmp_path, "run-001")
        assert artifact_dir == tmp_path / "run-001"

    def test_creates_directory(self, tmp_path: Path) -> None:
        artifact_dir = create_artifact_dir(tmp_path, "run-001")
        assert artifact_dir.is_dir()

    def test_creates_nested_results_dir(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "deep" / "nested"
        artifact_dir = create_artifact_dir(results_dir, "run-abc")
        assert artifact_dir.is_dir()

    def test_idempotent_on_existing_directory(self, tmp_path: Path) -> None:
        """Calling twice with the same run_id should not raise."""
        create_artifact_dir(tmp_path, "run-001")
        artifact_dir = create_artifact_dir(tmp_path, "run-001")
        assert artifact_dir.is_dir()

    def test_run_id_used_as_subdirectory_name(self, tmp_path: Path) -> None:
        run_id = "my__task__20260101-000000"
        artifact_dir = create_artifact_dir(tmp_path, run_id)
        assert artifact_dir.name == run_id


# ---------------------------------------------------------------------------
# write_run_record
# ---------------------------------------------------------------------------


class TestWriteRunRecord:
    def test_creates_run_json(self, tmp_path: Path) -> None:
        record = _make_run_record()
        path = write_run_record(tmp_path, record)
        assert path == tmp_path / "run.json"
        assert path.exists()

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        record = _make_run_record()
        path = write_run_record(tmp_path, record)
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(obj, dict)

    def test_run_id_serialized_correctly(self, tmp_path: Path) -> None:
        record = _make_run_record(run_id="task1__baseline__20260331-120000")
        path = write_run_record(tmp_path, record)
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert obj["run_id"] == "task1__baseline__20260331-120000"

    def test_task_id_present(self, tmp_path: Path) -> None:
        record = _make_run_record()
        path = write_run_record(tmp_path, record)
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert obj["task_id"] == "task1"

    def test_status_serialized_as_string(self, tmp_path: Path) -> None:
        record = _make_run_record()
        path = write_run_record(tmp_path, record)
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert obj["status"] == "passed"

    def test_validity_serialized_as_string(self, tmp_path: Path) -> None:
        record = _make_run_record()
        path = write_run_record(tmp_path, record)
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert obj["validity"] == "valid"

    def test_optional_token_fields_null_when_absent(self, tmp_path: Path) -> None:
        record = _make_run_record()
        path = write_run_record(tmp_path, record)
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert obj["reported_input_tokens"] is None
        assert obj["reported_output_tokens"] is None
        assert obj["reported_total_tokens"] is None

    def test_token_fields_serialized_when_present(self, tmp_path: Path) -> None:
        record = _make_run_record()
        record.reported_input_tokens = 100
        record.reported_output_tokens = 200
        record.reported_total_tokens = 300
        path = write_run_record(tmp_path, record)
        obj = json.loads(path.read_text(encoding="utf-8"))
        assert obj["reported_input_tokens"] == 100
        assert obj["reported_output_tokens"] == 200
        assert obj["reported_total_tokens"] == 300


# ---------------------------------------------------------------------------
# write_prompt
# ---------------------------------------------------------------------------


class TestWritePrompt:
    def test_creates_prompt_txt(self, tmp_path: Path) -> None:
        path = write_prompt(tmp_path, "Hello agent")
        assert path == tmp_path / "prompt.txt"
        assert path.exists()

    def test_content_matches(self, tmp_path: Path) -> None:
        prompt = "Do the thing.\nUse ripgrep."
        path = write_prompt(tmp_path, prompt)
        assert path.read_text(encoding="utf-8") == prompt

    def test_empty_prompt(self, tmp_path: Path) -> None:
        path = write_prompt(tmp_path, "")
        assert path.read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# write_diff
# ---------------------------------------------------------------------------


class TestWriteDiff:
    def test_creates_diff_patch(self, tmp_path: Path) -> None:
        path = write_diff(tmp_path, "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n")
        assert path == tmp_path / "diff.patch"
        assert path.exists()

    def test_content_matches(self, tmp_path: Path) -> None:
        diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1,3 +1,3 @@\n-x = 1\n+x = 2\n"
        path = write_diff(tmp_path, diff)
        assert path.read_text(encoding="utf-8") == diff

    def test_empty_diff(self, tmp_path: Path) -> None:
        path = write_diff(tmp_path, "")
        assert path.read_text(encoding="utf-8") == ""
