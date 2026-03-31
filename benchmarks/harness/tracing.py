"""benchmarks.harness.tracing — event writing and trace normalization.

See docs/plans/2026-03-31-v1-build-plan-design.md for responsibilities.
"""

import dataclasses
import json
import threading
from datetime import datetime
from pathlib import Path

from benchmarks.harness.models import EventRecord
from tools.base import InvocationRecord


class EventWriter:
    """Thread-safe writer that appends EventRecord objects as JSONL lines.

    Each call to ``write_event`` serialises the record to JSON and appends it
    as a single line to the file at ``trace_path``.  Parent directories are
    created automatically if they do not exist.
    """

    def __init__(self, trace_path: Path) -> None:
        self._path = trace_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def write_event(self, event: EventRecord) -> None:
        """Serialize *event* and append it as a JSON line."""
        line = event.model_dump_json() + "\n"
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line)

    def flush(self) -> None:
        """Ensure all previously written events are on disk.

        Because each ``write_event`` call opens the file, writes, and closes
        it, data is already flushed after every write.  This method exists as
        an explicit API hook for callers that need a guaranteed flush point.
        """


def read_trace(path: Path) -> list[EventRecord]:
    """Read a JSONL trace file and return a list of EventRecord objects.

    Lines that are empty or consist only of whitespace are skipped.
    """
    records: list[EventRecord] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(EventRecord.model_validate_json(stripped))
    return records


def _serialize_invocation(record: InvocationRecord) -> str:
    """Serialize an InvocationRecord to a JSON string, handling datetime fields."""

    def _default(obj: object) -> str:
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    return json.dumps(dataclasses.asdict(record), default=_default)


class InvocationWriter:
    """Thread-safe writer that appends InvocationRecord objects as JSONL lines.

    Each call to ``write_invocation`` serialises the record to JSON and appends
    it as a single line to the file at ``invocations_path``.  Parent directories
    are created automatically if they do not exist.
    """

    def __init__(self, invocations_path: Path) -> None:
        self._path = invocations_path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def write_invocation(self, record: InvocationRecord) -> None:
        """Serialize *record* and append it as a JSON line."""
        line = _serialize_invocation(record) + "\n"
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line)


def read_invocations(path: Path) -> list[dict]:
    """Read a JSONL invocations file and return a list of dicts.

    Lines that are empty or consist only of whitespace are skipped.
    """
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records
