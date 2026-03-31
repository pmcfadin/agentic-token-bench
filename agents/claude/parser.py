"""Claude output parser.

Parses the JSON output produced by ``claude -p ... --output-format json``.

The JSON schema (from observed output) contains a top-level ``usage`` object
with fields ``input_tokens``, ``output_tokens``, and optional cache fields.
Total tokens is computed as input + output.

Example (abbreviated)::

    {
        "type": "result",
        "subtype": "success",
        "result": "...",
        "usage": {
            "input_tokens": 3,
            "cache_creation_input_tokens": 12447,
            "cache_read_input_tokens": 6561,
            "output_tokens": 4
        }
    }
"""

from __future__ import annotations

import json


def parse_claude_json_output(output: str) -> dict:
    """Parse Claude's JSON output format into a Python dict.

    Args:
        output: Raw stdout string from ``claude --output-format json``.

    Returns:
        Parsed dict.  Returns an empty dict if ``output`` is empty or not
        valid JSON.
    """
    output = output.strip()
    if not output:
        return {}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {}


def extract_tokens_from_output(output: str) -> tuple[int, int, int, str]:
    """Extract token counts from Claude JSON output.

    Reads ``usage.input_tokens`` and ``usage.output_tokens`` from the parsed
    JSON.  Total tokens is ``input + output``.  Cache tokens are NOT counted
    as part of the reported totals because they are auxiliary billing metadata,
    not the primary I/O token counts.

    Args:
        output: Raw stdout string from ``claude --output-format json``.

    Returns:
        A four-tuple ``(input_tokens, output_tokens, total_tokens, evidence)``.
        All counts are 0 and ``evidence`` is an empty string when the token
        block cannot be found.
    """
    data = parse_claude_json_output(output)
    usage = data.get("usage", {})

    input_tokens = int(usage.get("input_tokens", 0))
    output_tokens = int(usage.get("output_tokens", 0))
    total_tokens = input_tokens + output_tokens

    if not usage:
        return 0, 0, 0, ""

    # Build a concise evidence snippet from the raw usage block.
    evidence = json.dumps(usage)
    return input_tokens, output_tokens, total_tokens, evidence
