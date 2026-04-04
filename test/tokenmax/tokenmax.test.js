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

test("install creates shared assets and uninstall removes them", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd", "rtk"],
    qmdCollections: "demo-project",
  });

  const install = performInstallLike("install", "claude", baseFlags(), fixture.env);
  assert.equal(install.results[0].status, "installed");

  const assetsDir = path.join(fixture.home, ".tokenmax", "assets");
  const guidancePath = path.join(assetsDir, "tool-guidance.md");
  assert.equal(fs.existsSync(guidancePath), true);
  const content = fs.readFileSync(guidancePath, "utf8");
  assert.match(content, /token-saving/i);

  assert.ok(Array.isArray(install.manifest.sharedAssets));
  assert.equal(install.manifest.sharedAssets.length, 1);
  assert.equal(install.manifest.sharedAssets[0].path, guidancePath);

  const uninstall = performInstallLike("uninstall", "claude", baseFlags(), fixture.env);
  assert.equal(uninstall.results[0].status, "removed");
  assert.equal(fs.existsSync(guidancePath), false);
});

test("status reports shared asset drift", () => {
  const fixture = createFixtureEnvironment({
    agents: ["claude"],
    tools: ["qmd"],
    qmdCollections: "demo-project",
  });

  performInstallLike("install", "claude", baseFlags(), fixture.env);

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

  performInstallLike("install", "claude", baseFlags(), fixture.env);

  const guidancePath = path.join(fixture.home, ".tokenmax", "assets", "tool-guidance.md");
  fs.rmSync(guidancePath, { force: true });
  assert.equal(fs.existsSync(guidancePath), false);

  performInstallLike("repair", "claude", baseFlags(), fixture.env);
  assert.equal(fs.existsSync(guidancePath), true);
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
