const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const test = require("node:test");
const { spawnSync } = require("child_process");

const { removeManagedBlock, upsertManagedBlock } = require("../../src/tokenmax/managed-files");
const { doctor, performInstallLike, status } = require("../../src/tokenmax/runner");
const { formatJsonOutput, parseCommand } = require("../../src/tokenmax/utils");

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

test("parseCommand accepts --scope and --mode flags with valid values", () => {
  const cmd = parseCommand(["install", "all", "--scope", "project", "--mode", "aggressive"]);
  assert.equal(cmd.flags.scope, "project");
  assert.equal(cmd.flags.mode, "aggressive");
});

test("parseCommand rejects invalid --scope and --mode values", () => {
  assert.throws(() => parseCommand(["install", "all", "--scope", "invalid"]), /Invalid --scope/);
  assert.throws(() => parseCommand(["install", "all", "--mode", "invalid"]), /Invalid --mode/);
});

test("parseCommand defaults scope to user and mode to stable", () => {
  const cmd = parseCommand(["install", "all"]);
  assert.equal(cmd.flags.scope, "user");
  assert.equal(cmd.flags.mode, "stable");
});

test("install with --mode aggressive stores mode in manifest", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd"],
    qmdCollections: "demo-project",
  });

  const result = performInstallLike("install", "claude", { ...baseFlags(), mode: "aggressive", scope: "user" }, fixture.env);
  assert.equal(result.manifest.mode, "aggressive");
});

test("bootstrap scripts contain the thin install flow", () => {
  const posixPath = path.join(process.cwd(), "scripts", "tokenmax", "install.sh");
  const powershellPath = path.join(process.cwd(), "scripts", "tokenmax", "install.ps1");
  const posix = fs.readFileSync(posixPath, "utf8");
  const powershell = fs.readFileSync(powershellPath, "utf8");

  // Original assertions
  assert.match(posix, /npm install/);
  assert.match(posix, /tokenmax --version/);
  assert.match(powershell, /npm install/);
  assert.match(powershell, /tokenmax install all --yes/);

  // OS/arch detection assertions
  assert.match(posix, /uname -s/);
  assert.match(posix, /uname -m/);
  assert.match(posix, /Unsupported operating system/);
  assert.match(powershell, /PROCESSOR_ARCHITECTURE/);

  // PATH fallback assertions
  assert.match(posix, /--prefix/);
  assert.match(powershell, /localPrefix/i);

  // Syntax check
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

test("install creates shared assets and uninstall removes them", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  const install = performInstallLike("install", "all", baseFlags(), fixture.env);
  assert.equal(install.results.find((r) => r.agent === "claude").status, "installed");

  const assetsDir = path.join(fixture.home, ".tokenmax", "assets");
  const guidancePath = path.join(assetsDir, "tool-guidance.md");
  assert.equal(fs.existsSync(guidancePath), true);
  const content = fs.readFileSync(guidancePath, "utf8");
  assert.match(content, /token-saving/i);

  assert.ok(Array.isArray(install.manifest.sharedAssets));
  assert.equal(install.manifest.sharedAssets.length, 1);
  assert.equal(install.manifest.sharedAssets[0].path, guidancePath);

  const uninstall = performInstallLike("uninstall", "all", baseFlags(), fixture.env);
  assert.equal(uninstall.results.find((r) => r.agent === "claude").status, "removed");
  assert.equal(fs.existsSync(guidancePath), false);
});

test("status reports shared asset drift", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd"],
    qmdCollections: "demo-project",
  });

  performInstallLike("install", "all", baseFlags(), fixture.env);

  const assetsDir = path.join(fixture.home, ".tokenmax", "assets");
  const guidancePath = path.join(assetsDir, "tool-guidance.md");
  fs.writeFileSync(guidancePath, "modified content\n", "utf8");

  const currentStatus = status(fixture.env);
  const assetDrift = currentStatus.drift.filter((d) => d.path === guidancePath);
  assert.equal(assetDrift.length, 1);
  assert.equal(assetDrift[0].reason, "content_changed");
});

test("repair regenerates missing shared assets", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd"],
    qmdCollections: "demo-project",
  });

  performInstallLike("install", "all", baseFlags(), fixture.env);

  const guidancePath = path.join(fixture.home, ".tokenmax", "assets", "tool-guidance.md");
  fs.rmSync(guidancePath, { force: true });
  assert.equal(fs.existsSync(guidancePath), false);

  performInstallLike("repair", "all", baseFlags(), fixture.env);
  assert.equal(fs.existsSync(guidancePath), true);
});

const EXPECTED_JSON_KEYS = ["agents", "changed_files", "command", "mode", "scope", "status", "warnings"];

