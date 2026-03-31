"""Tests for benchmarks.harness.tracing — EventWriter and read_trace."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from benchmarks.harness.models import EventRecord
from benchmarks.harness.tracing import EventWriter, read_trace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "event.schema.json"


def _load_schema() -> dict:
    with _SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _make_event(
    run_id: str = "run-001",
    step_id: str = "discover",
    event_type: str = "step_started",
    actor: str = "harness",
    payload: dict | None = None,
) -> EventRecord:
    return EventRecord(
        timestamp=datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        run_id=run_id,
        step_id=step_id,
        event_type=event_type,
        actor=actor,
        payload=payload or {},
    )


# ---------------------------------------------------------------------------
# EventWriter tests
# ---------------------------------------------------------------------------


class TestEventWriter:
    def test_write_single_event_creates_file(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        writer = EventWriter(trace)
        writer.write_event(_make_event())
        assert trace.exists()

    def test_write_single_event_and_read_back(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        event = _make_event(run_id="run-abc", event_type="tool_called", actor="agent")
        writer = EventWriter(trace)
        writer.write_event(event)

        records = read_trace(trace)
        assert len(records) == 1
        r = records[0]
        assert r.run_id == "run-abc"
        assert r.event_type == "tool_called"
        assert r.actor == "agent"

    def test_write_multiple_events_preserves_order(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        writer = EventWriter(trace)
        events = [
            _make_event(step_id="step-1", event_type="step_started"),
            _make_event(step_id="step-2", event_type="tool_called"),
            _make_event(step_id="step-3", event_type="step_finished"),
        ]
        for e in events:
            writer.write_event(e)

        records = read_trace(trace)
        assert len(records) == 3
        for original, read_back in zip(events, records):
            assert original.step_id == read_back.step_id
            assert original.event_type == read_back.event_type

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        trace = tmp_path / "nested" / "deep" / "trace.jsonl"
        writer = EventWriter(trace)
        writer.write_event(_make_event())
        assert trace.exists()

    def test_flush_is_callable(self, tmp_path: Path) -> None:
        """flush() must exist and be callable without raising."""
        writer = EventWriter(tmp_path / "trace.jsonl")
        writer.write_event(_make_event())
        writer.flush()  # should not raise

    def test_payload_round_trips(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        payload = {"tool": "ripgrep", "args": ["--json", "pattern"], "exit_code": 0}
        writer = EventWriter(trace)
        writer.write_event(_make_event(payload=payload))

        records = read_trace(trace)
        assert records[0].payload == payload


# ---------------------------------------------------------------------------
# JSONL format tests
# ---------------------------------------------------------------------------


class TestJsonlFormat:
    def test_one_json_object_per_line(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        writer = EventWriter(trace)
        for i in range(3):
            writer.write_event(_make_event(run_id=f"run-{i}"))

        raw_lines = trace.read_text(encoding="utf-8").splitlines()
        # Filter blank lines (there should be none, but be defensive)
        non_empty = [ln for ln in raw_lines if ln.strip()]
        assert len(non_empty) == 3
        for line in non_empty:
            obj = json.loads(line)
            assert isinstance(obj, dict)

    def test_each_line_is_valid_json(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        writer = EventWriter(trace)
        writer.write_event(_make_event())
        writer.write_event(_make_event(event_type="step_finished"))

        for line in trace.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)  # must not raise

    def test_events_validate_against_schema(self, tmp_path: Path) -> None:
        schema = _load_schema()
        trace = tmp_path / "trace.jsonl"
        writer = EventWriter(trace)
        events = [
            _make_event(event_type="step_started"),
            _make_event(event_type="tool_called", payload={"tool": "ripgrep"}),
            _make_event(event_type="step_finished"),
        ]
        for e in events:
            writer.write_event(e)

        for line in trace.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            jsonschema.validate(instance=obj, schema=schema)


# ---------------------------------------------------------------------------
# read_trace tests
# ---------------------------------------------------------------------------


class TestReadTrace:
    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        trace.write_text("", encoding="utf-8")
        assert read_trace(trace) == []

    def test_returns_event_record_objects(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        writer = EventWriter(trace)
        writer.write_event(_make_event())
        records = read_trace(trace)
        assert all(isinstance(r, EventRecord) for r in records)

    def test_timestamp_preserved(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        ts = datetime(2026, 1, 15, 8, 30, 0, tzinfo=timezone.utc)
        event = EventRecord(
            timestamp=ts,
            run_id="run-ts",
            step_id="s1",
            event_type="probe",
            actor="test",
        )
        writer = EventWriter(trace)
        writer.write_event(event)
        records = read_trace(trace)
        assert records[0].timestamp == ts


# ---------------------------------------------------------------------------
# Thread-safety test
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_writes_produce_correct_line_count(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        writer = EventWriter(trace)
        n_threads = 10
        events_per_thread = 20

        def write_events(thread_id: int) -> None:
            for i in range(events_per_thread):
                writer.write_event(
                    _make_event(run_id=f"thread-{thread_id}", step_id=f"step-{i}")
                )

        threads = [threading.Thread(target=write_events, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        records = read_trace(trace)
        assert len(records) == n_threads * events_per_thread

    def test_concurrent_writes_produce_valid_json_lines(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        writer = EventWriter(trace)

        def write_batch(thread_id: int) -> None:
            for _ in range(5):
                writer.write_event(_make_event(run_id=f"t{thread_id}"))

        threads = [threading.Thread(target=write_batch, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for line in trace.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)  # no interleaved partial lines
