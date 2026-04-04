const { VERSION } = require("./constants");
const { doctor, performInstallLike, status } = require("./runner");
const { parseCommand, printOutput } = require("./utils");

function helpText() {
  return [
    "tokenmax",
    "",
    "Commands:",
    "  tokenmax doctor",
    "  tokenmax status",
    "  tokenmax install all|claude|codex|gemini",
    "  tokenmax repair all|claude|codex|gemini",
    "  tokenmax uninstall all|claude|codex|gemini",
    "",
    "Flags:",
    "  --json",
    "  --yes",
    "  --dry-run",
    "  --force",
    "  --scope user|project",
    "  --mode stable|aggressive",
    "  --help",
  ].join("\n");
}

async function runCli(argv, env = process.env) {
  const command = parseCommand(argv);
  let output;

  switch (command.action) {
    case "help":
      output = { ok: true, text: helpText() };
      break;
    case "version":
      output = { ok: true, version: VERSION, text: VERSION };
      break;
    case "doctor":
      output = doctor(command.target, env, command.flags);
      break;
    case "status":
      output = status(env, command.flags);
      break;
    case "install":
    case "repair":
    case "uninstall":
      output = performInstallLike(command.action, command.target, command.flags, env);
      break;
    default:
      throw new Error(`Unsupported action: ${command.action}`);
  }

  printOutput(output, command.flags && command.flags.json);
  if (!output.ok) {
    process.exitCode = 1;
  }
  return output;
}

module.exports = {
  runCli,
};