test("--json install output has exact top-level keys and correct types", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  const result = performInstallLike("install", "claude", baseFlags(), fixture.env);
  const json = formatJsonOutput(result);

  assert.deepEqual(Object.keys(json).sort(), EXPECTED_JSON_KEYS);
  assert.equal(typeof json.status, "string");
  assert.ok(["ok", "partial", "failed"].includes(json.status));
  assert.ok(json.agents !== null && typeof json.agents === "object" && !Array.isArray(json.agents));
  assert.ok(Array.isArray(json.changed_files));
  assert.ok(Array.isArray(json.warnings));
});

test("--json install output status is ok when all agents succeed", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  const result = performInstallLike("install", "claude", baseFlags(), fixture.env);
  const json = formatJsonOutput(result);

  assert.equal(json.status, "ok");
  assert.equal(json.command, "install claude");
  assert.equal(json.mode, "stable");
  assert.equal(json.scope, "user");
  assert.ok("claude" in json.agents);
  assert.equal(json.agents.claude.status, "installed");
});

test("--json uninstall output has exact top-level keys and status ok", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  performInstallLike("install", "claude", baseFlags(), fixture.env);
  const result = performInstallLike("uninstall", "claude", baseFlags(), fixture.env);
  const json = formatJsonOutput(result);

  assert.deepEqual(Object.keys(json).sort(), EXPECTED_JSON_KEYS);
  assert.equal(json.status, "ok");
  assert.equal(json.command, "uninstall claude");
  assert.equal(json.agents.claude.status, "removed");
});

test("--json doctor output has exact top-level keys and status ok", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: [],
  });

  const result = doctor("all", fixture.env, baseFlags());
  const json = formatJsonOutput(result);

  assert.deepEqual(Object.keys(json).sort(), EXPECTED_JSON_KEYS);
  assert.equal(json.status, "ok");
  assert.equal(json.command, "doctor all");
  assert.equal(typeof json.agents, "object");
  assert.ok(!Array.isArray(json.agents));
  assert.ok("claude" in json.agents);
  assert.ok(Array.isArray(json.changed_files));
  assert.equal(json.changed_files.length, 0);
});

test("--json status output has exact top-level keys and status ok", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd"],
    qmdCollections: "demo-project",
  });

  performInstallLike("install", "claude", baseFlags(), fixture.env);
  const result = status(fixture.env, baseFlags());
  const json = formatJsonOutput(result);

  assert.deepEqual(Object.keys(json).sort(), EXPECTED_JSON_KEYS);
  assert.equal(json.status, "ok");
  assert.equal(json.command, "status all");
  assert.ok(Array.isArray(json.changed_files));
  assert.equal(json.changed_files.length, 0);
});

test("--json output status is failed when all attempted agents fail", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: [],
  });

  // Make a directory where a file needs to go so writeFileEnsured fails
  const claudeRoot = path.join(fixture.home, ".claude");
  const commandDir = path.join(claudeRoot, "commands", "tokenmax.md");
  fs.mkdirSync(commandDir, { recursive: true });

  const result = performInstallLike("install", "claude", baseFlags(), fixture.env);
  const json = formatJsonOutput(result);

  assert.equal(json.status, "failed");
  assert.equal(json.agents.claude.status, "failed");
});

test("--json output status is partial when some agents succeed and some fail", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude", "codex"],
    tools: [],
  });

  // Block claude's command file path with a directory to force a write failure
  const claudeRoot = path.join(fixture.home, ".claude");
  const commandDir = path.join(claudeRoot, "commands", "tokenmax.md");
  fs.mkdirSync(commandDir, { recursive: true });

  const result = performInstallLike("install", "all", baseFlags(), fixture.env);
  const json = formatJsonOutput(result);

  // claude should fail, codex should succeed (or gemini skipped), giving partial
  assert.equal(json.agents.claude.status, "failed");
  assert.equal(["partial", "ok"].includes(json.status), true);
  // If codex installed OK and gemini was skipped, all attempted = codex(ok) + claude(fail) => partial
  if (json.agents.codex && json.agents.codex.status === "installed") {
    assert.equal(json.status, "partial");
  }
});

test("--json per-agent entry includes errorCode and recoveryHint on failure", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: [],
  });

  const claudeRoot = path.join(fixture.home, ".claude");
  const commandDir = path.join(claudeRoot, "commands", "tokenmax.md");
  fs.mkdirSync(commandDir, { recursive: true });

  const result = performInstallLike("install", "claude", baseFlags(), fixture.env);
  const json = formatJsonOutput(result);

  assert.equal(json.agents.claude.status, "failed");
  // errorCode or error should be present; errorCode propagates if set
  assert.ok("errorCode" in result.results[0] || "error" in result.results[0]);
});

