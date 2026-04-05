const path = require("path");
const fs = require("fs");
const { ingestClaudeDir } = require("./ingest-claude");
const { ingestGeminiDir } = require("./ingest-gemini");
const { ingestCodexDir } = require("./ingest-codex");
const { detectInstallDate } = require("./install-detect");
const { summarize, rollingMedian } = require("./metrics");
const { renderText } = require("./report-text");
const { renderHtml } = require("./report-html");
const { VALID_CLIS } = require("./models");

/**
 * Parse a --since value: "30d", "7d", or absolute ISO date "2026-02-01".
 * Returns a Date or null.
 */
function parseSince(value, now = new Date()) {
  if (value == null || value === "") return null;
  const m = /^(\d+)d$/.exec(value);
  if (m) {
    const days = Number(m[1]);
    return new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
  }
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    throw new Error(`Invalid --since value: ${value}`);
  }
  return d;
}

/**
 * Parse --cli value: "claude,codex" → ["claude","codex"]. Returns VALID_CLIS if blank.
 */
function parseCliFilter(value) {
  if (!value) return VALID_CLIS.slice();
  const parts = value
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
  for (const p of parts) {
    if (!VALID_CLIS.includes(p)) {
      throw new Error(`Invalid --cli value: ${p}. Must be one of: ${VALID_CLIS.join(", ")}`);
    }
  }
  return parts;
}

function runBench({ homeDir, clis, since, cwd, now = new Date() }) {
  const ingesters = {
    claude: [".claude", ingestClaudeDir],
    gemini: [".gemini", ingestGeminiDir],
    codex: [".codex", ingestCodexDir],
  };
  const turns = [];
  for (const cli of clis) {
    const [subdir, ingest] = ingesters[cli];
    turns.push(...ingest(path.join(homeDir, subdir), { since, cwd }));
  }

  const { date: installDate, source: installSource } = detectInstallDate(homeDir);
  const summary = summarize(turns, { installDate });

  const rolling = {};
  for (const cli of clis) {
    const cliTurns = turns.filter((t) => t.cli === cli);
    rolling[cli] = rollingMedian(cliTurns, 7);
  }

  return {
    turns,
    summary,
    rolling,
    installDate,
    installSource,
    windowSince: since,
    now,
  };
}

/**
 * Reformat the bench result into the stable JSON schema documented in the README.
 */
function toJsonOutput(result) {
  const summaryOut = {};
  for (const cli of VALID_CLIS) {
    const s = result.summary[cli];
    if (!s) continue;
    summaryOut[cli] = {
      sessions: s.sessions,
      turns: s.turns,
      window_start: s.windowStart ? s.windowStart.toISOString() : null,
      window_end: s.windowEnd ? s.windowEnd.toISOString() : null,
      before: s.before
        ? {
            days: s.before.days,
            turns: s.before.turns,
            median_input_tokens: s.before.medianInputTokens,
            median_output_tokens: s.before.medianOutputTokens,
            cache_read_ratio: s.before.cacheReadRatio,
          }
        : null,
      after: s.after
        ? {
            days: s.after.days,
            turns: s.after.turns,
            median_input_tokens: s.after.medianInputTokens,
            median_output_tokens: s.after.medianOutputTokens,
            cache_read_ratio: s.after.cacheReadRatio,
          }
        : null,
      step_change: s.stepChange
        ? {
            input_tokens_pct: s.stepChange.inputTokensPct,
            cache_hit_delta_pts: s.stepChange.cacheHitDeltaPts,
          }
        : null,
    };
  }
  return {
    command: "bench",
    status: "ok",
    install_date: result.installDate ? result.installDate.toISOString() : null,
    install_source: result.installSource,
    window_since: result.windowSince ? result.windowSince.toISOString() : null,
    agents: summaryOut,
  };
}

function bench({ homeDir, cliFilter, since, cwd, htmlPath, json, writeFile = fs.writeFileSync }) {
  const clis = parseCliFilter(cliFilter);
  const sinceDate = parseSince(since);
  const result = runBench({ homeDir, clis, since: sinceDate, cwd });

  if (htmlPath) {
    const html = renderHtml({
      summary: result.summary,
      rolling: result.rolling,
      installDate: result.installDate,
      installSource: result.installSource,
      windowSince: result.windowSince,
    });
    writeFile(htmlPath, html, "utf8");
  }

  if (json) {
    return { ok: true, action: "bench", target: "all", json: toJsonOutput(result) };
  }

  const text = renderText({
    summary: result.summary,
    installDate: result.installDate,
    installSource: result.installSource,
    windowSince: result.windowSince,
  });
  return { ok: true, action: "bench", target: "all", text };
}

module.exports = { bench, runBench, parseSince, parseCliFilter, toJsonOutput };
