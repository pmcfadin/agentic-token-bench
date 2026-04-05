"use strict";
/**
 * install-detect.js
 *
 * Detects when tokenmax was installed by inspecting well-known artifacts in
 * the user's home directory.
 *
 * Priority order:
 *   1. "marker"  — ~/.tokenmax/installed_at file exists; parse its content as ISO-8601.
 *   2. "claude-md" — TODO: parse git history of ~/.claude/CLAUDE.md for the
 *      first commit that introduced the tokenmax managed block. Skipped for now
 *      because git subprocess calls add complexity and latency.
 *   3. "hook"    — ~/.claude/settings.json mtime, if the file contains a
 *      "PreToolUse" hook pointing at "rtk hook". Used as a proxy for the
 *      install date since tokenmax writes this entry during install.
 *   4. "binary"  — TODO: mtime of the `rtk` binary found via `which rtk`.
 *      Skipped for now (requires subprocess).
 *   5. "none"    — fall-through when no artifact is found.
 *
 * @param {string} homeDir  The user's home directory (e.g. os.homedir())
 * @returns {{ date: Date | null, source: "marker"|"claude-md"|"hook"|"binary"|"none" }}
 */

const fs = require("node:fs");
const path = require("node:path");

function detectInstallDate(homeDir) {
  // -----------------------------------------------------------------------
  // Priority 1: ~/.tokenmax/installed_at
  // -----------------------------------------------------------------------
  const markerFile = path.join(homeDir, ".tokenmax", "installed_at");
  if (fs.existsSync(markerFile)) {
    try {
      const raw = fs.readFileSync(markerFile, "utf8").trim();
      const date = new Date(raw);
      if (!Number.isNaN(date.getTime())) {
        return { date, source: "marker" };
      }
    } catch {
      // fall through to next priority
    }
  }

  // -----------------------------------------------------------------------
  // Priority 2 (TODO): Git history of ~/.claude/CLAUDE.md
  // Parse the first commit that introduced the tokenmax managed block.
  // Skipped: git subprocess calls add complexity and are deferred.
  // -----------------------------------------------------------------------

  // -----------------------------------------------------------------------
  // Priority 3: ~/.claude/settings.json mtime when it contains a PreToolUse
  // hook that invokes "rtk hook".
  // -----------------------------------------------------------------------
  const settingsFile = path.join(homeDir, ".claude", "settings.json");
  if (fs.existsSync(settingsFile)) {
    try {
      const content = fs.readFileSync(settingsFile, "utf8");
      const parsed = JSON.parse(content);
      // Check for a PreToolUse hook that contains "rtk hook"
      const hooks = parsed?.hooks?.PreToolUse;
      const hasRtkHook =
        Array.isArray(hooks) &&
        hooks.some((hook) => {
          // hook may be a string or an object with a command field
          const cmd = typeof hook === "string" ? hook : hook?.command ?? "";
          return typeof cmd === "string" && cmd.includes("rtk hook");
        });

      if (hasRtkHook) {
        const stat = fs.statSync(settingsFile);
        return { date: stat.mtime, source: "hook" };
      }
    } catch {
      // fall through to next priority
    }
  }

  // -----------------------------------------------------------------------
  // Priority 4 (TODO): mtime of the `rtk` binary found via `which rtk`.
  // Skipped: requires subprocess; deferred.
  // -----------------------------------------------------------------------

  return { date: null, source: "none" };
}

module.exports = { detectInstallDate };
