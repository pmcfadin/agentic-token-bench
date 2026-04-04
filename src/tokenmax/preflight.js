const fs = require("fs");
const path = require("path");
const { PreflightError } = require("./errors");
const { ensureDir } = require("./utils");

/**
 * Run preflight checks before any install/repair action.
 *
 * @param {string[]} ids - Agent IDs to check
 * @param {Object} adapterMap - Map of agent ID -> adapter
 * @param {Object} probes - Result of gatherProbes(): { platform, agents, tools }
 * @param {Object} flags - Command flags: { force, dryRun, ... }
 * @returns {{ checks: Array, errors: Array, warnings: Array }}
 */
function runPreflight(ids, adapterMap, probes, flags = {}) {
  const checks = [];

  // OS check: hard fail on unsupported platforms
  if (["aix", "sunos"].includes(process.platform)) {
    checks.push({
      agent: null,
      file: null,
      reason: `Unsupported OS: ${process.platform}`,
      severity: "error",
    });
  }

  // Per-agent config root writability check
  for (const id of ids) {
    const probe = probes.agents && probes.agents[id];
    if (!probe || !probe.configRoot) continue;

    // Only check agents that are present (others will be skipped anyway)
    if (probe.status !== "present") continue;

    try {
      // In dry-run mode, only test writability if the dir already exists.
      // Nonexistent dirs are fine for dry-run — they'd be created on the real install.
      if (flags.dryRun) {
        const dirExists = fs.existsSync(probe.configRoot);
        if (!dirExists) continue;
        // Dir exists; test that it's writable
        const marker = path.join(probe.configRoot, ".tokenmax-preflight");
        fs.writeFileSync(marker, "ok", "utf8");
        fs.rmSync(marker, { force: true });
      } else {
        ensureDir(probe.configRoot);
        const marker = path.join(probe.configRoot, ".tokenmax-preflight");
        fs.writeFileSync(marker, "ok", "utf8");
        fs.rmSync(marker, { force: true });
      }
    } catch (err) {
      checks.push({
        agent: id,
        file: probe.configRoot,
        reason: `Not writable: ${err.message}`,
        severity: "error",
      });
    }
  }

  // Helper tools check (warning only, --force suppresses)
  const toolValues = Object.values(probes.tools || {});
  const helperCount = toolValues.filter((t) => t.status === "present").length;
  if (helperCount === 0 && !flags.force) {
    checks.push({
      agent: null,
      file: null,
      reason: "No token-saving helper tools detected on PATH",
      severity: "warning",
    });
  }

  return {
    checks,
    errors: checks.filter((c) => c.severity === "error"),
    warnings: checks.filter((c) => c.severity === "warning"),
  };
}

/**
 * Throw a PreflightError if the preflight result contains any errors.
 *
 * @param {{ checks: Array, errors: Array, warnings: Array }} result
 */
function assertPreflight(result) {
  if (result.errors.length > 0) {
    const err = new PreflightError({
      message: `Preflight failed with ${result.errors.length} error(s)`,
      agent: result.errors[0].agent,
      file: result.errors[0].file,
      recoveryHint:
        "Fix the failing checks and retry, or run with --force to bypass warnings only",
    });
    err.checks = result.checks;
    throw err;
  }
}

module.exports = { runPreflight, assertPreflight };
