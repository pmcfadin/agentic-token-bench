"use strict";
/**
 * ingest-claude.js
 *
 * Reads Claude Code session transcripts from:
 *   <claudeHome>/projects/<cwd-slug>/<sessionId>.jsonl
 *
 * Each JSONL line with message.role === "assistant" and message.usage present
 * produces one TurnRecord. Lines that cannot be parsed or lack usage are
 * silently skipped (schema-drift rule).
 *
 * The cwd-slug encoding: the project path with "/" replaced by "-" and a
 * leading "-" prepended (so /Users/me/proj → -Users-me-proj).
 * We reverse this to recover the cwd: strip leading "-", replace "-" with "/".
 * This is ambiguous when original paths contain "-", but it is the best we can
 * do without additional metadata.
 */

const fs = require("node:fs");
const path = require("node:path");
const { makeTurn } = require("./models");

/**
 * Decode a Claude projects directory slug back to an approximate cwd.
 * The slug is the cwd with "/" replaced by "-" and a leading "-" prepended.
 * e.g. "-Users-me-proj" → "/Users/me/proj"
 *
 * Note: this is a lossy reverse; hyphens in original path components cannot
 * be distinguished from path separators. We return a best-effort string.
 */
function slugToCwd(slug) {
  // Strip leading "-", then replace "-" with "/"
  return "/" + slug.replace(/^-/, "").replace(/-/g, "/");
}

/**
 * @param {string} claudeHome  Path to ~/.claude (or equivalent)
 * @param {{ since?: Date, cwd?: string }} [opts]
 * @returns {import('./models').TurnRecord[]}
 */
function ingestClaudeDir(claudeHome, { since, cwd } = {}) {
  const projectsDir = path.join(claudeHome, "projects");
  if (!fs.existsSync(projectsDir)) return [];

  const records = [];

  for (const slug of fs.readdirSync(projectsDir)) {
    const slugPath = path.join(projectsDir, slug);
    if (!fs.statSync(slugPath).isDirectory()) continue;

    const turnCwd = slugToCwd(slug);

    // Apply cwd filter: if requested cwd is specified, the turn's cwd must
    // start with it.
    if (cwd != null && !turnCwd.startsWith(cwd)) continue;

    for (const entry of fs.readdirSync(slugPath)) {
      if (!entry.endsWith(".jsonl")) continue;

      const sessionId = path.basename(entry, ".jsonl");
      const filePath = path.join(slugPath, entry);
      const lines = fs.readFileSync(filePath, "utf8").split("\n");

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        let obj;
        try {
          obj = JSON.parse(trimmed);
        } catch {
          continue; // schema-drift: unparseable line
        }

        // Only process assistant messages with usage
        if (
          !obj.message ||
          obj.message.role !== "assistant" ||
          !obj.message.usage
        ) {
          continue;
        }

        const usage = obj.message.usage;
        const timestamp = obj.timestamp;
        if (!timestamp) continue;

        // Apply since filter
        const ts = new Date(timestamp);
        if (Number.isNaN(ts.getTime())) continue;
        if (since != null && ts < since) continue;

        // Count tool_use items in content array
        const content = obj.message.content;
        const toolCalls = Array.isArray(content)
          ? content.filter((c) => c && c.type === "tool_use").length
          : 0;

        try {
          records.push(
            makeTurn({
              cli: "claude",
              session_id: sessionId,
              timestamp: ts,
              model: obj.message.model || "unknown",
              cwd: turnCwd,
              input_tokens: usage.input_tokens || 0,
              output_tokens: usage.output_tokens || 0,
              cache_read_tokens: usage.cache_read_input_tokens || 0,
              cache_creation_tokens: usage.cache_creation_input_tokens || 0,
              tool_calls: toolCalls,
            })
          );
        } catch {
          continue; // schema-drift: invalid record shape
        }
      }
    }
  }

  return records;
}

module.exports = { ingestClaudeDir };
