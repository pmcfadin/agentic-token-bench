const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

function getHomeDir(env = process.env) {
  return env.HOME || env.USERPROFILE || os.homedir();
}

function getPlatform(env = process.env) {
  const home = getHomeDir(env);
  return {
    platform: process.platform,
    arch: process.arch,
    homeDir: home,
    userLocalBin:
      process.platform === "win32"
        ? path.join(home, "AppData", "Local", "tokenmax", "bin")
        : path.join(home, ".local", "bin"),
  };
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function fileExists(filePath) {
  try {
    fs.accessSync(filePath);
    return true;
  } catch (_error) {
    return false;
  }
}

function readFileIfExists(filePath) {
  return fileExists(filePath) ? fs.readFileSync(filePath, "utf8") : null;
}

function writeFileEnsured(filePath, content) {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, content, "utf8");
}

function removeFileIfExists(filePath) {
  if (fileExists(filePath)) {
    fs.rmSync(filePath, { force: true });
  }
}

function hashContent(content) {
  return crypto.createHash("sha256").update(content, "utf8").digest("hex");
}

function isoTimestamp(date = new Date()) {
  return date.toISOString().replace(/[:]/g, "-");
}

function stableStringify(value) {
  return JSON.stringify(sortValue(value), null, 2);
}

function sortValue(value) {
  if (Array.isArray(value)) {
    return value.map(sortValue);
  }
  if (value && typeof value === "object") {
    return Object.keys(value)
      .sort()
      .reduce((accumulator, key) => {
        accumulator[key] = sortValue(value[key]);
        return accumulator;
      }, {});
  }
  return value;
}

function parseValueFlag(argv, i, name, validValues) {
  const arg = argv[i];
  let value;
  if (arg.includes("=")) {
    value = arg.split("=")[1];
  } else {
    i++;
    value = argv[i];
  }
  if (!validValues.includes(value)) {
    throw new Error(`Invalid --${name} value: ${value}. Must be one of: ${validValues.join(", ")}`);
  }
  return { value, nextIndex: i };
}

function parseArgs(argv) {
  const { VALID_SCOPES, VALID_MODES } = require("./constants");
  const positionals = [];
  const flags = {
    json: false,
    yes: false,
    dryRun: false,
    force: false,
    help: false,
    version: false,
    scope: VALID_SCOPES[0],
    mode: VALID_MODES[0],
    backup: true,
  };

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith("--") && arg !== "-v") {
      positionals.push(arg);
      continue;
    }
    if (arg === "--json") {
      flags.json = true;
    } else if (arg === "--yes") {
      flags.yes = true;
    } else if (arg === "--dry-run") {
      flags.dryRun = true;
    } else if (arg === "--force") {
      flags.force = true;
    } else if (arg === "--help") {
      flags.help = true;
    } else if (arg === "--version" || arg === "-v") {
      flags.version = true;
    } else if (arg.startsWith("--scope")) {
      const result = parseValueFlag(argv, i, "scope", VALID_SCOPES);
      flags.scope = result.value; i = result.nextIndex;
    } else if (arg.startsWith("--mode")) {
      const result = parseValueFlag(argv, i, "mode", VALID_MODES);
      flags.mode = result.value; i = result.nextIndex;
    } else if (arg === "--backup") {
      flags.backup = true;
    } else if (arg === "--no-backup") {
      flags.backup = false;
    } else if (arg.startsWith("--backup=")) {
      const val = arg.split("=")[1];
      if (val === "false") {
        flags.backup = false;
      } else if (val === "true") {
        flags.backup = true;
      } else {
        throw new Error(`Invalid --backup value: ${val}. Must be true or false`);
      }
    } else {
      throw new Error(`Unknown flag: ${arg}`);
    }
  }

  return { positionals, flags };
}

function parseCommand(argv) {
  const { positionals, flags } = parseArgs(argv);

  if (flags.help) {
    return { action: "help", target: null, flags };
  }

  if (flags.version) {
    return { action: "version", target: null, flags };
  }

  if (positionals.length === 0) {
    return { action: "status", target: "all", flags };
  }

  if (positionals.length === 1 && ["doctor", "status"].includes(positionals[0])) {
    return { action: positionals[0], target: "all", flags };
  }

  if (positionals.length === 2 && ["install", "repair", "uninstall"].includes(positionals[0])) {
    return { action: positionals[0], target: positionals[1], flags };
  }

  throw new Error(`Unsupported command: ${argv.join(" ")}`);
}

function formatJsonOutput(result) {
  const action = result.action || "unknown";
  const target = result.target != null ? result.target : "all";
  const command = `${action} ${target}`;
  const mode = result.mode || "stable";
  const scope = result.scope || "user";
  const warnings = result.warnings || [];

  // Build agents object
  const agents = {};

  if (action === "doctor") {
    // result.agents is an array of { id, status, ... }
    for (const entry of result.agents || []) {
      const agentEntry = { status: entry.status };
      if (entry.status === "missing" || entry.status === "skipped") {
        agentEntry.reason = "not found";
      }
      agents[entry.id] = agentEntry;
    }
  } else if (action === "status") {
    // result.current.results is an array of { agent, status, ... }
    const currentResults = (result.current && result.current.results) || [];
    for (const entry of currentResults) {
      const agentEntry = { status: entry.status };
      if (entry.reason) {
        agentEntry.reason = entry.reason;
      }
      agents[entry.agent] = agentEntry;
    }
  } else {
    // install / repair / uninstall — result.results is an array of { agent, status, ... }
    for (const entry of result.results || []) {
      const agentEntry = { status: entry.status };
      if (entry.status === "skipped" || entry.status === "missing") {
        agentEntry.reason = entry.reason || "not found";
      }
      if (entry.errorCode) {
        agentEntry.errorCode = entry.errorCode;
      }
      if (entry.recoveryHint) {
        agentEntry.recoveryHint = entry.recoveryHint;
      }
      agents[entry.agent] = agentEntry;
    }
  }

  // Derive top-level status string
  let statusStr;
  if (action === "doctor" || action === "status") {
    statusStr = "ok";
  } else {
    const agentValues = Object.values(agents);
    const attempted = agentValues.filter((a) => a.status !== "skipped" && a.status !== "dry-run");
    if (attempted.length === 0) {
      statusStr = "ok";
    } else {
      const failed = attempted.filter((a) => a.status === "failed");
      if (failed.length === 0) {
        statusStr = "ok";
      } else if (failed.length === attempted.length) {
        statusStr = "failed";
      } else {
        statusStr = "partial";
      }
    }
  }

  // Build changed_files: paths from applied changes, deduped, sorted
  const changedSet = new Set();
  for (const entry of result.results || []) {
    for (const change of entry.changes || []) {
      if (change.applied === true) {
        changedSet.add(change.path);
      }
    }
  }
  const changed_files = Array.from(changedSet).sort();

  return { command, status: statusStr, mode, scope, agents, changed_files, warnings };
}

function printOutput(output, useJson) {
  if (useJson) {
    process.stdout.write(`${stableStringify(formatJsonOutput(output))}\n`);
    return;
  }

  if (output.text) {
    process.stdout.write(`${output.text}\n`);
    return;
  }

  process.stdout.write(`${stableStringify(output)}\n`);
}

module.exports = {
  ensureDir,
  fileExists,
  formatJsonOutput,
  getHomeDir,
  getPlatform,
  hashContent,
  isoTimestamp,
  parseCommand,
  printOutput,
  readFileIfExists,
  removeFileIfExists,
  stableStringify,
  writeFileEnsured,
};
