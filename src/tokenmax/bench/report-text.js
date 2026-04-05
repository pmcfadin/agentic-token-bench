/**
 * report-text.js — plain-text report renderer for tokenmax bench output.
 * Consumes the PerCliSummary produced by metrics.summarize().
 */

"use strict";

const CLI_LABELS = {
  claude: "Claude Code",
  gemini: "Gemini CLI",
  codex: "Codex CLI",
};

// Unicode minus (U+2212) and en-dash (U+2013).
const MINUS = "\u2212";
const ENDASH = "\u2013";

/** Format a Date as YYYY-MM-DD (UTC). */
function fmtDate(d) {
  return d instanceof Date ? d.toISOString().slice(0, 10) : String(d);
}

/** Format a number with thousands separators. */
function fmtNum(n) {
  return Number(n).toLocaleString("en-US");
}

/**
 * Render a delta percentage with the correct sign glyph.
 * Negative → unicode minus; positive → plus.
 */
function fmtPct(n) {
  if (n === null || n === undefined) return null;
  const abs = Math.abs(n);
  const sign = n < 0 ? MINUS : "+";
  return `${sign}${abs}%`;
}

/**
 * Render a cache hit delta in percentage points.
 */
function fmtPts(n) {
  if (n === null || n === undefined) return null;
  const abs = Math.abs(n);
  const sign = n < 0 ? MINUS : "+";
  return `${sign}${abs}pt`;
}

/**
 * renderText({ summary, installDate, installSource, windowSince }) → string
 *
 * @param {object} summary - PerCliSummary from metrics.summarize()
 * @param {Date|null} installDate
 * @param {string|null} installSource
 * @param {Date|null} windowSince
 * @returns {string}
 */
function renderText({ summary, installDate = null, installSource = null, windowSince = null }) {
  const lines = [];

  const cliOrder = ["claude", "gemini", "codex"];

  for (const cli of cliOrder) {
    const s = summary[cli];
    const label = CLI_LABELS[cli] || cli;

    if (!s || s.turns === 0) {
      lines.push(`${label.padEnd(12)}  no sessions in window`);
      lines.push("");
      continue;
    }

    // Header line: label  date range  sessions  turns
    const dateRange =
      s.windowStart && s.windowEnd
        ? `${fmtDate(s.windowStart)} ${ENDASH} ${fmtDate(s.windowEnd)}`
        : "";

    const sessionsStr = `${fmtNum(s.sessions)} session${s.sessions !== 1 ? "s" : ""}`;
    const turnsStr = `${fmtNum(s.turns)} turns`;

    lines.push(`${label.padEnd(12)}  ${dateRange}   ${sessionsStr}, ${turnsStr}`);

    if (installDate === null) {
      lines.push(
        `  (no install date detected \u2014 run 'tokenmax install' to set marker)`
      );
      lines.push("");
      continue;
    }

    // Before bucket.
    if (s.before) {
      const b = s.before;
      let line = `  Before tokenmax (${b.days} day${b.days !== 1 ? "s" : ""}):  median ${fmtNum(b.medianInputTokens)} input tok/turn`;
      const denom = b.cacheReadRatio > 0 || (b.cacheReadRatio === 0 && _hasCacheData(summary[cli], "before"));
      if (b.cacheReadRatio > 0) {
        line += ` \u00b7 cache-read ${Math.round(b.cacheReadRatio * 100)}%`;
      }
      lines.push(line);
    }

    // After bucket.
    if (s.after) {
      const a = s.after;
      let line = `  After  tokenmax (${a.days} day${a.days !== 1 ? "s" : ""}):  median ${fmtNum(a.medianInputTokens)} input tok/turn`;
      if (a.cacheReadRatio > 0) {
        line += ` \u00b7 cache-read ${Math.round(a.cacheReadRatio * 100)}%`;
      }
      lines.push(line);
    }

    // Step change.
    if (s.stepChange) {
      const sc = s.stepChange;
      const parts = [];
      if (sc.inputTokensPct !== null) {
        parts.push(`${fmtPct(sc.inputTokensPct)} input tokens per turn`);
      }
      if (sc.cacheHitDeltaPts !== null && sc.cacheHitDeltaPts !== 0) {
        parts.push(`${fmtPts(sc.cacheHitDeltaPts)} cache hit`);
      }
      if (parts.length > 0) {
        lines.push(`  Step change: ${parts.join(", ")}`);
      }
    }

    lines.push("");
  }

  // Trim trailing blank line.
  while (lines.length > 0 && lines[lines.length - 1] === "") {
    lines.pop();
  }

  return lines.join("\n");
}

/**
 * Internal helper: check if a bucket has any non-zero cache read tokens.
 * We can't tell from the ratio alone when ratio === 0.
 * Since we only have the summary (not raw turns) here, we rely on the ratio itself.
 * A ratio of exactly 0 with turns > 0 means denom > 0 only if input_tokens > 0 too,
 * but cache_read_tokens == 0.  We skip the label in that case — consistent with spec.
 */
function _hasCacheData(_cliSummary, _bucket) {
  // Placeholder — the ratio check in the caller is sufficient.
  return false;
}

module.exports = { renderText };
