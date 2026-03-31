"""Tests for InvocationWriter and read_invocations in benchmarks.harness.tracing."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from tools.base import InvocationRecord
from benchmarks.harness.tracing import InvocationWriter, read_invocations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    tool_id: str = "ripgrep",
    args_hash: str = "deadbeef",
    exit_status: int = 0,
    duration_ms: float = 5.0,
    step_id: str = "step-1",
    run_id: str = "run-001",
    timestamp: datetime | None = None,
) -> InvocationRecord:
    return InvocationRecord(
        tool_id=tool_id,
        timestamp=timestamp or datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        args_hash=args_hash,
        exit_status=exit_status,
        duration_ms=duration_ms,
        step_id=step_id,
        run_id=run_id,
    )


# ---------------------------------------------------------------------------
# InvocationWriter — single write
# ---------------------------------------------------------------------------


class TestInvocationWriterSingle:
    def test_write_single_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        writer.write_invocation(_make_record())
        assert path.exists()

    def test_write_single_and_read_back(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        record = _make_record(tool_id="fd", args_hash="abc123", run_id="run-x")
        writer = InvocationWriter(path)
        writer.write_invocation(record)

        records = read_invocations(path)
        assert len(records) == 1
        r = records[0]
        assert r["tool_id"] == "fd"
        assert r["args_hash"] == "abc123"
        assert r["run_id"] == "run-x"

    def test_all_fields_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        ts = datetime(2026, 1, 15, 8, 30, 0, tzinfo=timezone.utc)
        record = _make_record(
            tool_id="ripgrep",
            args_hash="ffff0000",
            exit_status=1,
            duration_ms=42.5,
            step_id="step-99",
            run_id="run-xyz",
            timestamp=ts,
        )
        writer = InvocationWriter(path)
        writer.write_invocation(record)

        records = read_invocations(path)
        assert len(records) == 1
        r = records[0]
        assert r["tool_id"] == "ripgrep"
        assert r["args_hash"] == "ffff0000"
        assert r["exit_status"] == 1
        assert r["duration_ms"] == 42.5
        assert r["step_id"] == "step-99"
        assert r["run_id"] == "run-xyz"
        # timestamp is serialized as ISO 8601 string
        assert r["timestamp"] == ts.isoformat()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "deep" / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        writer.write_invocation(_make_record())
        assert path.exists()


# ---------------------------------------------------------------------------
# InvocationWriter — multiple writes
# ---------------------------------------------------------------------------


class TestInvocationWriterMultiple:
    def test_write_multiple_preserves_order(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        records = [
            _make_record(tool_id="tool-a", step_id="step-1"),
            _make_record(tool_id="tool-b", step_id="step-2"),
            _make_record(tool_id="tool-c", step_id="step-3"),
        ]
        for r in records:
            writer.write_invocation(r)

        read_back = read_invocations(path)
        assert len(read_back) == 3
        for original, r in zip(records, read_back):
            assert r["tool_id"] == original.tool_id
            assert r["step_id"] == original.step_id

    def test_write_multiple_exit_statuses(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        for status in (0, 1, 2):
            writer.write_invocation(_make_record(exit_status=status))

        read_back = read_invocations(path)
        assert len(read_back) == 3
        assert [r["exit_status"] for r in read_back] == [0, 1, 2]


# ---------------------------------------------------------------------------
# JSONL format verification
# ---------------------------------------------------------------------------


class TestJsonlFormat:
    def test_one_json_object_per_line(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        for i in range(4):
            writer.write_invocation(_make_record(run_id=f"run-{i}"))

        raw_lines = path.read_text(encoding="utf-8").splitlines()
        non_empty = [ln for ln in raw_lines if ln.strip()]
        assert len(non_empty) == 4
        for line in non_empty:
            obj = json.loads(line)
            assert isinstance(obj, dict)

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        writer.write_invocation(_make_record())
        writer.write_invocation(_make_record(exit_status=1))

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)  # must not raise

    def test_each_line_contains_expected_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        writer.write_invocation(_make_record())

        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 1
        obj = json.loads(lines[0])
        for key in ("tool_id", "timestamp", "args_hash", "exit_status", "duration_ms", "step_id", "run_id"):
            assert key in obj

    def test_datetime_serialized_as_string(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        writer.write_invocation(_make_record())

        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        obj = json.loads(lines[0])
        assert isinstance(obj["timestamp"], str)


# ---------------------------------------------------------------------------
# read_invocations
# ---------------------------------------------------------------------------


class TestReadInvocations:
    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        path.write_text("", encoding="utf-8")
        assert read_invocations(path) == []

    def test_returns_list_of_dicts(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        writer.write_invocation(_make_record())
        result = read_invocations(path)
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        writer.write_invocation(_make_record())
        # Inject a blank line into the file
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n")
        writer.write_invocation(_make_record(tool_id="second-tool"))

        result = read_invocations(path)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Thread-safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_writes_produce_correct_line_count(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)
        n_threads = 10
        records_per_thread = 20

        def write_records(thread_id: int) -> None:
            for i in range(records_per_thread):
                writer.write_invocation(
                    _make_record(run_id=f"thread-{thread_id}", step_id=f"step-{i}")
                )

        threads = [
            threading.Thread(target=write_records, args=(t,)) for t in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        result = read_invocations(path)
        assert len(result) == n_threads * records_per_thread

    def test_concurrent_writes_produce_valid_json_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "tool_invocations.jsonl"
        writer = InvocationWriter(path)

        def write_batch(thread_id: int) -> None:
            for _ in range(5):
                writer.write_invocation(_make_record(run_id=f"t{thread_id}"))

        threads = [
            threading.Thread(target=write_batch, args=(i,)) for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)  # no interleaved partial lines
