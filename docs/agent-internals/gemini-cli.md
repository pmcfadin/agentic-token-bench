# Gemini CLI: Commands, Skills, and External Tools

*Primary sources: [Gemini CLI docs](https://google-gemini.github.io/gemini-cli/), [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli)*

*Source pin for repo-derived claims in this doc: `google-gemini/gemini-cli` commit `1ae0499e5d194954c455153ad1b8f4f9cc083c6a` inspected on 2026-04-02.*

---

## Overview

Gemini CLI is Google's open-source terminal coding agent. For installer work, the important surfaces are:

- `GEMINI.md` context files
- custom tools via `tools.discoveryCommand` / `tools.callCommand`
- extensions
- hooks
- policies
- sub-agents

Unlike Codex, Gemini has a documented hook system and a documented policy engine.

---

## Modes of Operation

| Mode | How to Invoke |
|---|---|
| Interactive | `gemini` |
| Non-interactive | `gemini -p "<prompt>"` |
| JSON output | `gemini -p "<prompt>" --output-format json` |
| Streaming JSON | `gemini -p "<prompt>" --output-format stream-json` |
| Auto-approve | `--yolo` |
| Sandboxed | `--sandbox` / `-s` |

### Important correction

`--yolo` and `--sandbox` are separate controls:

- `--yolo` enables **YOLO approval mode** (auto-approve tool calls)
- `--sandbox` enables **sandboxing**

The earlier phrasing "implicitly enables sandboxing" was incorrect. The public settings schema and sandbox docs treat approval mode and sandboxing as separate axes.

---

## GEMINI.md Context Files

`GEMINI.md` is Gemini CLI's project instruction file. It is conceptually similar to `CLAUDE.md`, but the format is different.

### Verified behavior

- `GEMINI.md` is freeform Markdown context, not a YAML-frontmatter rules file.
- The default filename can be changed with `context.fileName`.
- Gemini supports `@file.md` imports inside `GEMINI.md`.
- Gemini loads context hierarchically from user, workspace, and tool-accessed directories.

### Cross-agent implication

`GEMINI.md` is **not** a Claude-style rules file:

- no documented YAML frontmatter
- no documented `paths:` conditional syntax
- no evidence that Claude `CLAUDE.md` rules syntax is portable here

For installer work, treat `GEMINI.md` as plain/importable Markdown context.

---

## Agent Skills

Gemini CLI documents skill creation publicly, but the documented `SKILL.md` schema is minimal.

### Documented `SKILL.md` format

From `docs/cli/creating-skills.md`, the documented frontmatter fields are:

- `name`
- `description`

The body is plain Markdown instructions.

Recommended optional directories:

- `scripts/`
- `references/`
- `assets/`

### Cross-agent implication

Gemini skills are **not** documented as Claude-schema-compatible. The safe documented common subset is only:

- `name`
- `description`

Do not assume Claude fields like `allowed-tools`, `context`, `agent`, `paths`, or `hooks` will work in Gemini `SKILL.md`.

---

## Extensions

Gemini CLI has a first-class extension system. An extension is a directory with `gemini-extension.json`, but several important extension components live in sibling directories rather than the manifest itself.

### What an extension can bundle

| Component | Location |
|---|---|
| MCP servers | `gemini-extension.json` |
| Slash commands | `commands/*.toml` |
| Hooks | `hooks/hooks.json` |
| Skills | `skills/<name>/SKILL.md` |
| Sub-agents | `agents/*.md` |
| Policies | `policies/*.toml` |
| Themes | `gemini-extension.json` |
| Context file | `GEMINI.md` |

### Important correction

Hooks, skills, sub-agents, and policies are **not** authored inside `gemini-extension.json`. The extension manifest points to extension metadata; those other surfaces are discovered from their own directories.

---

## Custom Tool Discovery

Gemini CLI has an official low-level external tool mechanism:

```json
{
  "tools": {
    "discoveryCommand": "my-tool-registry --list-tools",
    "callCommand": "my-tool-runner"
  }
}
```

This is documented in public docs and present in the shipped settings schema, so it is not just a source-code artifact.

### Behavior

- `tools.discoveryCommand` runs at startup and returns tool declarations
- `tools.callCommand` executes the selected tool
- this is explicit opt-in, not PATH auto-discovery

### Stability note

This looks production-supported enough to document: it appears in public docs, configuration reference, and schema, not just in private source.

---

## Hooks

Gemini CLI has a documented hook system and it is materially more complete than Codex's current hook implementation.

### Configuration surfaces

- `settings.json` → `hooks`
- `settings.json` → `hooksConfig` for enable/disable/notifications
- extension-bundled hooks in `hooks/hooks.json`

### Supported event names

From the public hooks docs:

- `SessionStart`
- `SessionEnd`
- `BeforeAgent`
- `AfterAgent`
- `BeforeModel`
- `AfterModel`
- `BeforeToolSelection`
- `BeforeTool`
- `AfterTool`
- `PreCompress`
- `Notification`

### Supported handler type

The public hook reference documents only one handler type today:

- `command`

### Matcher behavior

- tool hooks (`BeforeTool`, `AfterTool`) use regex matchers
- lifecycle hooks use exact-string matching
- `*` or empty matcher can match all

### Why this matters for installer work

Gemini hooks are strong enough to support automatic tool-routing logic:

- `BeforeTool` can merge/override `tool_input`
- `AfterTool` can inject context or issue a `tailToolCallRequest`
- `BeforeToolSelection` can reduce or force the tool set seen by the model

So unlike current Codex hooks, Gemini's hook system is plausible for automatic command/tool rewriting workflows.

---

## Sub-agents

Gemini CLI documents local sub-agents publicly, including extension-bundled sub-agents.

### File format

Sub-agents live in `agents/*.md` and must begin with YAML frontmatter.

Documented fields:

- `name`
- `description`
- `kind`
- `tools`
- `mcpServers`
- `model`
- `temperature`
- `max_turns`
- `timeout_mins`

### Isolation semantics

Public docs explicitly say:

- sub-agents run in their own isolated context loop
- they can have isolated tools / inline MCP servers
- they cannot call other sub-agents

### Cross-agent implication

Gemini sub-agent files are their own format. They are not Claude sub-agent files and not Codex worker/agent config.

---

## Policies (`policies/*.toml`)

Gemini CLI's policy engine is fully documented and is a major part of the extension model.

### What policies do

Policies control whether a tool call is:

- `allow`
- `deny`
- `ask_user`

Rules can match on:

- `toolName`
- `mcpName`
- `argsPattern`
- `interactive`
- approval `modes`
- `priority`

### Extension policies

Extensions can ship `.toml` files under `policies/`.

Important documented constraints:

- extension policies run in their own tier
- extension policies cannot force `allow` or `yolo` bypasses the way a user/admin policy can

This makes extension policies suitable for guardrails and restrictions, not silent privilege escalation.

### Cross-agent implication

Gemini has a real policy engine; Claude and Codex do not expose the same TOML policy surface.

---

## `/compress` and Context Compaction

Gemini CLI has both a manual `/compress` command and internal compression logic.

### Source-backed behavior

From `packages/core/src/context/chatCompressionService.ts`:

- default compression threshold is `0.5` of the model token limit
- default preserved tail is `0.3` of the recent history
- recent tool outputs are preferentially preserved
- oversized older tool outputs may be truncated and saved to temp files
- Gemini generates a `<state_snapshot>` summary, then runs a verification pass over that summary
- compression is rejected if the result would inflate token count or if the summary is empty

### Config knob

The settings schema exposes `model.compressionThreshold`.

### Hook integration

Gemini exposes a `PreCompress` hook event, which Claude/Codex docs do not match directly.

### Cross-agent implication

Gemini has the most source-visible compaction logic of the three agents here. It is not just a blind "summarize and continue" command.

---

## Sandboxing

Gemini sandboxing is documented separately from approval mode.

### Ways to enable it

- `--sandbox` / `-s`
- `GEMINI_SANDBOX`
- `settings.json` → `tools.sandbox`

### Relevant settings

From the settings schema:

- `tools.sandbox`
- `tools.sandboxAllowedPaths`
- `tools.sandboxNetworkAccess`

### Important correction

`--yolo` does **not** imply sandboxing. It only changes approval behavior.

---

## Stream JSON Output

Public docs confirm `--output-format stream-json`, but they do **not** currently publish a stable, line-by-line event schema detailed enough to trust for code generation.

I removed the prior made-up event table because it was not pinned to a primary source.

What is verified:

- `stream-json` exists and is intended for real-time events
- the repo has internal event enums such as `content`, `tool_call_request`, `tool_call_response`, `thought`, `finished`, and related events

What is **not** fully verified here:

- the exact public `stream-json` wire contract exposed by the current CLI
- whether the internal event enum maps 1:1 to emitted CLI JSON lines

For production parsers, this still needs a dedicated live-output verification pass against the pinned repo revision.

---

## Token-Saving Tool Configuration

Gemini has several usable installer surfaces for token-saving tools:

### Stable documented options

- put tools on `PATH`
- provide routing instructions in `GEMINI.md`
- register explicit tools with `tools.discoveryCommand`
- register MCP servers
- bundle reusable behavior in extensions / skills

### Automatic rewriting option

Unlike current Codex hooks, Gemini hooks are capable enough to attempt automatic rewriting around `run_shell_command` or tool selection. That makes Gemini a realistic target for Claude-style command routing, though it will still need careful testing against the specific built-in tool names used by the current CLI.

---

## Open Gaps

The largest remaining gaps after checking docs and source are:

- **Exact `stream-json` wire schema:** needs live verification, not just internal enum inspection.
- **Skill schema compatibility:** only `name` and `description` are documented; Claude parity should not be assumed.
- **Extension/sub-agent compatibility:** Gemini sub-agent and extension formats are their own contracts, not shared with Claude or Codex.

