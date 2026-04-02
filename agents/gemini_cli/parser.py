"""gemini_cli output parser.

Parses the stream-json output produced by:
    gemini -p "..." --output-format stream-json

The final line of a successful run has the form:
    {"type":"result","status":"success","stats":{"total_tokens":N,"input_tokens":N,"output_tokens":N,...}}
"""

import json
import re


def parse_gemini_output(output: str) -> dict:
    """Parse gemini CLI output and return a structured dictionary.

    Handles both stream-json (structured) and plain text output.

    Args:
        output: Raw stdout captured from the gemini process.

    Returns:
        Dictionary with keys:
            - ``content``: Concatenated assistant message content (str).
            - ``stats``: Stats dict from the result line, or empty dict.
            - ``status``: ``"success"``, ``"error"``, or ``"unknown"``.
            - ``result_line``: The raw result JSON line, or empty string.
    """
    result: dict = {
        "content": "",
        "stats": {},
        "status": "unknown",
        "result_line": "",
        "has_result_line": False,
    }

    content_parts: list[str] = []
    result_line_raw = ""

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Plain text line – treat as content.
            content_parts.append(raw_line)
            continue

        msg_type = obj.get("type", "")
        if msg_type == "message" and obj.get("role") == "assistant":
            content_parts.append(obj.get("content", ""))
        elif msg_type == "result":
            result["status"] = obj.get("status", "unknown")
            result["stats"] = obj.get("stats", {})
            result_line_raw = line
            result["has_result_line"] = True

    result["content"] = "".join(content_parts)
    result["result_line"] = result_line_raw
    return result


def extract_tokens_from_output(output: str) -> tuple[int, int, int, str]:
    """Extract token counts from gemini CLI output.

    Tries stream-json structured parsing first; falls back to regex patterns
    for plain text output.

    Args:
        output: Raw stdout captured from the gemini process.

    Returns:
        A 4-tuple of ``(input_tokens, output_tokens, total_tokens, evidence_snippet)``.
        All counts are 0 and evidence_snippet is empty string when not found.
    """
    parsed = parse_gemini_output(output)
    stats = parsed.get("stats", {})

    if stats:
        input_tokens = int(stats.get("input_tokens", 0))
        output_tokens = int(stats.get("output_tokens", 0))
        total_tokens = int(stats.get("total_tokens", 0))
        evidence = parsed.get("result_line", "")
        if input_tokens or output_tokens or total_tokens:
            return input_tokens, output_tokens, total_tokens, evidence

    # Fallback: try plain-text patterns like "Tokens: input=N output=N total=N"
    pattern = re.compile(
        r"input[_\s]*tokens?[:\s=]+(\d+).*?output[_\s]*tokens?[:\s=]+(\d+).*?total[_\s]*tokens?[:\s=]+(\d+)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(output)
    if m:
        inp, out, tot = int(m.group(1)), int(m.group(2)), int(m.group(3))
        evidence = m.group(0)
        return inp, out, tot, evidence

    return 0, 0, 0, ""
