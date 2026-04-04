const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { AGENT_IDS, TOOL_IDS } = require("./constants");
const { ensureDir, fileExists, getHomeDir } = require("./utils");

function findExecutable(candidates, env = process.env) {
  const pathValue = env.PATH || "";
  const segments = pathValue.split(path.delimiter).filter(Boolean);
  const executableCandidates = process.platform === "win32"
    ? candidates.flatMap((candidate) => [candidate, `${candidate}.exe`, `${candidate}.cmd`, `${candidate}.bat`])
    : candidates;

  for (const segment of segments) {
    for (const candidate of executableCandidates) {
      const fullPath = path.join(segment, candidate);
      if (fileExists(fullPath)) {
        return fullPath;
      }
    }
  }

  return null;
}

function probeCommandVersion(executable, args) {
  try {
    return execFileSync(executable, args, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
  } catch (_error) {
    return null;
  }
}

function qmdWarnings(executable) {
  try {
    const output = execFileSync(executable, ["collection", "list"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }).trim();
    if (!output) {
      return ["qmd is installed but has no registered collections."];
    }
    return [];
  } catch (_error) {
    return ["qmd is installed but `qmd collection list` did not complete cleanly."];
  }
}

function probeTools(env = process.env) {
  const definitions = {
    qmd: { executables: ["qmd"], versionArgs: ["--version"] },
    rtk: { executables: ["rtk"], versionArgs: ["--version"] },
    rg: { executables: ["rg"], versionArgs: ["--version"] },
    "ast-grep": { executables: ["ast-grep", "sg"], versionArgs: ["--version"] },
    comby: { executables: ["comby"], versionArgs: ["--version"] },
    fastmod: { executables: ["fastmod"], versionArgs: ["--version"] },
  };

  return TOOL_IDS.reduce((accumulator, id) => {
    const definition = definitions[id];
    const executable = findExecutable(definition.executables, env);
    if (!executable) {
      accumulator[id] = { id, executable: null, version: null, status: "missing", warnings: [] };
      return accumulator;
    }

    const version = probeCommandVersion(executable, definition.versionArgs);
    const warnings = id === "qmd" ? qmdWarnings(executable) : [];
    accumulator[id] = {
      id,
      executable,
      version,
      status: version ? "present" : "broken",
      warnings,
    };
    return accumulator;
  }, {});
}

function agentConfigRoots(homeDir = getHomeDir()) {
  return {
    claude: path.join(homeDir, ".claude"),
    codex: path.join(homeDir, ".codex"),
    gemini: path.join(homeDir, ".gemini"),
  };
}

function probeAgents(env = process.env) {
  const homeDir = getHomeDir(env);
  const configRoots = agentConfigRoots(homeDir);
  const definitions = {
    claude: { executableNames: ["claude"], surfaces: ["CLAUDE.md", "commands", "settings.json"] },
    codex: { executableNames: ["codex"], surfaces: ["AGENTS.md", "skills"] },
    gemini: { executableNames: ["gemini"], surfaces: ["GEMINI.md", "commands"] },
  };

  return AGENT_IDS.reduce((accumulator, id) => {
    const definition = definitions[id];
    const executable = findExecutable(definition.executableNames, env);
    const configRoot = configRoots[id];
    const configExists = fileExists(configRoot);
    const status = executable || configExists ? "present" : "missing";
    accumulator[id] = {
      id,
      executable,
      configRoot,
      supportedSurfaces: definition.surfaces,
      status,
      warnings: [],
    };
    return accumulator;
  }, {});
}

function ensureWritableConfigRoot(configRoot) {
  ensureDir(configRoot);
  const markerPath = path.join(configRoot, ".tokenmax-write-test");
  fs.writeFileSync(markerPath, "ok", "utf8");
  fs.rmSync(markerPath, { force: true });
}

function findProjectRoot(startDir) {
  let current = path.resolve(startDir);
  const root = path.parse(current).root;
  while (current !== root) {
    if (fileExists(path.join(current, ".git"))) {
      return current;
    }
    current = path.dirname(current);
  }
  return null;
}

module.exports = {
  agentConfigRoots,
  ensureWritableConfigRoot,
  findExecutable,
  findProjectRoot,
  probeAgents,
  probeTools,
};
