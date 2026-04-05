const fs = require("fs");
const path = require("path");
const { AGENT_IDS, VERSION, statePaths } = require("./constants");
const { claudeAdapter, CLAUDE_HOOK } = require("./agents/claude");
const { codexAdapter } = require("./agents/codex");
const { geminiAdapter } = require("./agents/gemini");
const { BackupError, PreflightError, RollbackError, ValidationError, WriteError } = require("./errors");
const { runPreflight, assertPreflight } = require("./preflight");
const { extractManagedBlock, removeManagedBlock, upsertManagedBlock } = require("./managed-files");
const { probeAgents, probeTools, findProjectRoot } = require("./probe");
const { captureChangeRecord, findChangeRecord, initializeState, loadCurrentState, makeManifest, recordBackup, saveManifest } = require("./state");
const { renderToolGuidance } = require("./templates");
const { ensureDir, getPlatform, hashContent, readFileIfExists, removeFileIfExists, stableStringify, writeFileEnsured } = require("./utils");

function adapters() {
  return {
    claude: claudeAdapter(),
    codex: codexAdapter(),
    gemini: geminiAdapter(),
  };
}

function selectedAgents(target) {
  if (target === "all") {
    return AGENT_IDS;
  }
  if (!AGENT_IDS.includes(target)) {
    throw new Error(`Unsupported agent target: ${target}`);
  }
  return [target];
}

function gatherProbes(env = process.env) {
  return {
    platform: getPlatform(env),
    agents: probeAgents(env),
    tools: probeTools(env),
  };
}

function summarizeToolWarnings(tools) {
  const warnings = [];
  for (const tool of Object.values(tools)) {
    if (tool.status === "missing") {
      warnings.push(`${tool.id} is not installed on PATH.`);
    } else if (tool.status === "broken") {
      warnings.push(`${tool.id} is on PATH but its version check failed.`);
    }
    for (const warning of tool.warnings || []) {
      warnings.push(warning);
    }
  }
  return warnings;
}

function doctor(target, env = process.env, flags = {}) {
  const probes = gatherProbes(env);
  const selected = selectedAgents(target);
  const warnings = summarizeToolWarnings(probes.tools);
  const agentResults = selected.map((id) => ({
    id,
    status: probes.agents[id].status,
    executable: probes.agents[id].executable,
    configRoot: probes.agents[id].configRoot,
    supportedSurfaces: probes.agents[id].supportedSurfaces,
  }));

  // Collect-and-report only; doctor never calls assertPreflight.
  const preflight = runPreflight(selected, probes, flags);

  return {
    ok: true,
    version: VERSION,
    action: "doctor",
    target,
    mode: flags.mode || "stable",
    scope: flags.scope || "user",
    platform: probes.platform,
    agents: agentResults,
    tools: probes.tools,
    warnings,
    preflight,
    text: renderDoctorText(probes, selected, warnings, preflight),
  };
}

function renderDoctorText(probes, selected, warnings, preflight) {
  const lines = [
    `tokenmax ${VERSION}`,
    `Platform: ${probes.platform.platform}/${probes.platform.arch}`,
    "",
    "Agents:",
  ];
  for (const id of selected) {
    const agent = probes.agents[id];
    lines.push(`- ${id}: ${agent.status} (${agent.configRoot})`);
  }
  lines.push("", "Tools:");
  for (const tool of Object.values(probes.tools)) {
    lines.push(`- ${tool.id}: ${tool.status}${tool.executable ? ` (${tool.executable})` : ""}`);
  }
  if (warnings.length > 0) {
    lines.push("", "Warnings:");
    for (const warning of warnings) {
      lines.push(`- ${warning}`);
    }
  }
  if (preflight && preflight.checks.length > 0) {
    lines.push("", "Preflight:");
    for (const check of preflight.checks) {
      const loc = check.agent ? ` [${check.agent}]` : "";
      lines.push(`- [${check.severity}]${loc} ${check.reason}`);
    }
  }
  return lines.join("\n");
}

