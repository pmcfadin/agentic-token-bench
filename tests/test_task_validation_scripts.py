"""Tests for the cassandra-ripgrep-01 and cassandra-ripgrep-02 validation scripts.

These tests invoke the scripts via subprocess so the exit-code contract is
exercised exactly as the harness would exercise it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Absolute path to the scripts directory so tests work from any cwd.
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


def _run_script(script_name: str, task_id: str, artifact_dir: Path) -> subprocess.CompletedProcess:
    """Run a validation script and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / script_name), "--task", task_id, str(artifact_dir)],
        capture_output=True,
        text=True,
    )


def _write_answer(artifact_dir: Path, content: str) -> None:
    (artifact_dir / "final_answer.txt").write_text(content)


# ---------------------------------------------------------------------------
# cassandra-ripgrep-01 tests
# ---------------------------------------------------------------------------


class TestValidateCassandraRipgrep01:
    SCRIPT = "validate_cassandra_ripgrep_01.py"
    TASK = "cassandra-ripgrep-01"

    def test_full_pass_with_all_hints(self, tmp_path: Path) -> None:
        _write_answer(
            tmp_path,
            "source_path: src/java/org/apache/cassandra/service/ReadRepair.java\n"
            "config_path: conf/cassandra.yaml (key: read_repair_chance)\n"
            "test_path: test/unit/org/apache/cassandra/service/ReadRepairTest.java\n",
        )
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 0
        assert output["status"] == "pass"

    def test_partial_pass_missing_config(self, tmp_path: Path) -> None:
        _write_answer(
            tmp_path,
            "source_path: src/java/org/apache/cassandra/service/ReadRepair.java\n"
            "config_path: (unknown)\n"
            "test_path: test/unit/org/apache/cassandra/service/ReadRepairTest.java\n",
        )
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 2
        assert output["status"] == "partial"

    def test_fail_with_empty_answer(self, tmp_path: Path) -> None:
        _write_answer(tmp_path, "")
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 1
        assert output["status"] == "fail"

    def test_fail_when_final_answer_missing(self, tmp_path: Path) -> None:
        # Do not write final_answer.txt
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 1
        assert output["status"] == "fail"
        assert "final_answer.txt" in output["details"]["error"]

    def test_fail_with_wrong_task_id(self, tmp_path: Path) -> None:
        _write_answer(tmp_path, "irrelevant")
        result = _run_script(self.SCRIPT, "cassandra-ripgrep-99", tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 1
        assert output["status"] == "fail"

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        _write_answer(
            tmp_path,
            "source_path: src/java/org/apache/cassandra/service/ReadRepairTest.java\n",
        )
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        # Should not raise
        parsed = json.loads(result.stdout)
        assert "status" in parsed
        assert "details" in parsed


# ---------------------------------------------------------------------------
# cassandra-ripgrep-02 tests
# ---------------------------------------------------------------------------


class TestValidateCassandraRipgrep02:
    SCRIPT = "validate_cassandra_ripgrep_02.py"
    TASK = "cassandra-ripgrep-02"

    def _full_pass_answer(self) -> str:
        """Return an answer that should produce a full pass."""
        paths = [
            "src/java/org/apache/cassandra/db/compaction/SizeTieredCompactionStrategy.java",
            "src/java/org/apache/cassandra/db/compaction/SizeTieredCompactionStrategyOptions.java",
            "src/java/org/apache/cassandra/db/compaction/CompactionManager.java",
            "src/java/org/apache/cassandra/schema/TableParams.java",
            "test/unit/org/apache/cassandra/db/compaction/SizeTieredCompactionStrategyTest.java",
            "src/java/org/apache/cassandra/cql3/statements/schema/AlterTableStatement.java",
        ]
        return "reference_paths:\n" + "\n".join(f"  - {p}" for p in paths)

    def test_full_pass_with_all_required_paths(self, tmp_path: Path) -> None:
        _write_answer(tmp_path, self._full_pass_answer())
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 0
        assert output["status"] == "pass"

    def test_partial_pass_missing_options_file(self, tmp_path: Path) -> None:
        # Include the main strategy file but not the options class.
        answer = (
            "reference_paths:\n"
            "  - src/java/org/apache/cassandra/db/compaction/SizeTieredCompactionStrategy.java\n"
            "  - src/java/org/apache/cassandra/db/compaction/CompactionManager.java\n"
            "  - src/java/org/apache/cassandra/schema/TableParams.java\n"
            "  - test/unit/org/apache/cassandra/db/compaction/SizeTieredCompactionTest.java\n"
            "  - src/java/org/apache/cassandra/cql3/statements/schema/AlterTableStatement.java\n"
        )
        _write_answer(tmp_path, answer)
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 2
        assert output["status"] == "partial"

    def test_fail_with_false_positive_absolute_path(self, tmp_path: Path) -> None:
        _write_answer(
            tmp_path,
            "reference_paths:\n"
            "  - /Users/agent/cassandra/src/SizeTieredCompactionStrategy.java\n"
            "  - /Users/agent/cassandra/src/SizeTieredCompactionStrategyOptions.java\n",
        )
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 1
        assert output["status"] == "fail"

    def test_fail_with_empty_answer(self, tmp_path: Path) -> None:
        _write_answer(tmp_path, "")
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 1
        assert output["status"] == "fail"

    def test_fail_when_final_answer_missing(self, tmp_path: Path) -> None:
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 1
        assert output["status"] == "fail"
        assert "final_answer.txt" in output["details"]["error"]

    def test_fail_with_wrong_task_id(self, tmp_path: Path) -> None:
        _write_answer(tmp_path, "irrelevant")
        result = _run_script(self.SCRIPT, "cassandra-ripgrep-99", tmp_path)
        output = json.loads(result.stdout)
        assert result.returncode == 1
        assert output["status"] == "fail"

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        _write_answer(tmp_path, self._full_pass_answer())
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        parsed = json.loads(result.stdout)
        assert "status" in parsed
        assert "details" in parsed

    def test_details_include_path_count(self, tmp_path: Path) -> None:
        _write_answer(tmp_path, self._full_pass_answer())
        result = _run_script(self.SCRIPT, self.TASK, tmp_path)
        output = json.loads(result.stdout)
        assert "path_count" in output["details"]
        assert output["details"]["path_count"] >= 5
