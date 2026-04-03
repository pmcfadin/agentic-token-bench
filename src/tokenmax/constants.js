const path = require("path");

const VERSION = "0.1.0";
const AGENT_IDS = ["claude", "codex", "gemini"];
const TOOL_IDS = ["qmd", "rtk", "rg", "ast-grep", "comby", "fastmod"];
const TOOL_LABELS = {
  qmd: "qmd",
  rtk: "rtk",
  rg: "ripgrep",
  "ast-grep": "ast-grep",
  comby: "comby",
  fastmod: "fastmod",
};
const MANAGED_BLOCK_START = "<!-- tokenmax:start -->";
const MANAGED_BLOCK_END = "<!-- tokenmax:end -->";
const STATE_DIR_NAME = ".tokenmax";
const CURRENT_STATE_FILE = "current.json";
const MANIFESTS_DIR = "manifests";
const BACKUPS_DIR = "backups";
const LOGS_DIR = "logs";

const TOOL_CAPABILITIES = {
  qmd: {
    label: "qmd",
    purpose: "Read exact line ranges instead of whole files.",
    commands: ["qmd get <file>:<line> -l <count>"],
    guidance: "Use after locating the line with ripgrep when you need a single function or passage.",
  },
  rg: {
    label: "ripgrep",
    purpose: "Find files and exact line numbers before reading code.",
    commands: ["rg -l <pattern> .", "rg -n <pattern> <file>"],
    guidance: "Use before directory scans or broad file reads.",
  },
  rtk: {
    label: "rtk",
    purpose: "Compact shell output and listings.",
    commands: ["rtk ls <dir>", "rtk gain", "rtk <command>"],
    guidance: "Prefer for directory exploration and compact shell output.",
  },
  "ast-grep": {
    label: "ast-grep",
    purpose: "AST-aware search and rewrite for structural code changes.",
    commands: [
      "ast-grep run --pattern '<pattern>' --lang <lang> .",
      "ast-grep run --pattern '<old>' --rewrite '<new>' --lang <lang> -U .",
    ],
    guidance: "Use for method and expression rewrites where syntax matters.",
  },
  comby: {
    label: "comby",
    purpose: "Template-based structural rewrites with holes.",
    commands: ["comby '<pattern>' '<replacement>' .<ext> -matcher .<ext>"],
    guidance: "Use when argument shapes vary and a literal replace is too weak.",
  },
  fastmod: {
    label: "fastmod",
    purpose: "Fast literal string replacements across many files.",
    commands: ["fastmod --accept-all --fixed-strings <old> <new> -e <ext> ."],
    guidance: "Use for config keys or plain string renames.",
  },
};

function statePaths(homeDir) {
  const root = path.join(homeDir, STATE_DIR_NAME);
  return {
    root,
    current: path.join(root, CURRENT_STATE_FILE),
    manifestsDir: path.join(root, MANIFESTS_DIR),
    backupsDir: path.join(root, BACKUPS_DIR),
    logsDir: path.join(root, LOGS_DIR),
  };
}

module.exports = {
  AGENT_IDS,
  BACKUPS_DIR,
  CURRENT_STATE_FILE,
  LOGS_DIR,
  MANAGED_BLOCK_END,
  MANAGED_BLOCK_START,
  MANIFESTS_DIR,
  STATE_DIR_NAME,
  TOOL_CAPABILITIES,
  TOOL_IDS,
  TOOL_LABELS,
  VERSION,
  statePaths,
};
