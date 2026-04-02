# Codex — PATH Config and System Prompt for Token-Saving Tools

Codex runs in `--full-auto` mode with a PATH-filtered environment. Tool availability is enforced by what's on `PATH` at invocation time, not by system prompt alone. This guide covers both how to put the tools on PATH and what system prompt lines route the agent to use them.

## Invocation flags

The benchmark harness invokes Codex as:

```bash
codex exec --full-auto --json --ephemeral --skip-git-repo-check -p "<prompt>"
```

- `--full-auto`: No human-in-the-loop confirmations
- `--json`: Structured output with per-turn `usage` data for token counting
- `--ephemeral`: Isolates the run; does not persist session state
- `--skip-git-repo-check`: Allows running outside a git repo

---

## Putting tools on PATH

Codex resolves binaries from `PATH` at the time of invocation. The simplest approach:

```bash
# Verify each tool is installed and discoverable
which qmd rg rtk ast-grep comby fastmod

# If any are missing from PATH, add their bin directories explicitly:
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.cargo/bin:$PATH"

# Then invoke Codex
codex exec --full-auto --json --ephemeral --skip-git-repo-check -p "<prompt>"
```

For project-level repeatability, add a wrapper script:

```bash
#!/usr/bin/env bash
# run-codex.sh — ensures all token-saving tools are on PATH
export PATH="/opt/homebrew/bin:$HOME/.cargo/bin:$PATH"
exec codex exec --full-auto --json --ephemeral --skip-git-repo-check "$@"
```

### Install locations by tool and installer

| Tool | Homebrew | Cargo | npm |
|------|----------|-------|-----|
| qmd | `/opt/homebrew/bin/qmd` | `~/.cargo/bin/qmd` | — |
| ripgrep (`rg`) | `/opt/homebrew/bin/rg` | `~/.cargo/bin/rg` | — |
| rtk | — | `~/.cargo/bin/rtk` | — |
| ast-grep (`sg`) | `/opt/homebrew/bin/sg` | `~/.cargo/bin/sg` | `node_modules/.bin/sg` |
| comby | `/opt/homebrew/bin/comby` | — | — |
| fastmod | `/opt/homebrew/bin/fastmod` | `~/.cargo/bin/fastmod` | — |

---

## System prompt lines

Add these lines to your Codex system prompt (via `--system-prompt` or your Codex configuration) to route common tasks to CLI tools instead of agent-generated code:

```
# File and directory search
Before reading any directory, run `rg -l <pattern> .` to find relevant files.
Use `rtk ls <dir>` instead of recursive find or ls to explore directory structure.
Never read an entire file to find one function — use `rg -n <pattern> <file>` to locate the line, then `qmd get <file>:<line> -l <count>`.

# Code rewrites
For literal string renames: fastmod --accept-all --fixed-strings <old> <new> -e <ext> .
For method/expression renames: ast-grep run --pattern '<old>' --rewrite '<new>' --lang <lang> -U .
For structural rewrites with argument variation: comby '<pattern>' '<replacement>' .<ext> -matcher .<ext>
```

---

## Token count extraction

With `--json`, Codex emits structured JSON events. Token counts appear in per-turn `usage` objects:

```json
{
  "type": "message",
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 56
  }
}
```

Sum `input_tokens` + `output_tokens` across all message events for the total session token count.

---

## Minimal working example

```bash
export PATH="/opt/homebrew/bin:$HOME/.cargo/bin:$PATH"

codex exec \
  --full-auto \
  --json \
  --ephemeral \
  --skip-git-repo-check \
  -p "Find all files referencing read_repair_chance, then show me the implementation in the most relevant file"
```

With `rg` on PATH and the system prompt above, Codex will run `rg -l read_repair_chance .` first (48 tokens returned), then use `qmd get` to read the relevant passage (188 tokens), rather than reading every file in the directory (~24,000 tokens each).
