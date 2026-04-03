const path = require("path");
const { renderClaudeCommand, renderSharedMarkdown } = require("../templates");

const CLAUDE_HOOK = {
  hooks: {
    PreToolUse: [
      {
        matcher: "Bash",
        hooks: [
          {
            type: "command",
            command: "rtk hook",
          },
        ],
      },
    ],
  },
};

function claudeAdapter() {
  return {
    id: "claude",
    probe(probes) {
      return probes.agents.claude;
    },
    planChanges(context) {
      const configRoot = context.agent.configRoot;
      const changes = [];
      changes.push({
        path: path.join(configRoot, "CLAUDE.md"),
        ownership: "managed-block",
        managedBlock: renderSharedMarkdown("Claude Code", context.tools, [
          context.tools.rtk.status === "present"
            ? "rtk is installed. Tokenmax can maintain the documented `PreToolUse` hook in `settings.json`."
            : "rtk is not installed, so Tokenmax will not write the optional Claude hook block.",
          "Use `/tokenmax ...` to invoke the shared Tokenmax CLI from inside Claude Code.",
        ]),
      });

      changes.push({
        path: path.join(configRoot, "commands", "tokenmax.md"),
        ownership: "generated",
        content: renderClaudeCommand(),
      });

      if (context.tools.rtk.status === "present") {
        changes.push({
          path: path.join(configRoot, "settings.json"),
          ownership: "json-fragment",
          jsonFragment: CLAUDE_HOOK,
        });
      }

      return changes;
    },
    validate(changes) {
      const problems = [];
      for (const change of changes) {
        if (!change.applied) {
          problems.push(`Expected Claude change was not applied: ${change.path}`);
        }
      }
      return problems;
    },
  };
}

module.exports = {
  CLAUDE_HOOK,
  claudeAdapter,
};
