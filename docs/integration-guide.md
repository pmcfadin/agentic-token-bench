# Integration Guide: Wiring Token-Saving Tools into Your Agent Workflow

## The Pattern

Every file read, search, or bulk edit in an AI coding session stuffs full content into the LLM's context — most of it noise. Run a deterministic CLI tool first and hand the agent only the result. The agent doesn't need a 24,000-token file to answer a question about one function; it needs the 188-token passage that contains the answer.

```
[Full file: 24,437 tokens]
         |
         v
  qmd get Gossiper.java:361 -l 24
         |
         v
[Exact passage: 188 tokens]   ← 99.2% reduction
```

The benchmark in this repo measures that reduction for six tools across real Apache Cassandra source. Token numbers below are sourced from [`benchmarks/results/benchmark-data.json`](../benchmarks/results/benchmark-data.json); regenerate with `task export-data`.

---

## Prerequisites

Install the tools you want to use:

```bash
# qmd — precision line-range extraction
brew install qmd           # macOS
cargo install qmd          # from source

# ripgrep — fast file search
brew install ripgrep       # macOS
apt install ripgrep        # Debian/Ubuntu
cargo install ripgrep      # from source

# rtk — token-optimized shell proxy
cargo install rtk          # from source
# or: see https://github.com/rtk-ai/rtk for binary releases

# ast-grep — AST-aware search and rewrite
brew install ast-grep      # macOS
npm install -g @ast-grep/cli  # Node.js
cargo install ast-grep     # from source

# comby — structural code rewriting
brew install comby         # macOS
# or: https://comby.dev/docs/get-started#install

# fastmod — fast, safe bulk text replacement
brew install fastmod       # macOS
cargo install fastmod      # from source
pip install fastmod        # Python
```

---

## Tools

### qmd — 99.2% token reduction

**Use case.** Retrieve an exact passage from a source file by line range, without reading the whole file.

**When to reach for qmd.** You know the file and approximate line number of the code you need. `qmd get` returns only that range — the LLM sees 188 tokens instead of 24,437. Use it for reading specific functions, class definitions, or config blocks.

**Token savings** (from `benchmark-data.json`):

| Metric | Value |
|--------|-------|
| Avg raw tokens | 24,437 |
| Avg reduced tokens | 188 |
| Reduction | **99.2%** |
| Deterministic pass rate | 100% |

**Copy-paste command:**
```bash
qmd get src/java/org/apache/cassandra/gms/Gossiper.java:361 -l 24
```

#### Claude Code

Add to your `CLAUDE.md`:

```markdown
## qmd

Use `qmd get <file>:<line> -l <count>` to read a specific passage from a file.
Never read an entire file to inspect one function — use qmd first.
If you know the file path and approximate line number, qmd is always the right call.

Example: `qmd get src/main/App.java:120 -l 30`
```

Example prompt that triggers it:
> "Show me the gossip target selection logic in Gossiper.java around line 361."

#### Codex

Add to your system prompt:
```
When reading source files, prefer `qmd get <file>:<line> -l <count>` over reading the full file.
Only read the full file if you do not know the relevant line range.
```

Ensure `qmd` is on PATH before invoking Codex:
```bash
export PATH="$(which qmd | xargs dirname):$PATH"
codex exec --full-auto --json --ephemeral --skip-git-repo-check \
  "Show me the gossip round logic in Gossiper.java"
```

#### Gemini CLI

```bash
gemini -p "Show me the gossip target selection in Gossiper.java" \
  --output-format stream-json
```

