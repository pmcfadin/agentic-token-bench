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

function parseArgs(argv) {
  const positionals = [];
  const flags = {
    json: false,
    yes: false,
    dryRun: false,
    force: false,
    help: false,
    version: false,
  };

  for (const arg of argv) {
    if (!arg.startsWith("--")) {
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

function printOutput(output, useJson) {
  if (useJson) {
    process.stdout.write(`${stableStringify(output)}\n`);
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
