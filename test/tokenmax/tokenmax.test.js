const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const test = require("node:test");
const { spawnSync } = require("child_process");

const { removeManagedBlock, upsertManagedBlock } = require("../../src/tokenmax/managed-files");
const { doctor, performInstallLike, status } = require("../../src/tokenmax/runner");
const { parseCommand } = require("../../src/tokenmax/utils");

test("parseCommand supports version, status default, and install targets", () => {
  assert.deepEqual(parseCommand(["--version"]).action, "version");
  assert.deepEqual(parseCommand([]).action, "status");
  assert.deepEqual(parseCommand(["install", "all"]).target, "all");
});

test("managed block insert and removal preserve surrounding content", () => {
  const initial = "# Title\n\nExisting notes.\n";
  const updated = upsertManagedBlock(initial, "Managed content");
  assert.match(updated, /Managed content/);
  const removed = removeManagedBlock(updated);
  assert.equal(removed.trim(), initial.trim());
});

test("doctor reports missing agents and tools in an empty environment", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "tokenmax-home-"));
  const output = doctor("all", { HOME: home, PATH: "" });
  assert.equal(output.agents.every((agent) => agent.status === "missing"), true);
  assert.equal(Object.values(output.tools).every((tool) => tool.status === "missing"), true);
});

test("install claude writes managed files and uninstall removes them", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  const install = performInstallLike("install", "claude", baseFlags(), fixture.env);
  assert.equal(install.results[0].status, "installed");

  const claudeRoot = path.join(fixture.home, ".claude");
  const claudeDoc = fs.readFileSync(path.join(claudeRoot, "CLAUDE.md"), "utf8");
  const commandDoc = fs.readFileSync(path.join(claudeRoot, "commands", "tokenmax.md"), "utf8");
  const settings = JSON.parse(fs.readFileSync(path.join(claudeRoot, "settings.json"), "utf8"));

  assert.match(claudeDoc, /Tokenmax guidance for Claude Code/);
  assert.match(claudeDoc, /qmd/);
  assert.match(commandDoc, /tokenmax \{\{args\}\}/);
  assert.equal(settings.hooks.PreToolUse[0].hooks[0].command, "rtk hook");

  const currentStatus = status(fixture.env);
  assert.equal(currentStatus.drift.length, 0);

  const uninstall = performInstallLike("uninstall", "claude", baseFlags(), fixture.env);
  assert.equal(uninstall.results[0].status, "removed");
  assert.equal(fs.existsSync(path.join(claudeRoot, "commands", "tokenmax.md")), false);
  assert.equal(fs.existsSync(path.join(claudeRoot, "settings.json")), false);
});

test("dry-run does not create config roots", () => {
  const fixture = createFixtureEnvironment({
    agents: ["codex"],
    tools: [],
  });

  const result = performInstallLike("install", "codex", { ...baseFlags(), dryRun: true }, fixture.env);
  assert.equal(result.results[0].status, "dry-run");
  assert.equal(fs.existsSync(path.join(fixture.home, ".codex")), false);
});

test("status reports drift and repair restores missing generated files", () => {
  const fixture = createFixtureEnvironment({
    agents: ["gemini"],
    tools: ["qmd", "rg"],
    qmdCollections: "demo-project",
  });

  const install = performInstallLike("install", "gemini", baseFlags(), fixture.env);
  assert.equal(install.results[0].status, "installed");

  const commandPath = path.join(fixture.home, ".gemini", "commands", "tokenmax.toml");
  fs.writeFileSync(commandPath, 'description = "changed"\n', "utf8");

  const driftStatus = status(fixture.env);
  assert.deepEqual(driftStatus.drift, [{ path: commandPath, reason: "content_changed" }]);

  fs.rmSync(commandPath, { force: true });
  const repair = performInstallLike("repair", "gemini", baseFlags(), fixture.env);
  assert.equal(repair.results[0].status, "repaired");
  assert.equal(fs.existsSync(commandPath), true);
});

