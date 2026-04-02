# Agent Configs

Paste-ready configuration for wiring the six benchmarked token-saving tools into your agent of choice. Each file covers tool PATH setup, system prompt or CLAUDE.md snippets, and token count extraction for that agent.

Use these alongside [`docs/integration-guide.md`](../integration-guide.md), which covers tool selection, use cases, and benchmark token numbers for all six tools.

---

## Guides

| Agent | Config file | Key pattern |
|-------|------------|-------------|
| **Claude Code** | [`claude-code.md`](claude-code.md) | Paste sections into `CLAUDE.md`; Claude reads it at session start |
| **Codex** | [`codex.md`](codex.md) | Add tool binaries to `PATH` before `codex exec --full-auto`; add system prompt lines |
| **Gemini CLI** | [`gemini-cli.md`](gemini-cli.md) | Use `--output-format stream-json`; token counts in the final result line |

---

## Tool selection summary

| Task | Recommended tool |
|------|-----------------|
| Read a specific function | qmd |
| Find files by content | ripgrep |
| Explore a directory structure | rtk |
| Rename a method or expression | ast-grep |
| Rewrite a structural code pattern | comby |
| Rename a literal string or config key | fastmod |
