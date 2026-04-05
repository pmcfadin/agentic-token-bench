"use strict";
/**
 * ingest-gemini.js
 *
 * Reads Gemini CLI session transcripts from:
 *   <geminiHome>/tmp/<project-hash>/chats/session-*.json
 *
 * Each session is a single JSON file. Only messages of type "gemini" that
 * carry a `tokens` field produce TurnRecords. Messages without tokens are
 * silently skipped (schema-drift rule).
 *
 * Token mapping:
 *   input_tokens          = tokens.input - tokens.cached  (floor 0)
 *   output_tokens         = tokens.output + (tokens.thoughts || 0)
 *   cache_read_tokens     = tokens.cached
 *   cache_creation_tokens = 0  (not reported by Gemini CLI)
 *   tool_calls            = 0  (not reliably present)
 *
 * cwd is always null for Gemini turns (projectHash is not a filesystem path).
 * Therefore, if `cwd` filter is specified, all Gemini turns are skipped.
 */

const fs = require("node:fs");
const path = require("node:path");
const { makeTurn } = require("./models");

/**
 * @param {string} geminiHome  Path to ~/.gemini (or equivalent)
 * @param {{ since?: Date, cwd?: string }} [opts]
 * @returns {import('./models').TurnRecord[]}
 */
function ingestGeminiDir(geminiHome, { since, cwd } = {}) {
  // Gemini turns have cwd=null. If caller specifies a cwd filter, no Gemini
  // turns can match, so return immediately.
  if (cwd != null) return [];

  const tmpDir = path.join(geminiHome, "tmp");
  if (!fs.existsSync(tmpDir)) return [];

  const records = [];

  for (const hash of fs.readdirSync(tmpDir)) {
    const chatsDir = path.join(tmpDir, hash, "chats");
    if (!fs.existsSync(chatsDir)) continue;
    if (!fs.statSync(chatsDir).isDirectory()) continue;

    for (const entry of fs.readdirSync(chatsDir)) {
      if (!entry.endsWith(".json")) continue;

      const filePath = path.join(chatsDir, entry);

      let session;
      try {
        session = JSON.parse(fs.readFileSync(filePath, "utf8"));
      } catch {
        continue; // schema-drift: unparseable file
      }

      if (!session || !Array.isArray(session.messages)) continue;

      const sessionId = session.sessionId || path.basename(entry, ".json");

      for (const msg of session.messages) {
        // Only gemini messages with a tokens field produce records
        if (!msg || msg.type !== "gemini" || !msg.tokens) continue;

        const tok = msg.tokens;
        const timestamp = msg.timestamp;
        if (!timestamp) continue;

        const ts = new Date(timestamp);
        if (Number.isNaN(ts.getTime())) continue;
        if (since != null && ts < since) continue;

        const cached = tok.cached || 0;
        const rawInput = tok.input || 0;
        const inputTokens = Math.max(0, rawInput - cached);
        const outputTokens = (tok.output || 0) + (tok.thoughts || 0);

        try {
          records.push(
            makeTurn({
              cli: "gemini",
              session_id: sessionId,
              timestamp: ts,
              model: "gemini",
              cwd: null,
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
  }

  return records;
}

module.exports = { ingestGeminiDir };
