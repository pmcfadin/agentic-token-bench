"""benchmarks.harness.tracing — event writing and trace normalization.

See docs/plans/2026-03-31-v1-build-plan-design.md for responsibilities.
"""

import threading
from pathlib import Path

from benchmarks.harness.models import EventRecord


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
