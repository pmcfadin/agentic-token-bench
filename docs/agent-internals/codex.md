# Codex CLI: Commands, Skills, and External Tools

*Primary sources: [developers.openai.com/codex](https://developers.openai.com/codex), [openai/codex](https://github.com/openai/codex)*

*Source pin for repo-derived claims in this doc: `openai/codex` commit `cb9fb562a46c2217ff0386bb487932db828b3cda` inspected on 2026-04-02.*

---

## Overview

Codex CLI is OpenAI's local coding agent. It runs on the user's machine, reads local files, executes shell commands, applies patches, talks to MCP servers, and can also use plugins, skills, and sub-agents.

Two distinctions matter for installer work:

- **Sandboxing** controls what the process can access.
- **Approval policy** controls when Codex asks the user before acting.

Those are configured separately.

---

## Shell Subcommands

| Subcommand | Purpose |
|---|---|
| `codex exec "<prompt>"` | Run Codex non-interactively |
| `codex exec resume` | Continue a prior non-interactive thread |
| `codex resume` | Resume a prior interactive session |
| `codex login` | Authenticate |
| `codex features` | Inspect and toggle feature flags |
| `codex cloud` | Interact with Codex Cloud tasks / remote work, not local tool wiring |
| `codex sandbox` | Run a command inside Codex sandbox enforcement |
| `codex mcp` | Manage MCP server registrations |

`codex cloud` is not the local CLI's plugin or tool-routing surface. The repo wires it to the `codex-cloud-tasks` crate, and the main README distinguishes local Codex CLI from the cloud-based Codex Web / cloud task experience.

---

## AGENTS.md and Prompt Assembly

Codex uses `AGENTS.md` as its project instruction file. It is the closest analogue to `CLAUDE.md`, but the format is much simpler.

### What the loader actually does

From `codex-rs/core/src/project_doc.rs`:

1. Finds the project root using `project_root_markers` (default `.git`).
2. Walks from that root down to the current working directory.
3. Concatenates `AGENTS.override.md` and `AGENTS.md` files it finds along the way.

### Important format constraints

- `AGENTS.md` is treated as **plain Markdown text**.
- No YAML frontmatter parser exists for `AGENTS.md`.
- No primary-source evidence in the repo for Claude-style structured directives such as `paths:`, conditional loading, or skill-like metadata.
- Additional filenames can be configured via `project_doc_fallback_filenames`, but they are still just read as Markdown text.

### Size limit

The relevant config key is `project_doc_max_bytes`, but the current loader applies it as a **total byte budget across the concatenated project-doc chain**, not "per file".

### Cross-agent implication

`AGENTS.md` is **not** a drop-in format match for Claude Code's richer `CLAUDE.md` rules syntax. For installer design, treat Codex project guidance as freeform Markdown only.

---

## Skills

Codex supports reusable skills, but the current skill file format is **not** the same as Claude Code's richer SKILL schema.

### What the current loader reads

From `codex-rs/core-skills/src/loader.rs`, the `SKILL.md` parser currently recognizes:

- `name`
- `description`
- `metadata.short-description`

Behavior:

- `name` may be omitted; Codex falls back to the skill directory name.
- `description` may be omitted; the loader falls back to an empty string.
- No source-backed evidence that Codex currently parses Claude-style fields such as `allowed-tools`, `context`, `agent`, `paths`, `hooks`, or `argument-hint` from `SKILL.md`.

### Product-specific sidecar metadata

Codex also looks for `agents/openai.yaml` next to a skill. The current loader reads:

- `interface.display_name`
- `interface.short_description`
- `interface.icon_small`
- `interface.icon_large`
- `interface.brand_color`
- `interface.default_prompt`
- `dependencies.tools[]`
- `policy.allow_implicit_invocation`
- `policy.products`

This is the current source-backed way to attach UI/dependency/policy metadata to a skill.

### Important compatibility note

There are protocol comments elsewhere in the repo that mention `SKILL.json`, but in the current loader code inspected for this doc, the sidecar metadata file actually read by Codex is `agents/openai.yaml`. I did **not** find source-backed proof that a `SKILL.json` authoring path is active in the current CLI. Treat `SKILL.json` support as **unverified** until confirmed from the live loader.

### Cross-agent implication

For installer work, assume:

- **Claude Code skill files:** richer schema
- **Codex skill files:** minimal `SKILL.md` plus optional `agents/openai.yaml`

A single Claude-style `SKILL.md` should **not** be assumed to work unchanged in Codex.

---

## Plugins

Codex plugin authoring is mostly source-derived today; public documentation lags behind the implementation.

### Manifest location

The required manifest path is:

```text
<plugin-root>/.codex-plugin/plugin.json
```

This path is hard-coded in the repo (`PLUGIN_MANIFEST_PATH`).

### Current manifest fields

From `codex-rs/core/src/plugins/manifest.rs`, the top-level JSON manifest supports:

- `name`
- `description`
- `skills`
- `mcpServers`
- `apps`
- `interface`

`interface` currently supports:

- `displayName`
- `shortDescription`
- `longDescription`
- `developerName`
- `category`
- `capabilities`
- `websiteUrl` / `websiteURL`
- `privacyPolicyUrl` / `privacyPolicyURL`
- `termsOfServiceUrl` / `termsOfServiceURL`
- `defaultPrompt`
- `brandColor`
- `composerIcon`
- `logo`
- `screenshots`

### Path rules

Manifest path fields such as `skills`, `mcpServers`, `apps`, and interface asset paths must:

- start with `./`
- stay inside the plugin root
- not escape via `..`

### Marketplace / install catalog

Local and repo plugin catalogs are indexed by `.agents/plugins/marketplace.json`. The repo's marketplace loader treats that file as the install catalog for plugin names and source paths. This is the current source-backed install surface, but I did not find a stable public "publish a plugin" guide that fully documents this contract.

### Cross-agent implication

Codex plugin authoring is **not** Claude-compatible. It has its own manifest location and schema.

---

## Hooks (`hooks.json`)

Codex does have a hook system now, but it is not feature-complete and it is currently behind the experimental feature flag `codex_hooks`.

### Stability

The feature registry labels `CodexHooks` as experimental, with config key:

```toml
[features]
codex_hooks = true
```

### Discovery

Codex discovers `hooks.json` alongside active config layers and merges handlers in config precedence order.

### Supported events today

From `codex-rs/hooks/src/engine/config.rs`, the current config schema supports:

- `PreToolUse`
- `PostToolUse`
- `SessionStart`
- `UserPromptSubmit`
- `Stop`

### Supported handler types today

Config parsing recognizes:

- `command`
- `prompt`
- `agent`

But current runtime support is narrower:

- `command` hooks run
- `prompt` hooks are skipped as "not supported yet"
- `agent` hooks are skipped as "not supported yet"
- `async` hooks are skipped as "not supported yet"

### Current config shape

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^Bash$",
        "hooks": [
          {
            "type": "command",
            "command": "./hooks/pre-tool.sh",
            "timeout": 600
          }
        ]
      }
    ]
  }
}
```

### Critical limitation for installer work

Codex hook schemas expose fields such as `updatedInput`, `additionalContext`, and `permissionDecision`, but the current runtime rejects several of them for `PreToolUse`:

- `updatedInput` is currently **unsupported**
- `additionalContext` is currently **unsupported**
- `permissionDecision: "allow"` is currently **unsupported**
- `permissionDecision: "ask"` is currently **unsupported**

In practice, current `PreToolUse` hooks are only useful for **blocking** a tool call, not rewriting it.

### Cross-agent implication

Codex hooks are **not** feature-parity with Claude Code hooks, and they are **not** currently sufficient for transparent shell-command rewriting in the Claude `rtk` style.

---

## External Tools

Codex reaches external tooling through three main paths:

### 1. Shell tool

Codex can execute arbitrary shell commands, but it does not enumerate tools from `PATH` as first-class model-visible tools. Installed binaries are only reachable when the model chooses to invoke the shell.

### 2. MCP servers

MCP servers are configured explicitly in config files, for example:

```toml
[mcp_servers.my_server]
command = "npx"
args = ["-y", "my-mcp-package"]
env = { API_KEY = "..." }
enabled_tools = ["tool_a", "tool_b"]
disabled_tools = ["dangerous_tool"]
```

This is the structured tool integration mechanism for Codex.

### 3. Plugins

Plugins can bundle MCP servers, skills, and app integrations, but plugin metadata is Codex-specific as described above.

---

## JSON Output Format (`codex exec --json`)

The JSON event stream has changed over time. For machine consumers, use the repo's SDK/event types rather than older docs.

### Current top-level event types

Pinned to `openai/codex` commit `cb9fb562...`, from `sdk/typescript/src/events.ts`:

- `thread.started`
- `turn.started`
- `turn.completed`
- `turn.failed`
- `item.started`
- `item.updated`
- `item.completed`
- `error`

### Current item `type` values

From `sdk/typescript/src/items.ts`:

- `command_execution`
- `file_change`
- `mcp_tool_call`
- `agent_message`
- `reasoning`
- `web_search`
- `todo_list`
- `error`

### Important correction

Older docs and examples that show event names like `agent_message_delta` are not a safe source of truth for current integrations. The TypeScript SDK in the repo is the better source to code against.

---

## Files Read at Startup

Relevant startup inputs for installer work:

- config layers ending in `config.toml`
- `AGENTS.override.md` / `AGENTS.md`
- `hooks.json` in active config folders
- discovered skills under skill roots
- plugin catalogs in `.agents/plugins/marketplace.json`
- plugin manifests in `.codex-plugin/plugin.json`

---

## Token-Saving Tool Configuration

For an installer that wants to steer Codex toward token-saving CLI tools:

### What works today

- put the tools on `PATH`
- add prompt-routing guidance in `AGENTS.md`
- expose structured tools through MCP where possible
- package skills/plugins if you need reusable installable behavior

### What does not work today

Do **not** assume Codex hooks can transparently rewrite arbitrary shell commands before execution. The experimental hook system exists, but the current runtime does not support `PreToolUse.updatedInput`, so Claude-style command rewriting is not presently source-backed.

---

## Open Gaps

These are the remaining high-value gaps after checking the current official docs and repo:

- **Skill frontmatter:** current source shows a minimal Codex schema, not Claude parity.
- **`SKILL.json`:** mentioned in protocol comments, but active loader support is unverified.
- **Plugin publishing workflow:** local manifest and marketplace layout are source-backed, but a stable public publishing guide was not found.
- **Hooks:** present but experimental and not feature-complete.
- **Codex Cloud:** relevant to cloud tasks / Codex Web, not local installer wiring.

