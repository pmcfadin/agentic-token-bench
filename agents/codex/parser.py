"""codex output parser.

Handles two output modes emitted by ``codex exec``:
  1. JSON Lines (``--json`` flag): each line is a JSON object; token counts
     appear in the ``turn.completed`` event's ``usage`` field.
  2. Plain text (default): a ``tokens used`` section containing a formatted
     integer appears somewhere in the output.

The parser tries JSON Lines first and falls back to plain-text extraction.
"""

from __future__ import annotations

import json
import re


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def parse_codex_output(output: str) -> dict:
    """Parse codex output into a structured dictionary.

    Tries to detect JSON Lines mode first.  Falls back to plain-text parsing.

    Args:
        output: Raw stdout (or combined stdout+stderr) from a ``codex exec``
            invocation.

    Returns:
        A dict with at least these keys:
            ``mode``         – ``"json"`` or ``"plaintext"``
            ``input_tokens`` – int or None
            ``output_tokens`` – int or None
            ``total_tokens`` – int or None
            ``cached_input_tokens`` – int or None
            ``evidence_snippet`` – str or None
            ``events``       – list[dict] (JSON mode only, else [])
            ``agent_text``   – combined agent message text (str)
    """
    if _looks_like_jsonl(output):
        return _parse_jsonl(output)
    return _parse_plaintext(output)


def extract_tokens_from_output(output: str) -> tuple[int, int, int, str]:
    """Extract input, output, total token counts and an evidence snippet.

    Args:
        output: Raw output string from a ``codex exec`` invocation.

    Returns:
        A 4-tuple of ``(input_tokens, output_tokens, total_tokens,
        evidence_snippet)``.  All token counts are 0 when not found.
        ``evidence_snippet`` is the raw text that contained the counts,
        or an empty string when nothing was found.

    Raises:
        ValueError: If token information is completely absent from the output.
    """
    parsed = parse_codex_output(output)
    inp = parsed.get("input_tokens") or 0
    out = parsed.get("output_tokens") or 0
    total = parsed.get("total_tokens") or 0
    snippet = parsed.get("evidence_snippet") or ""

    if inp == 0 and out == 0 and total == 0:
        raise ValueError(
            "No token counts found in codex output. "
            "Pass --json flag or ensure the run completed successfully."
        )

    return inp, out, total, snippet


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _looks_like_jsonl(output: str) -> bool:
    """Return True if *any* line in output is a valid JSON object."""
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                json.loads(line)
                return True
            except json.JSONDecodeError:
                continue
    return False


def _parse_jsonl(output: str) -> dict:
    """Parse JSON Lines output from ``codex exec --json``."""
    events: list[dict] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            events.append(obj)
        except json.JSONDecodeError:
            # Skip non-JSON lines (e.g. ANSI escape sequences on first boot)
            continue

    # Locate ``turn.completed`` events — the last one wins.
    usage: dict | None = None
    evidence_snippet: str = ""
    for event in reversed(events):
        if event.get("type") == "turn.completed" and "usage" in event:
            usage = event["usage"]
            evidence_snippet = json.dumps(event)
            break

    # Collect agent message text from ``item.completed`` events.
    agent_text_parts: list[str] = []
    for event in events:
        if (
            event.get("type") == "item.completed"
            and isinstance(event.get("item"), dict)
            and event["item"].get("type") == "agent_message"
        ):
            text = event["item"].get("text", "")
            if text:
                agent_text_parts.append(text)

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached: int | None = None

    if usage is not None:
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        cached = usage.get("cached_input_tokens")
        # total_tokens may not be explicit; derive it when absent.
        if "total_tokens" in usage:
            total_tokens = usage["total_tokens"]
        elif input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

    return {
        "mode": "json",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_input_tokens": cached,
        "evidence_snippet": evidence_snippet,
        "events": events,
        "agent_text": "\n".join(agent_text_parts),
    }


def _parse_plaintext(output: str) -> dict:
    """Parse plain-text output from ``codex exec`` (no ``--json`` flag).

    Codex plain-text output contains a ``tokens used`` section followed by a
    formatted integer on the next non-empty line, e.g.::

        tokens used
        9,428
        hello

    We extract that total count and set input/output to 0 since the
    plain-text format does not break them out.
    """
    total_tokens: int | None = None
    evidence_snippet: str = ""

    lines = output.splitlines()
    for idx, line in enumerate(lines):
        # Detect the "tokens used" label (case-insensitive).
        if re.search(r"tokens?\s+used", line, re.IGNORECASE):
            # The number appears on the next non-empty line.
            for candidate in lines[idx + 1 :]:
                candidate = candidate.strip()
                if candidate:
                    # Remove locale-formatted commas/dots and parse.
                    clean = re.sub(r"[,_\s]", "", candidate)
                    if re.fullmatch(r"\d+", clean):
                        total_tokens = int(clean)
                        evidence_snippet = f"{line.strip()}\n{candidate}"
                    break
            if total_tokens is not None:
                break

    # Collect agent text: lines after the final "codex" speaker label,
    # excluding the token summary block.
    agent_text = _extract_plaintext_agent_text(output)

    return {
        "mode": "plaintext",
        "input_tokens": 0 if total_tokens is not None else None,
        "output_tokens": 0 if total_tokens is not None else None,
        "total_tokens": total_tokens,
        "cached_input_tokens": None,
        "evidence_snippet": evidence_snippet or None,
        "events": [],
        "agent_text": agent_text,
    }


def _extract_plaintext_agent_text(output: str) -> str:
    """Return the agent response text from plain-text codex output."""
    # Find the last "codex\n<content>" block and take what follows.
    match = re.search(r"^codex\s*$", output, re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""
    after = output[match.end() :]
    # Strip the "tokens used\n<number>" trailer.
    trailer = re.search(r"tokens?\s+used", after, re.IGNORECASE)
    if trailer:
        after = after[: trailer.start()]
    return after.strip()