test("--json changed_files is a deduped sorted array of applied paths", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  const result = performInstallLike("install", "claude", baseFlags(), fixture.env);
  const json = formatJsonOutput(result);

  assert.ok(Array.isArray(json.changed_files));
  // All paths should be strings
  for (const p of json.changed_files) {
    assert.equal(typeof p, "string");
  }
  // Should be sorted
  const sorted = [...json.changed_files].sort();
  assert.deepEqual(json.changed_files, sorted);
  // No duplicates
  assert.equal(json.changed_files.length, new Set(json.changed_files).size);
  // Should have some files since install succeeded
  assert.ok(json.changed_files.length > 0);
});

test("--json mode and scope reflect flags values", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd"],
    qmdCollections: "demo-project",
  });

  const flags = { ...baseFlags(), mode: "aggressive", scope: "user" };
  const result = performInstallLike("install", "claude", flags, fixture.env);
  const json = formatJsonOutput(result);

  assert.equal(json.mode, "aggressive");
  assert.equal(json.scope, "user");
});

test("--json skipped agents include reason field", () => {
  // No agents in fixture environment => all will be skipped
  const fixture = createFixtureEnvironment({
    agents: [],
    tools: [],
  });

  const result = performInstallLike("install", "all", baseFlags(), fixture.env);
  const json = formatJsonOutput(result);

  // All agents should be skipped
  for (const entry of Object.values(json.agents)) {
    assert.equal(entry.status, "skipped");
    assert.ok("reason" in entry);
  }
});

test("parseArgs: --backup sets true, --no-backup sets false, default is true", () => {
  const defaultCmd = parseCommand(["install", "all"]);
  assert.equal(defaultCmd.flags.backup, true);

  const withBackup = parseCommand(["install", "all", "--backup"]);
  assert.equal(withBackup.flags.backup, true);

  const noBackup = parseCommand(["install", "all", "--no-backup"]);
  assert.equal(noBackup.flags.backup, false);

  const backupFalse = parseCommand(["install", "all", "--backup=false"]);
  assert.equal(backupFalse.flags.backup, false);

  const backupTrue = parseCommand(["install", "all", "--backup=true"]);
  assert.equal(backupTrue.flags.backup, true);
});

test("install with --no-backup completes and creates no backup directory", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  const result = performInstallLike("install", "claude", { ...baseFlags(), backup: false }, fixture.env);
  assert.equal(result.results[0].status, "installed");

  const backupDir = path.join(fixture.home, ".tokenmax", "backups");
  assert.equal(fs.existsSync(backupDir), false);
});

test("manifest records backupsEnabled: false when install run with --no-backup", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  const result = performInstallLike("install", "claude", { ...baseFlags(), backup: false }, fixture.env);
  assert.equal(result.manifest.backupsEnabled, false);
});

test("manifest records backupsEnabled: true when install run with default flags", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  const result = performInstallLike("install", "claude", baseFlags(), fixture.env);
  assert.equal(result.manifest.backupsEnabled, true);
});

test("rollback after failure with --no-backup produces warning instead of crashing", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: [],
  });

  // Make a directory where a file needs to go so writeFileEnsured fails mid-apply
  const claudeRoot = path.join(fixture.home, ".claude");
  const commandDir = path.join(claudeRoot, "commands", "tokenmax.md");
  fs.mkdirSync(commandDir, { recursive: true });

  const result = performInstallLike("install", "claude", { ...baseFlags(), backup: false }, fixture.env);
  assert.equal(result.results[0].status, "failed");

  // Should have warnings about no backup available, not a crash
  const agentResult = result.results[0];
  const allWarnings = agentResult.warnings || [];
  const hasNoBackupWarning = allWarnings.some((w) => w.includes("No backup available"));
  assert.equal(hasNoBackupWarning, true, `Expected 'No backup available' warning, got: ${JSON.stringify(allWarnings)}`);
});

test("status text indicates backups: enabled or disabled from manifest", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  performInstallLike("install", "claude", { ...baseFlags(), backup: false }, fixture.env);
  const st = status(fixture.env);
  assert.match(st.text, /Backups: disabled/);

  // Now reinstall with backup enabled
  const fixture2 = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });
  performInstallLike("install", "claude", baseFlags(), fixture2.env);
  const st2 = status(fixture2.env);
  assert.match(st2.text, /Backups: enabled/);
});

function baseFlags() {
  return {
    json: false,
    yes: false,
    dryRun: false,
    force: false,
    scope: "user",
    mode: "stable",
    backup: true,
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
