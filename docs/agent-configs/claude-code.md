# Claude Code — Setup and CLAUDE.md Snippets for All 6 Tools

## Setup

**Install:**
```bash
npm install -g @anthropic-ai/claude-code
# or: download from https://claude.ai/code
```

**Verify:**
```bash
claude --version
claude -p "hello" --output-format json
```

**How CLAUDE.md works:**  
Claude Code reads `CLAUDE.md` at the start of every session. Paste tool snippets into your project's `CLAUDE.md` (or `~/.claude/CLAUDE.md` for global config) and Claude will follow the rules automatically — no need to instruct it per-prompt.

Create or open the file:
```bash
# Project-level (checked into the repo)
touch CLAUDE.md

# Global (applies to all projects)
touch ~/.claude/CLAUDE.md
```

Then paste any of the sections below.

---

## Tool setup

Some tools need one-time or per-project setup before Claude Code can use them.

### qmd — index your codebase first

`qmd get` looks up line ranges from a named collection. You must register your project and build the index before any `qmd get` calls will work:

```bash
# Add your project as a named collection (once per codebase)
qmd collection add /path/to/your/project --name my-project

# Build the index
qmd update

# Verify
qmd collection list
```

The index lives in `~/.cache/qmd/index.sqlite`. Rerun `qmd update` after large file changes. To restrict indexing to specific file types:

```bash
sqlite3 ~/.cache/qmd/index.sqlite \
  "UPDATE store_collections SET pattern='**/*.{java,ts,py}' WHERE name='my-project';"
qmd update
```

### rtk — configure the Claude Code hook

rtk works transparently in Claude Code via a `PreToolUse` hook that intercepts Bash calls and rewrites them through rtk automatically. Without the hook, you'd call `rtk <cmd>` explicitly every time.

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "rtk hook"
          }
        ]
      }
    ]
  }
}
```

After adding the hook, `git status` becomes `rtk git status` automatically — no prompt or CLAUDE.md changes needed. Verify with:

```bash
rtk gain          # should show token savings accumulating
rtk gain --history
```

The other four tools (ripgrep, ast-grep, comby, fastmod) need only be on `PATH` — no additional setup required.

---

## qmd

**Usage**: Retrieve an exact passage from a source file by line range (99.2% token reduction).

```bash
qmd get <file>:<line> -l <count>   # read N lines starting at line
qmd get src/main/App.java:120 -l 30
```

**When Claude should use this automatically:**
- Any time you know the file and approximate line number
- Before asking Claude to read a function — find the line with `rg -n` first, then `qmd get`
- Never read a whole file when you only need one function

**Expected output**: The exact source lines requested, nothing else. No surrounding context, no file header.

---

## ripgrep

**Usage**: Find files containing a pattern before reading them (95.4% token reduction).

```bash
rg -l <pattern> .              # list files containing pattern
rg -n <pattern> <file>         # find exact line number in a file
rg --type java <pattern> .     # restrict to file type
```

**When Claude should use this automatically:**
- Before reading any directory to find a file — always run ripgrep first
- Before using `qmd get` — use `rg -n` to find the exact line number
- Never use `find . -name` or directory listings to locate a file by content

**Expected output**: For `-l`: one file path per line. For `-n`: `<file>:<line>:<match>` per line.

---

## rtk

**Usage**: Token-optimized CLI proxy (94.7% token reduction on directory listings).

```bash
rtk ls <dir>                   # compact directory listing
rtk gain                       # show token savings analytics
rtk gain --history             # show command usage history
rtk discover                   # find missed opportunities in Claude Code history
rtk proxy <cmd>                # execute raw command without filtering (debug)
```

**When Claude should use this automatically:**
- Any time you need to understand a directory's structure — use `rtk ls` not `ls -la -R`
- Automatically via the Claude Code hook: `git status` → `rtk git status` (transparent)

**Expected output**: A compact listing with only essential fields. No inode numbers, no timestamps unless requested.

⚠️ **Name collision**: If `rtk gain` fails with an unexpected error, you may have `reachingforthejack/rtk` (Rust Type Kit) installed instead. Verify with `which rtk` and `rtk --version`.

---

## ast-grep

**Usage**: AST-aware search and structural rewrite (93.3% token reduction).

```bash
ast-grep run --pattern '<pattern>' --lang <lang> .          # search
ast-grep run --pattern '<old>' --rewrite '<new>' --lang <lang> -U .  # rewrite
```

**When Claude should use this automatically:**
- Renaming a method, function call, or expression across a codebase
- When fastmod would match inside comments or strings (wrong)
- Supported languages: Java, TypeScript, JavaScript, Python, Go, Rust, C, C++

**Expected output**: Matched file paths with line numbers (search), or diff of rewrites (with `-U`).

**When NOT to use ast-grep:**
- Renaming a bare identifier across config files, YAML, or plain strings → use fastmod
- The pattern is not a valid syntax fragment in the target language

---

## comby

**Usage**: Structural code rewriting with template holes (83.6% token reduction).

```bash
comby '<pattern>' '<replacement>' .<ext> -matcher .<ext>
comby '<pattern>' '<replacement>' .<ext> -diff -matcher .<ext>   # preview only
```

**When Claude should use this automatically:**
- The rewrite involves a call pattern where arguments vary: `foo(:[args])` → `bar(:[args])`
- The target is too complex for fastmod but ast-grep's exact AST is too rigid
- Use `:[hole]` syntax to match arbitrary expressions within a structural template

**Expected output**: Modified files in place (default), or a unified diff with `-diff`.

**When NOT to use comby:**
- Simple literal string rename → use fastmod
- Rename a specific method call with no argument variation → use ast-grep

---

## fastmod

**Usage**: Fast literal string replacement across a codebase (65.1% token reduction).

```bash
fastmod --accept-all --fixed-strings <old> <new> -e <ext> .
fastmod --accept-all --fixed-strings old_name new_name -e java,yaml .
```

**When Claude should use this automatically:**
- Renaming a config key, underscore identifier, or any literal string across many files
- When the text to replace is not a syntax expression (no method calls, no parentheses)
- Use `--fixed-strings` to disable regex interpretation; use `-e` to restrict by extension

**Expected output**: Number of replacements made, list of modified files.

**When NOT to use fastmod:**
- Renaming a method call or expression → use ast-grep
- The pattern has structural variation (different argument shapes) → use comby
