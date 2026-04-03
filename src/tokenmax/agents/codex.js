const path = require("path");
const { renderCodexSkill, renderSharedMarkdown } = require("../templates");

function codexAdapter() {
  return {
    id: "codex",
    probe(probes) {
      return probes.agents.codex;
    },
    planChanges(context) {
      const configRoot = context.agent.configRoot;
      return [
        {
          path: path.join(configRoot, "AGENTS.md"),
          ownership: "managed-block",
          managedBlock: renderSharedMarkdown("Codex", context.tools, [
            "Codex does not currently support source-backed transparent shell-command rewriting like Claude hooks.",
            "Use the installed Tokenmax skill to tell Codex to run `tokenmax ...` explicitly.",
          ]),
        },
        {
          path: path.join(configRoot, "skills", "tokenmax", "SKILL.md"),
          ownership: "generated",
          content: renderCodexSkill(),
        },
      ];
    },
    validate(changes) {
      const problems = [];
      for (const change of changes) {
        if (!change.applied) {
          problems.push(`Expected Codex change was not applied: ${change.path}`);
        }
      }
      return problems;
    },
  };
}

module.exports = {
  codexAdapter,
};
