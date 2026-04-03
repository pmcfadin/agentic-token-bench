# Claude Code: Commands, Skills, and External Tools

*Primary sources: [Anthropic Claude Code docs](https://docs.anthropic.com/en/docs/claude-code) inspected on 2026-04-02.*

---

## Overview

Claude Code is Anthropic's local coding agent and terminal workflow. For installer work, the important documented surfaces are:

- `CLAUDE.md` memory / instruction files
- custom slash commands
- hooks
- MCP servers
- sub-agents
- `/compact` for context compaction

Several other surfaces mentioned in prior research remain real possibilities, but are not currently pinned by a primary public source. Those are called out explicitly below instead of being treated as settled facts.

---

## Built-in Slash Commands

Anthropic's current slash-command docs publicly document built-ins including:

- `/agents`
- `/clear`
- `/compact`
- `/config`
- `/cost`
- `/doctor`
- `/help`
- `/init`
- `/login`
- `/logout`
- `/mcp`
- `/memory`
- `/model`
- `/permissions`
- `/pr_comments`
- `/review`
- `/status`
- `/terminal-setup`
- `/vim`

For installer design, the important ones are `/memory`, `/mcp`, `/permissions`, `/agents`, and `/compact`.

---

## `CLAUDE.md` Memory Files

`CLAUDE.md` is Claude Code's project instruction file.

### Verified behavior

Anthropic's memory docs currently document:

- a global `~/.claude/CLAUDE.md`
- a project `CLAUDE.md`
- hierarchical loading from parent directories
- `@path/to/file.md` imports inside `CLAUDE.md`
- inspection via `/memory`

The docs also note that Claude Code automatically compacts conversation history when context gets large, and `/compact` lets the user trigger compaction manually.

### Format notes

Current public docs clearly support:

- plain Markdown
- imported Markdown fragments via `@...`

What I did **not** find a current primary public source for:

- YAML frontmatter on `CLAUDE.md` itself
- a stable current `paths:` conditional syntax on `CLAUDE.md`
- a hard size limit suitable to code against

### Cross-agent implication

Compared with the other two agents:

- Claude supports `@file`-style imports in its memory file
- Codex `AGENTS.md` is simpler freeform Markdown with hierarchical concatenation
- Gemini `GEMINI.md` is also freeform Markdown, but its import/config story is different

Do not assume these three instruction-file formats are interchangeable.

---

## Custom Commands vs. Skills

Anthropic's current public docs clearly document **custom slash commands** in `.claude/commands/`.

Documented frontmatter for custom commands includes fields such as:

- `description`
- `argument-hint`
- `allowed-tools`
- `model`

### Important source gap

Prior research and the previous draft of this doc described a richer `.claude/skills/<name>/SKILL.md` surface with fields like:

- `context: fork`
- `agent`
- `hooks`
- `paths`
- `disable-model-invocation`
- `user-invocable`

I did **not** find a fresh public primary source during this pass that pins the full current `SKILL.md` schema well enough to treat it as settled.

### Practical guidance

For code you are going to write against:

- custom slash commands in `.claude/commands/` are source-backed
- the full standalone Claude `SKILL.md` contract still needs one more primary-source pass before it should be treated as authoritative

---

## External Tools

Claude Code reaches external tooling through:

### 1. The Bash tool

Claude can execute arbitrary shell commands, subject to approval rules and hook interception.

### 2. MCP servers

Anthropic's docs publicly document `claude mcp add ...` and `settings.json`-based MCP configuration. MCP tools and prompts then become available to Claude Code.

### 3. Custom slash commands

Custom commands can wrap shell usage, MCP prompts, and local project workflow instructions.

---

## Hooks

Claude Code's hook system is publicly documented and is the strongest documented hook surface of the three agents for command-routing workflows.

### Documented hook events

Anthropic's hook docs publicly list events including:

- `PreToolUse`
- `PostToolUse`
- `Notification`
- `UserPromptSubmit`
- `Stop`
- `SubagentStop`
- `PreCompact`
- `SessionStart`
- `SessionEnd`

### Documented matcher behavior

The public docs explicitly say:

- only `PreToolUse` and `PostToolUse` support a `matcher`
- other events ignore `matcher`

### Documented handler shape

The public examples and hook docs clearly document shell-command hooks configured in `settings.json`, for example:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/log-bash.sh"
          }
        ]
      }
    ]
  }
}
```

### Verified behavior from docs

- hook scripts receive JSON on `stdin`
- hook scripts use exit codes to signal allow/block/error behavior
- `SessionStart` and `UserPromptSubmit` hooks can inject additional context
- `PreToolUse` can block tool execution
- `Stop` and `SubagentStop` can block and prompt Claude to continue

### Important correction

The old doc showed an `if` field like:

```json
"if": "Bash(rm *)"
```

I did **not** find a current primary public source that documents any `if` grammar for Claude Code hooks. The supported, source-backed filter surface is `matcher`. The `if` example should therefore be treated as **unverified and removed**.

### Remaining hook gap

The exact full mutation schema for command rewriting should still be pinned against Anthropic's current hook reference before writing production code that depends on request mutation rather than blocking/approval behavior.

---

## Sub-agents

Anthropic's sub-agent docs clearly describe specialized sub-agents with:

- their own context window
- configurable / restricted tool access
- task-specific delegation

### What is source-backed

Public docs clearly support:

- custom sub-agents in `.claude/agents/`
- sub-agent descriptions used for delegation
- tool restrictions per sub-agent

### Important source gap

Prior research referenced `context: fork` skills and asked what a forked subagent inherits:

- parent `CLAUDE.md`
- tool permissions
- environment
- approval state

I did **not** find a sufficiently explicit public source spelling out that inheritance contract. For installer work, treat fork/subagent inheritance details as **not yet pinned**.

### Experimental teams gap

Prior notes also referenced `SendMessage` and `TeamCreate` / `TeamDelete` patterns. I did **not** find a stable public Anthropic source documenting this as a supported wire protocol. Do not code against agent-team internals from the current public docs.

---

## MCP Servers

Anthropic publicly documents MCP server registration and use in Claude Code.

What is clearly documented:

- local stdio servers
- remote HTTP servers
- auth / environment configuration
- MCP tools and prompts becoming available inside Claude Code

### Remaining source gap: deferred tool loading

Prior research mentioned deferred MCP tools via `defer_loading: true`.

I did **not** find a current primary public source confirming:

- the exact key spelling
- whether it is per-server or per-tool
- the exact config location

Treat deferred MCP loading as **unverified** until re-pinned from current docs or first-party code.

---

## Plugins

The previous doc described plugin installation and plugin-bundled skills/hooks/MCP content, but plugin **authoring** remains a source gap.

### What I could verify

Anthropic's public docs and search results reference Claude Code IDE/editor plugins and integrations.

### What I could not verify as a current public authoring contract

- plugin directory layout
- plugin manifest schema
- publish/install packaging format
- full list of plugin manifest fields

For installer work, Claude plugin authoring should be treated as **needs primary source**.

---

## Context Compaction

Claude Code has both:

- automatic compaction when context usage grows large
- a manual `/compact` command

This is source-backed from Anthropic's memory/cost docs and is relevant for long benchmark runs.

What is still missing from the public docs, compared with Gemini's source-visible implementation, is a detailed documented algorithm for what Claude preserves versus summarizes during compaction.

---

## Token-Saving Tool Configuration

Claude Code remains the most promising surface for automatic shell-command routing because:

- hooks are documented
- `PreToolUse` can intercept Bash usage
- `CLAUDE.md` and custom slash commands can steer tool choice

What is safe to rely on right now:

- PATH-based tool availability through Bash
- prompt routing via `CLAUDE.md`
- command wrappers via custom slash commands
- blocking / approval logic via hooks

What still needs one more pin before coding a transparent rewriter:

- the exact current hook output fields for mutating a Bash invocation rather than merely blocking or annotating it

---

## Open Gaps

These are the remaining installer-relevant gaps after this review:

- **Plugin authoring:** no current public manifest/packaging spec found.
- **Agent teams / `SendMessage`:** not stable enough in public docs to treat as supported.
- **Hook `if` syntax:** no current primary source found; do not rely on it.
- **Skill `context: fork` inheritance:** exact inheritance contract remains undocumented in public docs.
- **Deferred MCP tools:** exact `defer_loading` contract not pinned from a primary source.
- **Full Claude `SKILL.md` schema:** prior research was richer than what I could currently re-pin from public docs.

