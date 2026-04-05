# Tokenmax Install Specification

## Purpose

`tokenmax` is the cross-platform installer and maintenance command for wiring
token-saving CLI tools into Claude Code, Codex, and Gemini CLI.

The installer must:

- expose one stable user-facing command: `tokenmax`
- work on macOS, Linux, and Windows
- keep bootstrap logic small
- keep real install logic inside the versioned `tokenmax` executable
- avoid relying on undocumented agent internals

---

## Design Goals

### 1. One real command

The system command is always:

```bash
tokenmax
```

Agent-specific commands and wrappers may exist, but they are adapters. They are
not the source of truth.

### 2. Thin bootstrap

Bootstrap scripts install `tokenmax` and then hand off to:

```bash
tokenmax install all
```

Bootstrap scripts do not contain agent-specific edit logic.

### 3. Safe-by-default installation

The installer must prefer source-backed configuration surfaces:

- Claude Code: `CLAUDE.md`, custom commands, documented hooks, MCP config
- Codex: `AGENTS.md`, skills/plugins, MCP config
- Gemini CLI: `GEMINI.md`, commands, hooks, extensions, policies, MCP config

It must not depend on unsupported Codex hook rewriting or undocumented Claude
plugin authoring.

### 4. Reversible changes

Every install operation must support backup, status inspection, repair, and
uninstall.

---

## Supported Bootstrap Paths

### POSIX bootstrap

For macOS and Linux:

```bash
curl -fsSL https://tokenmax.dev/install.sh | sh
```

### PowerShell bootstrap

For Windows:

```powershell
irm https://tokenmax.dev/install.ps1 | iex
```

### Bootstrap responsibilities

The bootstrap script must:

1. Detect OS and architecture.
2. Resolve the requested version.
3. Download the correct `tokenmax` artifact or package.
4. Install it into a user-local bin directory.
5. Ensure that directory is on `PATH`.
6. Run `tokenmax --version`.
7. Optionally run `tokenmax install all --yes`.

### Non-goals for bootstrap

The bootstrap script must not:

- edit Claude, Codex, or Gemini config directly
- contain agent-specific routing rules
- contain benchmark-specific business logic

---

## Install Locations

### Executable

Recommended default install targets:

- macOS/Linux: `~/.local/bin/tokenmax`
- Windows: `%USERPROFILE%\\AppData\\Local\\tokenmax\\bin\\tokenmax.exe`

### Tokenmax state

Recommended state root:

```text
~/.tokenmax/
```

This directory stores:

- backups
- install manifests
- shared command templates
- generated helper scripts
- logs

---

## Command Set

### Core commands

```bash
tokenmax --version
tokenmax doctor
tokenmax status
tokenmax install all
tokenmax uninstall all
tokenmax repair all
tokenmax bench
```

### Per-agent commands

```bash
tokenmax install claude
tokenmax install codex
tokenmax install gemini

tokenmax uninstall claude
tokenmax uninstall codex
tokenmax uninstall gemini

tokenmax repair claude
tokenmax repair codex
tokenmax repair gemini
```

### Recommended flags

```bash
tokenmax install all --yes
tokenmax install all --dry-run
tokenmax install all --force
tokenmax install all --backup
tokenmax install all --scope user
tokenmax install all --scope project
tokenmax install all --mode stable
tokenmax install all --mode aggressive
```

---

## Command Semantics

### `tokenmax doctor`

Checks local prerequisites and reports:

- OS and architecture
- detected agents
- writable config locations
- required helper tools on `PATH`
- missing dependencies
- stale or conflicting prior installs

It does not modify files.

### `tokenmax status`

Reports current Tokenmax-managed state:

- installed `tokenmax` version
- detected agents
- install mode
- files owned by Tokenmax
- backup availability
- validation result per agent
- drift from the recorded install manifest

### `tokenmax install all`

Installs Tokenmax-managed integration for every detected supported agent.

Default behavior:

- install only on detected agents
- back up touched files
- validate after write
- print per-agent results

### `tokenmax repair all`

Re-applies or fixes Tokenmax-owned assets when:

- a managed file was deleted
- a generated command wrapper drifted
- a prior install was partial

### `tokenmax bench`

Passive before/after token-usage report built from the transcripts already
written by Claude Code, Gemini CLI, and Codex CLI.

```bash
tokenmax bench                      # text report, all CLIs
tokenmax bench --cli claude,codex   # filter CLIs
tokenmax bench --since 30d          # relative window
tokenmax bench --since 2026-02-01   # absolute window
tokenmax bench --cwd ~/projects/foo # scope to one project
tokenmax bench --html report.html   # single-file shareable chart
tokenmax bench --json               # machine-readable output
```

The install-date anchor is written to `~/.tokenmax/installed_at` on first
`tokenmax install` and is never overwritten, so upgrades preserve the original
divider. If the marker is missing, bench falls back to the `PreToolUse` hook
mtime in `~/.claude/settings.json`.

Metrics reported per CLI: median input tokens per turn, cache-read ratio
(Claude Code), and the step-change delta between the before/after buckets.
Sessions without token-count events are skipped silently. Reports contain
aggregates only — no message content, no filenames beyond the `cwd` root.

Bench is read-only. It does not modify any files (it may write the `--html`
report to a user-specified path).

### `tokenmax uninstall all`

Removes Tokenmax-owned integration and restores backups where available.

It must not delete unrelated user-authored files or revert unrelated edits.

---

## Install Modes

### `stable`

