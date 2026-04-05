const fs = require("fs");
const { PreflightError } = require("./errors");
const { ensureWritableConfigRoot } = require("./probe");

/**
 * Run preflight checks before any install/repair action.
 *
 * @param {string[]} ids - Agent IDs to check
 * @param {Object} probes - Result of gatherProbes(): { platform, agents, tools }
 * @param {Object} flags - Command flags: { force, dryRun, ... }
 * @returns {{ checks: Array, errors: Array, warnings: Array }}
 */
function runPreflight(ids, probes, flags = {}) {
  const checks = [];

  if (["aix", "sunos"].includes(process.platform)) {
    checks.push({
      agent: null,
      file: null,
      reason: `Unsupported OS: ${process.platform}`,
      severity: "error",
    });
  }

  for (const id of ids) {
    const probe = probes.agents && probes.agents[id];
    if (!probe || !probe.configRoot) continue;
    if (probe.status !== "present") continue;

    // In dry-run mode, nonexistent dirs aren't a failure — a real install would create them.
    if (flags.dryRun && !fs.existsSync(probe.configRoot)) continue;

    try {
      ensureWritableConfigRoot(probe.configRoot);
    } catch (err) {
      checks.push({
        agent: id,
        file: probe.configRoot,
        reason: `Not writable: ${err.message}`,
        severity: "error",
      });
    }
  }

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
