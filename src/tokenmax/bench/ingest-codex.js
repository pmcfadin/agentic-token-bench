"use strict";
/**
 * ingest-codex.js
 *
 * Reads Codex CLI session transcripts from:
 *   <codexHome>/sessions/YYYY/MM/DD/rollout-*.jsonl
 *
 * Each JSONL file may contain:
 *   - A "session_meta" line (type === "session_meta") carrying session id, cwd,
 *     and optionally model.
 *   - "event_msg" lines (type === "event_msg") with payload.type === "token_count"
 *     and payload.info non-null. Lines with info === null are silently skipped
 *     (pre-PR#1583 style, schema-drift rule).
 *
 * Token mapping from payload.info.last_token_usage:
 *   input_tokens          = last.input_tokens - last.cached_input_tokens  (floor 0)
 *   output_tokens         = last.output_tokens + (last.reasoning_output_tokens || 0)
 *   cache_read_tokens     = last.cached_input_tokens
 *   cache_creation_tokens = 0
 *   tool_calls            = 0
 */

const fs = require("node:fs");
const path = require("node:path");
const { makeTurn } = require("./models");

/**
 * Walk YYYY/MM/DD sub-tree and collect all .jsonl file paths.
 * @param {string} sessionsDir
 * @returns {string[]}
 */
function collectJsonlFiles(sessionsDir) {
  const result = [];
  if (!fs.existsSync(sessionsDir)) return result;

  for (const year of fs.readdirSync(sessionsDir)) {
    const yearPath = path.join(sessionsDir, year);
    if (!fs.statSync(yearPath).isDirectory()) continue;

    for (const month of fs.readdirSync(yearPath)) {
      const monthPath = path.join(yearPath, month);
      if (!fs.statSync(monthPath).isDirectory()) continue;

      for (const day of fs.readdirSync(monthPath)) {
        const dayPath = path.join(monthPath, day);
        if (!fs.statSync(dayPath).isDirectory()) continue;

        for (const entry of fs.readdirSync(dayPath)) {
          if (entry.endsWith(".jsonl")) {
            result.push(path.join(dayPath, entry));
          }
        }
      }
    }
  }

  return result;
}

/**
 * @param {string} codexHome  Path to ~/.codex (or equivalent)
 * @param {{ since?: Date, cwd?: string }} [opts]
 * @returns {import('./models').TurnRecord[]}
 */
function ingestCodexDir(codexHome, { since, cwd } = {}) {
  const sessionsDir = path.join(codexHome, "sessions");
  const files = collectJsonlFiles(sessionsDir);

  const records = [];

  for (const filePath of files) {
    const lines = fs.readFileSync(filePath, "utf8").split("\n");

    // First pass: extract session_meta (session id, cwd, model)
    let sessionId = path.basename(filePath, ".jsonl");
    let sessionCwd = null;
    let sessionModel = "codex";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      let obj;
      try {
        obj = JSON.parse(trimmed);
      } catch {
        continue;
      }

      if (obj.type === "session_meta" && obj.payload) {
        if (obj.payload.id) sessionId = String(obj.payload.id);
        if (obj.payload.cwd) sessionCwd = String(obj.payload.cwd);
        if (obj.payload.model) sessionModel = String(obj.payload.model);
        break; // session_meta is typically the first line
      }
    }

    // Apply cwd filter
    if (cwd != null && (sessionCwd == null || !sessionCwd.startsWith(cwd))) {
      continue;
    }

    // Second pass: extract token_count events
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      let obj;
      try {
        obj = JSON.parse(trimmed);
      } catch {
        continue;
      }

      if (
        obj.type !== "event_msg" ||
        !obj.payload ||
        obj.payload.type !== "token_count" ||
        !obj.payload.info // skip info === null (pre-PR#1583)
      ) {
        continue;
      }

      const last = obj.payload.info.last_token_usage;
      if (!last) continue;

      const timestamp = obj.timestamp;
      if (!timestamp) continue;

      const ts = new Date(timestamp);
      if (Number.isNaN(ts.getTime())) continue;
      if (since != null && ts < since) continue;

      const cached = last.cached_input_tokens || 0;
      const inputTokens = Math.max(0, (last.input_tokens || 0) - cached);
      const outputTokens =
        (last.output_tokens || 0) + (last.reasoning_output_tokens || 0);

      try {
        records.push(
          makeTurn({
            cli: "codex",
            session_id: sessionId,
            timestamp: ts,
            model: sessionModel,
            cwd: sessionCwd,
            input_tokens: inputTokens,
            output_tokens: outputTokens,
            cache_read_tokens: cached,
            cache_creation_tokens: 0,
            tool_calls: 0,
          })
        );
      } catch {
        continue; // schema-drift: invalid record shape
      }
    }
  }

  return records;
}

module.exports = { ingestCodexDir };
