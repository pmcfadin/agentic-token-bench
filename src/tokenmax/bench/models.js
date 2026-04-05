/**
 * TurnRecord — normalized per-turn token usage across Claude Code, Gemini CLI,
 * and Codex CLI. This is the single shared contract consumed by metrics and
 * report renderers. Ingesters produce TurnRecord[]; everything downstream is
 * pure over that array.
 *
 * Shape:
 *   cli:                   "claude" | "gemini" | "codex"
 *   session_id:            string
 *   timestamp:             Date (UTC)
 *   model:                 string
 *   cwd:                   string | null    (project root; may be null if unknown)
 *   input_tokens:          number >= 0      (non-cached input)
 *   output_tokens:         number >= 0
 *   cache_read_tokens:     number >= 0      (cache hits; 0 if CLI doesn't report)
 *   cache_creation_tokens: number >= 0      (cache writes; 0 if not reported)
 *   tool_calls:            number >= 0      (tool_use blocks in this turn)
 *
 * Privacy contract: TurnRecord carries NO message content, no filenames beyond
 * the cwd root, no prompts. Ingesters must drop all content fields.
 */

const { AGENT_IDS } = require("../constants");
const VALID_CLIS = AGENT_IDS;

function makeTurn({
  cli,
  session_id,
  timestamp,
  model = "unknown",
  cwd = null,
  input_tokens = 0,
  output_tokens = 0,
  cache_read_tokens = 0,
  cache_creation_tokens = 0,
  tool_calls = 0,
}) {
  if (!VALID_CLIS.includes(cli)) {
    throw new Error(`Invalid cli: ${cli}`);
  }
  if (!session_id) {
    throw new Error("session_id required");
  }
  const ts = timestamp instanceof Date ? timestamp : new Date(timestamp);
  if (Number.isNaN(ts.getTime())) {
    throw new Error(`Invalid timestamp: ${timestamp}`);
  }
  return {
    cli,
    session_id: String(session_id),
    timestamp: ts,
    model: String(model),
    cwd: cwd == null ? null : String(cwd),
    input_tokens: toNonNeg(input_tokens),
    output_tokens: toNonNeg(output_tokens),
    cache_read_tokens: toNonNeg(cache_read_tokens),
    cache_creation_tokens: toNonNeg(cache_creation_tokens),
    tool_calls: toNonNeg(tool_calls),
  };
}

function toNonNeg(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.trunc(n);
}

module.exports = {
  VALID_CLIS,
  makeTurn,
};