function installSharedAssets(state, probes, flags) {
  const guidancePath = path.join(state.assetsDir, "tool-guidance.md");
  const sharedAssets = [];

  if (flags.dryRun) {
    sharedAssets.push({
      path: guidancePath,
      ownership: "generated",
      contentHash: null,
      applied: false,
    });
    return sharedAssets;
  }

  ensureDir(state.assetsDir);

  const content = renderToolGuidance(probes.tools) + "\n";
  const existing = readFileIfExists(guidancePath);
  if (state.backupRoot) {
    recordBackup(state.backupRoot, guidancePath, existing);
  }

  writeFileEnsured(guidancePath, content);

  sharedAssets.push({
    path: guidancePath,
    ownership: "generated",
    contentHash: hashContent(content),
    applied: true,
  });

  return sharedAssets;
}

function removeSharedAssets(state, flags) {
  if (flags.dryRun) return;

  const guidancePath = path.join(state.assetsDir, "tool-guidance.md");
  const existing = readFileIfExists(guidancePath);
  if (existing != null && state.backupRoot) {
    recordBackup(state.backupRoot, guidancePath, existing);
  }
  removeFileIfExists(guidancePath);
}

function computeSharedAssetDrift(sharedAssets) {
  const drift = [];
  for (const asset of sharedAssets || []) {
    const currentContent = readFileIfExists(asset.path);
    if (!currentContent) {
      drift.push({ path: asset.path, reason: "missing" });
      continue;
    }
    if (asset.contentHash && hashContent(currentContent) !== asset.contentHash) {
      drift.push({ path: asset.path, reason: "content_changed" });
    }
  }
  return drift;
}

function performInstallLike(action, target, flags, env = process.env) {
  const probes = gatherProbes(env);
  const ids = selectedAgents(target);
  const adapterMap = adapters();
  const homeDir = probes.platform.homeDir;

  // Apply scope override BEFORE preflight so writability checks hit the actual target dirs.
  if (flags.scope === "project") {
    const projectRoot = findProjectRoot(process.cwd());
    if (!projectRoot) {
      return {
        ok: false,
        version: VERSION,
        action,
        target,
        mode: flags.mode || "stable",
        scope: flags.scope || "user",
        error: "No project root found (no .git directory in parent chain)",
        text: "Error: --scope project requires a git repository. No .git found.",
      };
    }
    for (const id of ids) {
      const agent = probes.agents[id];
      if (agent.status === "present") {
        agent.configRoot = projectRoot;
      }
    }
  }

  try {
    const preflightResult = runPreflight(ids, probes, flags);
    assertPreflight(preflightResult);
  } catch (err) {
    if (err instanceof PreflightError) {
      return {
        ok: false,
        version: VERSION,
        action,
        target,
        mode: flags.mode || "stable",
        scope: flags.scope || "user",
        errorCode: err.code,
        error: err.message,
        recoveryHint: err.recoveryHint,
        checks: err.checks || [],
        results: [],
        warnings: summarizeToolWarnings(probes.tools),
        text: `Error: ${err.message}`,
      };
    }
    throw err;
  }

  const state = flags.dryRun
    ? {
        runId: "dry-run",
        backupRoot: null,
        assetsDir: statePaths(homeDir).assetsDir,
      }
    : initializeState(homeDir, new Date(), flags);
  const results = [];
  const globalWarnings = summarizeToolWarnings(probes.tools);

  // Shared assets are managed only on "all" targets to avoid breaking other
  // agents' references when uninstalling a single agent.
  let sharedAssets = [];
  if (target === "all") {
    if (action === "uninstall") {
      removeSharedAssets(state, flags);
    } else {
      sharedAssets = installSharedAssets(state, probes, flags);
    }
  }

  const priorManifest = action === "uninstall" ? loadCurrentState(homeDir) : null;

  for (const id of ids) {
    const adapter = adapterMap[id];
    const agent = adapter.probe(probes);
    if (agent.status !== "present") {
      results.push({
        agent: id,
        status: "skipped",
        reason: "agent_missing",
        changes: [],
      });
      continue;
    }

    const changes = adapter.planChanges({
      action,
      flags,
      agent,
      tools: probes.tools,
      probes,
      mode: flags.mode || "stable",
    });

    if (action === "uninstall") {
      results.push(applyUninstall(agent, changes, state, flags, priorManifest));
      continue;
    }

    results.push(applyInstall(action, adapter, agent, changes, state, flags));
  }

  const manifest = makeManifest({
    homeDir,
    runId: state.runId,
    backupRoot: state.backupRoot,
    mode: flags.mode || "stable",
    probes,
    results,
    sharedAssets,
    backupsEnabled: flags.backup !== false,
  });

  if (!flags.dryRun && action !== "doctor") {
    saveManifest(homeDir, manifest);
  }

  return {
    ok: results.every((result) => ["installed", "repaired", "removed", "skipped", "dry-run"].includes(result.status)),
    version: VERSION,
    action,
    target,
    mode: flags.mode || "stable",
    scope: flags.scope || "user",
    runId: state.runId,
    results,
    warnings: globalWarnings,
    manifest: flags.dryRun ? null : manifest,
    text: renderActionText(action, results, globalWarnings, flags),
  };
}

