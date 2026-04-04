const fs = require("fs");
const path = require("path");
const { statePaths, VERSION } = require("./constants");
const { ensureDir, hashContent, isoTimestamp, readFileIfExists, stableStringify, writeFileEnsured } = require("./utils");

function initializeState(homeDir, now = new Date(), flags = {}) {
  const paths = statePaths(homeDir);
  ensureDir(paths.root);
  ensureDir(paths.manifestsDir);
  ensureDir(paths.logsDir);
  ensureDir(paths.assetsDir);

  const runId = isoTimestamp(now);

  let backupRoot = null;
  if (flags.backup !== false) {
    ensureDir(paths.backupsDir);
    backupRoot = path.join(paths.backupsDir, runId);
    ensureDir(backupRoot);
  }

  return { ...paths, runId, backupRoot };
}

function loadCurrentState(homeDir) {
  const paths = statePaths(homeDir);
  const raw = readFileIfExists(paths.current);
  if (!raw) {
    return null;
  }
  return JSON.parse(raw);
}

function recordBackup(backupRoot, filePath, content) {
  if (backupRoot == null) {
    return null;
  }
  const safeName = filePath.replace(/[/:\\]/g, "__");
  const target = path.join(backupRoot, safeName);
  writeFileEnsured(target, content == null ? "" : content);
  return target;
}

function saveManifest(homeDir, manifest) {
  const paths = statePaths(homeDir);
  ensureDir(paths.manifestsDir);
  writeFileEnsured(paths.current, `${stableStringify(manifest)}\n`);
  const historyPath = path.join(paths.manifestsDir, `${manifest.runId}.json`);
  writeFileEnsured(historyPath, `${stableStringify(manifest)}\n`);
  return historyPath;
}

function makeManifest({ homeDir, runId, backupRoot, mode, probes, results, sharedAssets, backupsEnabled }) {
  return {
    version: VERSION,
    runId,
    homeDir,
    backupRoot,
    backupsEnabled: backupsEnabled !== false,
    mode,
    installedAt: new Date().toISOString(),
    probes,
    results,
    sharedAssets: sharedAssets || [],
  };
}

function captureChangeRecord(change, content, backupPath, validation = "pending") {
  const fragmentForHash =
    change.ownership === "json-fragment" &&
    change.jsonFragment &&
    change.jsonFragment.hooks &&
    Array.isArray(change.jsonFragment.hooks.PreToolUse)
      ? change.jsonFragment.hooks.PreToolUse[0] || {}
      : change.jsonFragment || {};

  return {
    path: change.path,
    ownership: change.ownership,
    backupPath,
    validation,
    contentHash: hashContent(content),
    blockHash: change.ownership === "managed-block" ? hashContent(change.managedBlock || "") : null,
    fragmentHash: change.ownership === "json-fragment" ? hashContent(stableStringify(fragmentForHash)) : null,
  };
}

module.exports = {
  captureChangeRecord,
  initializeState,
  loadCurrentState,
  makeManifest,
  recordBackup,
  saveManifest,
};
