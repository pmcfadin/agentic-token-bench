# Gemini CLI — stream-json Token Reporting and Tool Config

Gemini CLI streams JSON events to stdout when run with `--output-format stream-json`. This guide covers how token counts are reported, the edge case when the result line is absent (see [#46](https://github.com/pmcfadin/agentic-token-bench/issues/46)), and how to configure tool access.

## Invocation flags

The benchmark harness invokes Gemini CLI as:

```bash
gemini -p "<prompt>" --output-format stream-json
```

- `--output-format stream-json`: Emits one JSON object per line as events arrive
- `-p "<prompt>"`: Non-interactive prompt mode

---

## Token count extraction

### Primary path: result line

The final line of `stream-json` output is a `{"type":"result",...}` object containing a `stats` block:

```json
{
  "type": "result",
  "content": "...",
  "stats": {
    "total_tokens": 836,
    "input_tokens": 788,
    "output_tokens": 48
  }
}
```

Extract `stats.total_tokens` for the session total. This is the authoritative count.

To extract from a completed run:
```bash
gemini -p "your prompt" --output-format stream-json \
  | tail -1 \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['stats']['total_tokens'])"
```

### Fallback path: sum message events (issue #46)

If the result line is absent — which can happen when the session times out, when the process is interrupted, or in certain error conditions — fall back to summing `input_tokens` + `output_tokens` from individual message events:

```bash
gemini -p "your prompt" --output-format stream-json > output.jsonl

# Primary: try the result line
python3 -c "
import sys, json
lines = open('output.jsonl').readlines()
for line in reversed(lines):
    try:
        d = json.loads(line.strip())
        if d.get('type') == 'result' and 'stats' in d:
            print(d['stats']['total_tokens'])
            sys.exit(0)
    except Exception:
        pass

# Fallback: sum message events
total = 0
for line in lines:
    try:
        d = json.loads(line.strip())
        usage = d.get('usage') or d.get('stats') or {}
        total += usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
    except Exception:
        pass
print(total)
"
```

> **Note on #46**: Runs where neither the result line nor message-event sums are available are marked invalid and excluded from the benchmark scorecard. The `token_evidence.txt` artifact records the raw extraction attempt for inspection.

---

## Putting tools on PATH

Gemini CLI resolves binaries from the shell's `PATH`. Same approach as Codex:

```bash
export PATH="/opt/homebrew/bin:$HOME/.cargo/bin:$PATH"
gemini -p "<prompt>" --output-format stream-json
```

---

## System prompt for tool preference

Gemini CLI does not have a `--system-prompt` flag in the same way as Codex. Embed routing instructions directly in your prompt:

```bash
gemini --output-format stream-json -p "
System: Before reading files, run rg -l <pattern> . to find relevant files.
Use qmd get <file>:<line> -l <count> to read specific passages, not full files.
For literal renames: fastmod --accept-all --fixed-strings <old> <new> -e <ext> .

Task: Find all files referencing read_repair_chance and show me the implementation.
"
```

Or use a prompt file for reuse:

```bash
cat > system.txt << 'EOF'
Before reading files, run `rg -l <pattern> .` to find relevant files.
Use `qmd get <file>:<line> -l <count>` to read specific passages, not full files.
Use `rtk ls <dir>` for directory listings, not recursive find.
For literal string renames: `fastmod --accept-all --fixed-strings <old> <new> -e <ext> .`
For method renames: `ast-grep run --pattern '<old>' --rewrite '<new>' --lang <lang> -U .`
EOF

gemini --output-format stream-json -p "$(cat system.txt)

Task: Find all files referencing read_repair_chance and show me the implementation."
```

---

## Minimal working example

```bash
export PATH="/opt/homebrew/bin:$HOME/.cargo/bin:$PATH"

gemini --output-format stream-json -p "
Use rg -l to find files, qmd get to read passages.

Find which files implement read repair in this Cassandra checkout, then show me the core logic.
" | tee run.jsonl

# Extract token count
tail -1 run.jsonl | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stats',{}).get('total_tokens','(no result line)'))"
```

With `rg` and `qmd` on PATH and the routing instructions above, Gemini will search first (48 tokens), then read only the relevant passage (188 tokens), rather than reading the full directory.
