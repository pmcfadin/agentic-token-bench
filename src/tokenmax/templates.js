const { TOOL_CAPABILITIES } = require("./constants");

function detectedTools(tools) {
  return Object.values(tools)
    .filter((tool) => tool.status === "present")
    .sort((left, right) => left.id.localeCompare(right.id));
}

function missingTools(tools) {
  return Object.values(tools)
    .filter((tool) => tool.status !== "present")
    .sort((left, right) => left.id.localeCompare(right.id));
}

function renderToolGuidance(tools, options = {}) {
  const available = detectedTools(tools);
  const lines = [];

  if (available.length === 0) {
    lines.push("No token-saving benchmark tools are currently installed on PATH.");
    lines.push("Ask the user before assuming these tools are available.");
    return lines.join("\n");
  }

  lines.push("Prefer the installed token-saving CLI tools before broad file reads or large shell output.");
  for (const tool of available) {
    const capability = TOOL_CAPABILITIES[tool.id];
    lines.push(`- ${capability.label}: ${capability.purpose}`);
    lines.push(`  Use: ${capability.commands.join(" | ")}`);
    lines.push(`  Guidance: ${capability.guidance}`);
  }

  const missing = missingTools(tools);
  if (missing.length > 0 && options.includeMissingNote !== false) {
    lines.push("");
    lines.push(
      `Missing tools: ${missing.map((tool) => tool.id).join(", ")}. Do not assume they exist.`
    );
  }

  return lines.join("\n");
}

function renderSharedMarkdown(agentLabel, tools, extraLines = []) {
  const lines = [
    `# Tokenmax guidance for ${agentLabel}`,
    "",
    "This block is managed by tokenmax. Update it with `tokenmax repair` instead of editing it manually.",
    "",
    renderToolGuidance(tools),
  ];

  if (extraLines.length > 0) {
    lines.push("", ...extraLines);
  }

  return lines.join("\n").trim();
}

function renderClaudeCommand() {
  return [
    "---",
    "description: Run tokenmax installer and maintenance commands",
    "argument-hint: [install|status|doctor|repair|uninstall] ...",
    "---",
    "",
    "Run `tokenmax {{args}}` in Bash. If no arguments are provided, run `tokenmax status`.",
    "Summarize the result briefly and call out any missing tools or skipped agents.",
    "",
  ].join("\n");
}

function renderCodexSkill() {
  return [
    "---",
    "name: tokenmax",
    "description: Run the tokenmax installer and maintenance CLI for local agent configuration.",
    "---",
    "",
    "# tokenmax",
    "",
    "Use this skill when the user wants to install, repair, inspect, or remove Tokenmax-managed agent integrations.",
    "",
    "Run `tokenmax <args>` in the shell. If no arguments were supplied, run `tokenmax status`.",
    "Report skipped agents, missing benchmark tools, and any follow-up action that still requires the user.",
    "",
  ].join("\n");
}

function renderGeminiCommand() {
  return [
    'description = "Run tokenmax installer and maintenance commands"',
    'prompt = """',
    "Run `tokenmax {{args}}` in the shell. If no arguments are supplied, run `tokenmax status`.",
    "Summarize the result and call out missing tools or skipped agents.",
    '"""',
    "",
  ].join("\n");
}

module.exports = {
  detectedTools,
  missingTools,
  renderClaudeCommand,
  renderCodexSkill,
  renderGeminiCommand,
  renderSharedMarkdown,
  renderToolGuidance,
};