function applyInstall(action, adapter, agent, changes, state, flags) {
  const actionStatus = flags.dryRun ? "dry-run" : action === "repair" ? "repaired" : "installed";
  const appliedChanges = [];
  const rollbackStack = [];

  try {
    for (const change of changes) {
      if (flags.dryRun) {
        appliedChanges.push({
          path: change.path,
          ownership: change.ownership,
          applied: false,
        });
        continue;
      }

      const existing = readFileIfExists(change.path);
      let backupPath;
      try {
        backupPath = recordBackup(state.backupRoot, change.path, existing);
      } catch (err) {
        throw new BackupError({
          message: err.message,
          agent: agent.id,
          file: change.path,
          recoveryHint: null,
        });
      }
      rollbackStack.push({ path: change.path, hadExisting: existing != null, backupPath });

      let nextContent;
      if (change.ownership === "managed-block") {
        nextContent = upsertManagedBlock(existing, change.managedBlock);
      } else if (change.ownership === "generated") {
        nextContent = change.content;
      } else if (change.ownership === "json-fragment") {
        nextContent = applyClaudeHook(existing, change.jsonFragment);
      } else {
        throw new Error(`Unsupported change ownership: ${change.ownership}`);
      }

      try {
        writeFileEnsured(change.path, nextContent);
      } catch (err) {
        throw new WriteError({
          message: err.message,
          agent: agent.id,
          file: change.path,
          recoveryHint: null,
        });
      }
      appliedChanges.push({
        ...captureChangeRecord(change, nextContent, backupPath, "ok"),
        applied: true,
      });
    }

    if (flags.dryRun) {
      return {
        agent: agent.id,
        status: actionStatus,
        changes: appliedChanges,
      };
    }

    const validation = adapter.validate(appliedChanges);
    if (validation.length > 0) {
      throw new ValidationError({
        message: validation.join("; "),
        agent: agent.id,
        file: null,
        recoveryHint: null,
      });
    }

    return {
      agent: agent.id,
      status: actionStatus,
      changes: appliedChanges,
    };
  } catch (error) {
    if (!flags.force && !flags.dryRun) {
      const rollbackWarnings = [];
      try {
        rollbackChanges(rollbackStack, { warnings: rollbackWarnings });
      } catch (rollbackErr) {
        // Rollback failed — surface that, but preserve the original cause.
        rollbackErr.cause = error;
        return {
          agent: agent.id,
          status: "failed",
          error: rollbackErr.message,
          errorCode: rollbackErr.code || null,
          recoveryHint: rollbackErr.recoveryHint || null,
          originalError: error.message,
          warnings: rollbackWarnings.length > 0 ? rollbackWarnings : undefined,
          changes: appliedChanges,
        };
      }
      if (rollbackWarnings.length > 0) {
        return {
          agent: agent.id,
          status: "failed",
          error: error.message,
          errorCode: error.code || null,
          recoveryHint: error.recoveryHint || null,
          warnings: rollbackWarnings,
          changes: appliedChanges,
        };
      }
    }
    return {
      agent: agent.id,
      status: "failed",
      error: error.message,
      errorCode: error.code || null,
      recoveryHint: error.recoveryHint || null,
      changes: appliedChanges,
    };
  }
}