`stable` is the default mode.

It uses only source-backed surfaces that are stable enough to automate:

- Claude: `CLAUDE.md`, custom command, optional documented hook scaffolding
- Codex: `AGENTS.md`, skill/plugin wrapper, no hook rewriting
- Gemini: `GEMINI.md`, command or extension wrapper, optional documented hooks

### `aggressive`

`aggressive` may enable extra integrations where they are documented and testable,
but it still must not depend on:

- unsupported Codex `PreToolUse.updatedInput`
- undocumented Claude plugin authoring
- unverified Gemini stream-json wire assumptions

---

## `tokenmax install all` Flow

### Phase 1: Detection

The command detects:

- Claude Code config roots
- Codex config roots
- Gemini CLI config roots
- project root, if `--scope project` is used

If an agent is not installed, Tokenmax skips it and reports that decision.

### Phase 2: Preflight

The command verifies:

- target directories exist or can be created
- target files are readable and writable
- required helper binaries are present
- current OS supports the requested install mode

### Phase 3: Backup

Before any write, Tokenmax creates a timestamped backup set under:

```text
~/.tokenmax/backups/<timestamp>/
```

The backup set must include:

- original file copies
- a manifest of intended writes
- per-agent install metadata

### Phase 4: Shared asset install

Tokenmax writes shared assets under `~/.tokenmax/`, such as:

- prompt fragments
- helper scripts
- generated command bodies
- install manifest metadata

### Phase 5: Agent-specific configuration

#### Claude Code

Allowed write surfaces:

- `CLAUDE.md` guidance snippet
- `.claude/commands/tokenmax.md` custom command
- optional documented hook config when the feature is explicitly enabled

Tokenmax must not assume undocumented Claude plugin authoring.

#### Codex

Allowed write surfaces:

- `AGENTS.md` guidance snippet
- a Codex-facing skill or plugin wrapper that shells out to `tokenmax`
- Codex MCP configuration, if used

Tokenmax must not rely on Codex hook rewriting because current source shows
that path is experimental and insufficient for command mutation.

#### Gemini CLI

Allowed write surfaces:

- `GEMINI.md` guidance snippet
- `.gemini/commands/tokenmax.toml` or extension-provided command
- optional hook, policy, or extension config where needed

### Phase 6: Validation

After writes, Tokenmax validates:

- files exist at expected locations
- rendered command wrappers parse correctly
- config JSON or TOML remains valid
- managed file markers are present

### Phase 7: Summary

Tokenmax prints:

- installed agents
- skipped agents
- changed files
- warnings
- rollback command

---

## Agent-Facing Command Shape

### Goal

On each supported agent, the user should be able to invoke a visible agent-level
command named `tokenmax`, but the command body must delegate to the installed
system executable.

### Desired command experience

Examples:

- Claude Code: `/tokenmax install all`
- Gemini CLI: `/tokenmax install all`
- Codex: skill/plugin wrapper that prompts Codex to run `tokenmax install all`

### Constraint

Codex does not have the same documented custom command surface as Claude and
Gemini. The spec therefore treats the executable as primary and Codex wrappers
as secondary adapters.

---

## File Ownership Model

Tokenmax must track ownership explicitly.

Each managed write must be tagged as one of:

- `generated`
- `managed-block`
- `copied-template`

### Managed-block rule

When Tokenmax modifies a shared user file such as `CLAUDE.md`, `AGENTS.md`, or
`GEMINI.md`, it should prefer inserting a bounded managed block instead of
rewriting the whole file.

Example marker shape:

```text
<!-- tokenmax:start -->
...
<!-- tokenmax:end -->
```

This makes repair and uninstall safer.

---

## Rollback and Uninstall

### Rollback guarantee

If `install all` fails after partial writes, Tokenmax must either:

- restore the previous state automatically, or
- leave a complete recovery manifest and print the recovery command

### `uninstall all`

Uninstall must:

- remove generated files owned by Tokenmax
- remove managed blocks from shared files
- restore backed-up originals when available
- preserve unrelated user content

---

## Output Contract

Every mutating command should emit:

- a human-readable summary
- a machine-readable result object, optionally behind `--json`

Recommended JSON result shape:

```json
{
  "command": "install all",
  "status": "ok",
  "mode": "stable",
  "agents": {
    "claude": { "status": "installed" },
    "codex": { "status": "installed" },
    "gemini": { "status": "skipped", "reason": "not found" }
  },
  "changed_files": [],
  "warnings": []
}
```

---

## Errors

### Failure classes

- `preflight_failed`
- `backup_failed`
- `write_failed`
- `validation_failed`
- `rollback_failed`

### Error handling rule

On failure, Tokenmax must say:

- what failed
- which file or agent was affected
- whether rollback succeeded
- what the user should run next

---

## Recommended Initial Scope

Version 1 should implement:

- bootstrap installers for POSIX and PowerShell
- `doctor`
- `status`
- `install all`
- `uninstall all`
- `repair all`
- `stable` mode only
- managed-block edits for `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md`
- agent-facing `tokenmax` command wrappers where the surface is documented

Version 1 should not implement:

- transparent shell-command rewriting in Codex
- undocumented Claude plugin packaging
- aggressive extension/policy behavior by default

---

## Open Questions

- Should the first release ship as a Node CLI, a single binary, or both?
- Should `install all` auto-install underlying helper tools, or only wire them if already present?
- Should project-scoped installs be allowed for all three agents, or only where the target agent clearly supports local project config?