Token counts appear in the final `{"type":"result",...}` line under `stats.total_tokens`. If that line is absent (see [#46](https://github.com/pmcfadin/agentic-token-bench/issues/46)), sum `input_tokens` + `output_tokens` from individual message events.

Add the same system prompt line as Codex to instruct Gemini to prefer `qmd`.

---

### ripgrep — 95.4% token reduction

**Use case.** Find which files contain a pattern, without reading every file in the directory.

**When to reach for ripgrep.** You need to locate files before reading them. `rg -l <pattern>` returns a list of matching file paths — the LLM sees 48 tokens instead of 1,043. Use it as a mandatory pre-step before any directory-wide search.

**Token savings** (from `benchmark-data.json`):

| Metric | Value |
|--------|-------|
| Avg raw tokens | 1,043 |
| Avg reduced tokens | 48 |
| Reduction | **95.4%** |
| Deterministic pass rate | 100% |

**Copy-paste command:**
```bash
rg -l read_repair_chance .
```

#### Claude Code

Add to your `CLAUDE.md`:

```markdown
## ripgrep

Use `rg -l <pattern> .` to find files before reading them.
Never read an entire directory to find a file — run ripgrep first, then read only matched files.
Use `rg -n <pattern> <file>` to find the exact line before using qmd.

Examples:
- `rg -l DatabaseDescriptor .`       # find files containing a class
- `rg -n "getReadRepair" src/`       # find exact line for qmd
```

Example prompt that triggers it:
> "Which files reference read_repair_chance?"

#### Codex

Add to your system prompt:
```
Before reading any directory, run `rg -l <pattern> .` to find relevant files.
Never read an entire directory listing to locate a file.
```

Ensure `rg` is on PATH:
```bash
export PATH="$(which rg | xargs dirname):$PATH"
codex exec --full-auto --json --ephemeral --skip-git-repo-check \
  "Find all files that reference read_repair_chance"
```

#### Gemini CLI

```bash
gemini -p "Find files referencing read_repair_chance" \
  --output-format stream-json
```

Add the system prompt line from the Codex section. Token reporting follows the same stream-json pattern described under qmd.

---

### rtk — 94.7% token reduction

**Use case.** Get a compact directory listing that fits in context, rather than a verbose recursive dump.

**When to reach for rtk.** You need to understand a directory's structure before deciding what to read. `rtk ls` produces a token-optimized listing — the LLM sees 648 tokens instead of 12,284. Use it before any broad exploration of an unfamiliar package.

**Token savings** (from `benchmark-data.json`):

| Metric | Value |
|--------|-------|
| Avg raw tokens | 12,284 |
| Avg reduced tokens | 648 |
| Reduction | **94.7%** |
| Deterministic pass rate | 100% |

**Copy-paste command:**
```bash
rtk ls cassandra-db/
```

#### Claude Code

Add to your `CLAUDE.md`:

```markdown
## rtk

**Usage**: Token-optimized shell proxy. All standard commands are rewritten automatically via the Claude Code hook.

Use `rtk ls <dir>` explicitly when you need a compact directory listing.
Never use `find . -type f` or `ls -la -R` to explore a directory — use rtk ls instead.

Example: `rtk ls src/java/org/apache/cassandra/db/`

⚠️ **Name collision**: If `rtk gain` fails, you may have reachingforthejack/rtk (Rust Type Kit) installed instead. Verify with `which rtk`.
```

Example prompt that triggers it:
> "What's in the cassandra db package?"

#### Codex

Add to your system prompt:
```
Use `rtk ls <dir>` instead of recursive find or ls to explore directory structure.
Prefer token-optimized output over verbose listings.
```

Ensure `rtk` is on PATH:
```bash
export PATH="$(which rtk | xargs dirname):$PATH"
codex exec --full-auto --json --ephemeral --skip-git-repo-check \
  "Summarize the structure of the cassandra db package"
```

#### Gemini CLI

```bash
gemini -p "What's in the cassandra db package?" \
  --output-format stream-json
```

Same PATH and system prompt approach as Codex. Token reporting follows the stream-json pattern described under qmd.

---

### ast-grep — 93.3% token reduction

**Use case.** Rename or rewrite all call sites of a method with AST-aware precision, avoiding string-match false positives.

**When to reach for ast-grep.** You need to rename a method, update an API call, or find structural patterns across a codebase. Unlike `fastmod`, ast-grep understands syntax trees — it won't match a variable named `getReadRepairChance` inside a comment or string. Use it when the rewrite needs to be syntactically correct.

**Token savings** (from `benchmark-data.json`):

| Metric | Value |
|--------|-------|
| Avg raw tokens | 2,436 |
| Avg reduced tokens | 162 |
| Reduction | **93.3%** |
| Deterministic pass rate | 100% |

**Copy-paste command:**
```bash
ast-grep run --pattern 'DatabaseDescriptor.getReadRepairChance()' \
  --rewrite 'ReadRepairConfig.getChance()' --lang java -U .
```

#### Claude Code

Add to your `CLAUDE.md`:

```markdown
## ast-grep

Use `ast-grep run --pattern <pattern> --rewrite <replacement> --lang <lang> -U .`
for AST-aware method renames and structural rewrites.

Prefer over fastmod/sed when:
- The pattern is a method call or expression (not a bare string)
- False positives in comments or strings would be a problem
- The language is Java, TypeScript, Python, Go, Rust, or C/C++

Example: `ast-grep run --pattern 'foo.bar()' --rewrite 'foo.baz()' --lang java -U .`
```

Example prompt that triggers it:
> "Rename DatabaseDescriptor.getReadRepairChance() to ReadRepairConfig.getChance() across the codebase."

#### Codex

Add to your system prompt:
```
For method renames and API migrations, prefer `ast-grep run --pattern <old> --rewrite <new> --lang <lang> -U .`
over sed or fastmod when syntax precision matters.
```

Ensure `ast-grep` is on PATH:
```bash
export PATH="$(which ast-grep | xargs dirname):$PATH"
codex exec --full-auto --json --ephemeral --skip-git-repo-check \
  "Rename getReadRepairChance to getChance in all Java files"
```

#### Gemini CLI

```bash
gemini -p "Rename DatabaseDescriptor.getReadRepairChance() to ReadRepairConfig.getChance()" \
  --output-format stream-json
```

Same PATH and system prompt approach as Codex.

---

### comby — 83.6% token reduction

**Use case.** Rewrite structural code patterns using template-based matching, with language-aware hole-filling.

**When to reach for comby.** You need to rewrite a pattern that's more complex than a literal string but not quite an AST query. Comby uses `:[hole]` syntax to match arbitrary expressions within a structural pattern — useful for renaming call patterns where the arguments vary.

**Token savings** (from `benchmark-data.json`):

| Metric | Value |
|--------|-------|
| Avg raw tokens | 1,879 |
| Avg reduced tokens | 308 |
| Reduction | **83.6%** |
| Deterministic pass rate | 100% |

**Copy-paste command:**
```bash
comby 'DatabaseDescriptor.getReadRepairChance()' 'ReadRepairConfig.getChance()' \
  .java -diff -matcher .java
```

#### Claude Code

Add to your `CLAUDE.md`:

```markdown
## comby

Use `comby '<pattern>' '<replacement>' .<ext> -matcher .<ext>` for structural code rewrites.
Comby understands language structure — use it when fastmod's text replacement is too broad
and ast-grep's exact AST patterns are too rigid.

Use `:[hole]` syntax to match variable expressions:
`comby 'foo(:[args])' 'bar(:[args])' .java -matcher .java`

Example: `comby 'DatabaseDescriptor.getReadRepairChance()' 'ReadRepairConfig.getChance()' .java -diff`
```

Example prompt that triggers it:
> "Use comby to rewrite all calls to getReadRepairChance."

#### Codex

Add to your system prompt:
```
For structural code rewrites with template holes, use `comby '<pattern>' '<replacement>' .<ext> -matcher .<ext>`.
This is preferable to sed for language-aware rewrites.
```

Ensure `comby` is on PATH:
```bash
export PATH="$(which comby | xargs dirname):$PATH"
codex exec --full-auto --json --ephemeral --skip-git-repo-check \
  "Rewrite getReadRepairChance to getChance using comby"
```

#### Gemini CLI

```bash
gemini -p "Rewrite DatabaseDescriptor.getReadRepairChance() to ReadRepairConfig.getChance()" \
  --output-format stream-json
```

Same PATH and system prompt approach as Codex.

---

### fastmod — 65.1% token reduction

**Use case.** Rename a string across all files of a given extension, fast and safely.

**When to reach for fastmod.** You need a literal string replaced across the entire codebase and you know the exact text. Fastmod is the right tool for identifier renames (underscored names, config keys, file-path strings) where AST-awareness isn't needed. Use ast-grep or comby when the pattern is a method call or expression.

**Token savings** (from `benchmark-data.json`):

| Metric | Value |
|--------|-------|
| Avg raw tokens | 2,436 |
| Avg reduced tokens | 850 |
| Reduction | **65.1%** |
| Deterministic pass rate | 100% |

**Copy-paste command:**
```bash
fastmod --accept-all --fixed-strings read_repair_chance read_repair_probability -e java,yaml .
```

#### Claude Code

Add to your `CLAUDE.md`:

```markdown
## fastmod

Use `fastmod --accept-all --fixed-strings <old> <new> -e <ext> .` for literal string renames.
Prefer over sed/awk for bulk renames — fastmod is faster and processes only matched files.

When to use fastmod vs ast-grep:
- fastmod: literal strings, config keys, underscore identifiers
- ast-grep: method calls, expressions, anything with syntax structure

Example: `fastmod --accept-all --fixed-strings old_name new_name -e java,yaml .`
```

Example prompt that triggers it:
> "Rename read_repair_chance to read_repair_probability in all Java and YAML files."

#### Codex

Add to your system prompt:
```
For literal string renames across a codebase, use `fastmod --accept-all --fixed-strings <old> <new> -e <ext> .`
instead of sed loops or manual file edits.
```

Ensure `fastmod` is on PATH:
```bash
export PATH="$(which fastmod | xargs dirname):$PATH"
codex exec --full-auto --json --ephemeral --skip-git-repo-check \
  "Rename read_repair_chance to read_repair_probability in all Java and YAML files"
```

#### Gemini CLI

```bash
gemini -p "Rename read_repair_chance to read_repair_probability across Java and YAML files" \
  --output-format stream-json
```

Same PATH and system prompt approach as Codex.

---

## Submit a Tool

Know a CLI tool that saves tokens in agentic coding workflows?

Criteria:
- Takes file or codebase input
- Produces smaller, targeted output (diff, filtered results, index)
- Deterministic — same input, same output, every time

**[Open an issue with the tool submission template →](https://github.com/pmcfadin/agentic-token-bench/issues/new?template=submit-tool.yml)**