function applyUninstall(agent, changes, state, flags, priorManifest) {
  const appliedChanges = [];
  const preservedFiles = [];

  for (const change of changes) {
    if (flags.dryRun) {
      appliedChanges.push({ path: change.path, ownership: change.ownership, applied: false });
      continue;
    }

    const existing = readFileIfExists(change.path);
    if (existing == null) {
      continue;
    }
    const backupPath = recordBackup(state.backupRoot, change.path, existing);
    if (change.ownership === "managed-block") {
      const nextContent = removeManagedBlock(existing);
      if (nextContent) {
        writeFileEnsured(change.path, nextContent);
      } else {
        removeFileIfExists(change.path);
      }
      appliedChanges.push({
        path: change.path,
        ownership: change.ownership,
        applied: true,
        backupPath,
      });
    } else if (change.ownership === "generated") {
      const record = findChangeRecord(priorManifest, agent.id, change.path);
      if (record && record.contentHash && !flags.force) {
        const currentHash = hashContent(existing);
        if (currentHash !== record.contentHash) {
          preservedFiles.push(change.path);
          appliedChanges.push({
            path: change.path,
            ownership: change.ownership,
            applied: false,
            preserved: true,
          });
          continue;
        }
      }
      removeFileIfExists(change.path);
      appliedChanges.push({
        path: change.path,
        ownership: change.ownership,
        applied: true,
        backupPath,
      });
    } else if (change.ownership === "json-fragment") {
      const nextContent = removeClaudeHook(existing);
      if (nextContent) {
        writeFileEnsured(change.path, nextContent);
      } else {
        removeFileIfExists(change.path);
      }
      appliedChanges.push({
        path: change.path,
        ownership: change.ownership,
        applied: true,
        backupPath,
      });
    }
  }

  const result = {
    agent: agent.id,
    status: flags.dryRun ? "dry-run" : "removed",
    changes: appliedChanges,
  };

  if (preservedFiles.length > 0) {
    result.preservedFiles = preservedFiles;
    result.warnings = preservedFiles.map((p) => `Preserved ${p}: modified since install`);
  }

  return result;
}

function rollbackChanges(rollbackStack, options = {}) {
  const warnings = options.warnings || [];
  for (let index = rollbackStack.length - 1; index >= 0; index -= 1) {
    const item = rollbackStack[index];
    if (item.backupPath == null) {
      warnings.push(`No backup available for ${item.path}; manual recovery required`);
      continue;
    }
    try {
      const backupContent = fs.readFileSync(item.backupPath, "utf8");
      if (item.hadExisting) {
        writeFileEnsured(item.path, backupContent);
      } else {
        removeFileIfExists(item.path);
      }
    } catch (err) {
      throw new RollbackError({
        message: `Rollback failed for ${item.path}: ${err.message}`,
        agent: null,
        file: item.path,
        recoveryHint: `Manually restore from backup: ${item.backupPath}`,
      });
    }
  }
}

function applyClaudeHook(existingContent, fragment) {
  const current = existingContent ? JSON.parse(existingContent) : {};
  current.hooks = current.hooks || {};
  current.hooks.PreToolUse = current.hooks.PreToolUse || [];
  const hookList = current.hooks.PreToolUse;
  const candidate = fragment.hooks.PreToolUse[0];
  const hasExisting = hookList.some((entry) => stableStringify(entry) === stableStringify(candidate));
  if (!hasExisting) {
    hookList.push(candidate);
  }
  return `${stableStringify(current)}\n`;
}

function removeClaudeHook(existingContent) {
  const current = existingContent ? JSON.parse(existingContent) : {};
  if (!current.hooks || !Array.isArray(current.hooks.PreToolUse)) {
    return existingContent;
  }
  const target = stableStringify(CLAUDE_HOOK.hooks.PreToolUse[0]);
  current.hooks.PreToolUse = current.hooks.PreToolUse.filter(
    (entry) => stableStringify(entry) !== target
  );
  if (current.hooks.PreToolUse.length === 0) {
    delete current.hooks.PreToolUse;
  }
  if (current.hooks && Object.keys(current.hooks).length === 0) {
    delete current.hooks;
  }
  if (Object.keys(current).length === 0) {
    return "";
  }
  return `${stableStringify(current)}\n`;
}