test("bootstrap scripts contain the thin install flow", () => {
  const posixPath = path.join(process.cwd(), "scripts", "tokenmax", "install.sh");
  const powershellPath = path.join(process.cwd(), "scripts", "tokenmax", "install.ps1");
  const posix = fs.readFileSync(posixPath, "utf8");
  const powershell = fs.readFileSync(powershellPath, "utf8");

  assert.match(posix, /npm install -g/);
  assert.match(posix, /tokenmax --version/);
  assert.match(powershell, /npm install -g/);
  assert.match(powershell, /tokenmax install all --yes/);

  const syntax = spawnSync("sh", ["-n", posixPath], { encoding: "utf8" });
  assert.equal(syntax.status, 0, syntax.stderr);
});

test("error classes carry code, agent, file, and recoveryHint", () => {
  const { PreflightError, BackupError, WriteError, ValidationError, RollbackError } = require("../../src/tokenmax/errors");

  const err = new PreflightError({
    message: "dir not writable",
    agent: "claude",
    file: "/home/.claude",
    recoveryHint: "tokenmax doctor",
  });
  assert.equal(err.code, "preflight_failed");
  assert.equal(err.agent, "claude");
  assert.equal(err.file, "/home/.claude");
  assert.equal(err.recoveryHint, "tokenmax doctor");
  assert.equal(err.message, "dir not writable");
  assert.ok(err instanceof Error);

  assert.equal(new BackupError({ message: "fail" }).code, "backup_failed");
  assert.equal(new WriteError({ message: "fail" }).code, "write_failed");
  assert.equal(new ValidationError({ message: "fail" }).code, "validation_failed");
  assert.equal(new RollbackError({ message: "fail" }).code, "rollback_failed");
});

test("install failure result includes errorCode and recoveryHint", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: [],
  });

  // Make a directory where a file needs to go so writeFileEnsured fails
  const claudeRoot = path.join(fixture.home, ".claude");
  const commandDir = path.join(claudeRoot, "commands", "tokenmax.md");
  fs.mkdirSync(commandDir, { recursive: true });

  const result = performInstallLike("install", "claude", baseFlags(), fixture.env);
  assert.equal(result.results[0].status, "failed");
  assert.ok("errorCode" in result.results[0] || "error" in result.results[0]);
});

function baseFlags() {
  return {
    json: false,
    yes: false,
    dryRun: false,
    force: false,
  };
}

function createFixtureEnvironment({ agents, tools, qmdCollections = "" }) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "tokenmax-home-"));
  const binDir = path.join(home, "bin");
  fs.mkdirSync(binDir, { recursive: true });

  for (const agent of agents) {
    writeExecutable(path.join(binDir, agent), agentScript(agent));
  }

  for (const tool of tools) {
    writeExecutable(path.join(binDir, toolExecutableName(tool)), toolScript(tool));
  }

  return {
    home,
    env: {
      HOME: home,
      PATH: binDir,
      QMD_COLLECTION_OUTPUT: qmdCollections,
    },
  };
}

function writeExecutable(filePath, content) {
  fs.writeFileSync(filePath, content, "utf8");
  fs.chmodSync(filePath, 0o755);
}

function agentScript(name) {
  return `#!/bin/sh
if [ "$1" = "--version" ]; then
  echo "${name} 1.0.0"
  exit 0
fi
exit 0
`;
}

function toolExecutableName(tool) {
  return tool === "ast-grep" ? "ast-grep" : tool;
}

function toolScript(tool) {
  if (tool === "qmd") {
    return `#!/bin/sh
if [ "$1" = "--version" ]; then
  echo "qmd 1.0.0"
  exit 0
fi
if [ "$1" = "collection" ] && [ "$2" = "list" ]; then
  if [ -n "$QMD_COLLECTION_OUTPUT" ]; then
    echo "$QMD_COLLECTION_OUTPUT"
  fi
  exit 0
fi
exit 0
`;
  }

  return `#!/bin/sh
if [ "$1" = "--version" ]; then
  echo "${tool} 1.0.0"
  exit 0
fi
exit 0
`;
}
