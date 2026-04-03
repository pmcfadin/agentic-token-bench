const path = require("path");
const { renderGeminiCommand, renderSharedMarkdown } = require("../templates");

function geminiAdapter() {
  return {
    id: "gemini",
    probe(probes) {
      return probes.agents.gemini;
    },
    planChanges(context) {
      const configRoot = context.agent.configRoot;
      return [
        {
          path: path.join(configRoot, "GEMINI.md"),
          ownership: "managed-block",
          managedBlock: renderSharedMarkdown("Gemini CLI", context.tools, [
            "Tokenmax v1 does not install Gemini hook or policy automation by default.",
            "Use `/tokenmax ...` to invoke the shared Tokenmax CLI from inside Gemini CLI.",
          ]),
        },
        {
          path: path.join(configRoot, "commands", "tokenmax.toml"),
          ownership: "generated",
          content: renderGeminiCommand(),
        },
      ];
    },
    validate(changes) {
      const problems = [];
      for (const change of changes) {
        if (!change.applied) {
          problems.push(`Expected Gemini change was not applied: ${change.path}`);
        }
      }
      return problems;
    },
  };
}

module.exports = {
  geminiAdapter,
};