function extractClaudeHook(existingContent) {
  const current = existingContent ? JSON.parse(existingContent) : {};
  const hookList = current.hooks && Array.isArray(current.hooks.PreToolUse) ? current.hooks.PreToolUse : [];
  const target = stableStringify(CLAUDE_HOOK.hooks.PreToolUse[0]);
  const match = hookList.find((entry) => stableStringify(entry) === target);
  return match || {};
}

function status(env = process.env, flags = {}) {
  const probes = gatherProbes(env);
  const homeDir = probes.platform.homeDir;
  const current = loadCurrentState(homeDir);
  const drift = current ? computeDrift(current.results) : [];
  const assetDrift = current ? computeSharedAssetDrift(current.sharedAssets) : [];
  const allDrift = [...drift, ...assetDrift];
  return {
    ok: true,
    version: VERSION,
    action: "status",
    target: "all",
    mode: flags.mode || "stable",
    scope: flags.scope || "user",
    current,
    drift: allDrift,
    warnings: summarizeToolWarnings(probes.tools),
    text: renderStatusText(current, allDrift),
  };
}

function computeDrift(results) {
  const drift = [];
  for (const result of results) {
    for (const change of result.changes || []) {
      const currentContent = readFileIfExists(change.path);
      if (!currentContent) {
        drift.push({ path: change.path, reason: "missing" });
        continue;
      }
      if (change.ownership === "managed-block") {
        const block = extractManagedBlock(currentContent);
        const currentHash = block ? hashContent(block) : null;
        if (currentHash !== change.blockHash) {
          drift.push({ path: change.path, reason: "managed_block_changed" });
        }
      } else if (change.ownership === "json-fragment") {
        const currentHash = hashContent(stableStringify(extractClaudeHook(currentContent)));
        if (currentHash !== change.fragmentHash) {
          drift.push({ path: change.path, reason: "json_fragment_changed" });
        }
      } else if (change.contentHash && hashContent(currentContent) !== change.contentHash) {
        drift.push({ path: change.path, reason: "content_changed" });
      }
    }
  }
  return drift;
}

function renderStatusText(current, drift) {
  if (!current) {
    return "No tokenmax install state found.";
  }
  const backupsLabel = current.backupsEnabled === false ? "disabled" : "enabled";
  const lines = [
    `tokenmax ${current.version}`,
    `Last run: ${current.runId}`,
    `Mode: ${current.mode}`,
    `Backups: ${backupsLabel}`,
    "",
    "Agents:",
  ];
  for (const result of current.results) {
    lines.push(`- ${result.agent}: ${result.status}`);
  }
  if (drift.length > 0) {
    lines.push("", "Drift:");
    for (const item of drift) {
      lines.push(`- ${item.path}: ${item.reason}`);
    }
  } else {
    lines.push("", "Drift: none");
  }
  return lines.join("\n");
}

function renderActionText(action, results, warnings, flags) {
  const lines = [`tokenmax ${action}${flags.dryRun ? " (dry-run)" : ""}`];
  for (const result of results) {
    lines.push(`- ${result.agent}: ${result.status}${result.reason ? ` (${result.reason})` : ""}`);
    if (result.error) {
      lines.push(`  ${result.error}`);
    }
  }

  const allPreserved = results.flatMap((result) => result.preservedFiles || []);
  if (allPreserved.length > 0) {
    lines.push("", "Preserved due to user modifications:");
    for (const filePath of allPreserved) {
      lines.push(`- ${filePath}`);
    }
  }

  if (warnings.length > 0) {
    lines.push("", "Warnings:");
    for (const warning of warnings) {
      lines.push(`- ${warning}`);
    }
  }
  return lines.join("\n");
}

module.exports = {
  doctor,
  performInstallLike,
  status,
};
