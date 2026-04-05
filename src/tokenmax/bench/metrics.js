/**
 * metrics.js — pure aggregation functions over TurnRecord[].
 * No side effects, no I/O.
 */

"use strict";

const CLIS = ["claude", "gemini", "codex"];

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Return the median of a sorted numeric array (mutates a copy). */
function median(values) {
  if (values.length === 0) return 0;
  const sorted = values.slice().sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1
    ? sorted[mid]
    : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}

/**
 * cacheReadRatio — cache_read_tokens / (input_tokens + cache_read_tokens).
 * Returns 0 when denominator is zero.
 */
function cacheReadRatio(turns) {
  let cacheRead = 0;
  let input = 0;
  for (const t of turns) {
    cacheRead += t.cache_read_tokens;
    input += t.input_tokens;
  }
  const denom = input + cacheRead;
  return denom === 0 ? 0 : cacheRead / denom;
}

/** Build a BucketStats from a set of turns and a day span. */
function bucketStats(turns, days) {
  return {
    days,
    turns: turns.length,
    medianInputTokens: median(turns.map((t) => t.input_tokens)),
    medianOutputTokens: median(turns.map((t) => t.output_tokens)),
    cacheReadRatio: cacheReadRatio(turns),
  };
}

/** Count unique session_ids. */
function countSessions(turns) {
  return new Set(turns.map((t) => t.session_id)).size;
}

/** Difference in whole days between two Dates (ceil). */
function daySpan(start, end) {
  const ms = end.getTime() - start.getTime();
  return Math.max(1, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

// ---------------------------------------------------------------------------
// filterSince
// ---------------------------------------------------------------------------

/**
 * Drop turns with timestamp < since.
 * @param {object[]} turns - TurnRecord[]
 * @param {Date} since
 * @returns {object[]}
 */
function filterSince(turns, since) {
  const t = since instanceof Date ? since.getTime() : new Date(since).getTime();
  return turns.filter((turn) => turn.timestamp.getTime() >= t);
}

// ---------------------------------------------------------------------------
// rollingMedian
// ---------------------------------------------------------------------------

/**
 * 7-day rolling median of input_tokens per day.
 * Returns one entry per day from the first day to the last day in turns.
 *
 * @param {object[]} turns - TurnRecord[] (single CLI)
 * @param {number} windowDays - rolling window size (default 7)
 * @returns {Array<{date: Date, median: number}>}
 */
function rollingMedian(turns, windowDays = 7) {
  if (turns.length === 0) return [];

  // Group input_tokens by day (ISO date string as key).
  const byDay = new Map();
  for (const t of turns) {
    const key = t.timestamp.toISOString().slice(0, 10);
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key).push(t.input_tokens);
  }

  // Build a sorted list of all days in range.
  const allKeys = Array.from(byDay.keys()).sort();
  const firstDate = new Date(allKeys[0] + "T00:00:00Z");
  const lastDate = new Date(allKeys[allKeys.length - 1] + "T00:00:00Z");
  const days = [];
  for (let d = new Date(firstDate); d <= lastDate; d = new Date(d.getTime() + 86400000)) {
    days.push(d.toISOString().slice(0, 10));
  }

  const result = [];
  for (let i = 0; i < days.length; i++) {
    // Gather tokens from days[max(0,i-windowDays+1) .. i].
    const startIdx = Math.max(0, i - windowDays + 1);
    const windowTokens = [];
    for (let j = startIdx; j <= i; j++) {
      const tokens = byDay.get(days[j]);
      if (tokens) windowTokens.push(...tokens);
    }
    result.push({
      date: new Date(days[i] + "T00:00:00Z"),
      median: median(windowTokens),
    });
  }
  return result;
}

// ---------------------------------------------------------------------------
// summarize
// ---------------------------------------------------------------------------

/**
 * @param {object[]} turns - TurnRecord[]
 * @param {{ installDate: Date|null }} options
 * @returns {object} PerCliSummary keyed by cli name
 */
function summarize(turns, { installDate = null } = {}) {
  const result = {};

  for (const cli of CLIS) {
    const cliTurns = turns.filter((t) => t.cli === cli);

    if (cliTurns.length === 0) {
      result[cli] = {
        windowStart: null,
        windowEnd: null,
        sessions: 0,
        turns: 0,
        before: null,
        after: null,
        stepChange: null,
      };
      continue;
    }

    // Sort by timestamp to find window bounds.
    const sorted = cliTurns.slice().sort((a, b) => a.timestamp - b.timestamp);
    const windowStart = sorted[0].timestamp;
    const windowEnd = sorted[sorted.length - 1].timestamp;

    const sessions = countSessions(cliTurns);

    if (installDate == null) {
      result[cli] = {
        windowStart,
        windowEnd,
        sessions,
        turns: cliTurns.length,
        before: null,
        after: null,
        stepChange: null,
      };
      continue;
    }

    const installMs = installDate instanceof Date ? installDate.getTime() : new Date(installDate).getTime();

    const beforeTurns = sorted.filter((t) => t.timestamp.getTime() < installMs);
    const afterTurns = sorted.filter((t) => t.timestamp.getTime() >= installMs);

    const beforeBucket =
      beforeTurns.length === 0
        ? null
        : bucketStats(beforeTurns, daySpan(windowStart, installDate));

    const afterBucket =
      afterTurns.length === 0
        ? null
        : bucketStats(afterTurns, daySpan(installDate, windowEnd));

    let stepChange = null;
    if (beforeBucket !== null && afterBucket !== null) {
      const inputPct =
        beforeBucket.medianInputTokens === 0
          ? null
          : Math.round(
              ((afterBucket.medianInputTokens - beforeBucket.medianInputTokens) /
                beforeBucket.medianInputTokens) *
                100
            );
      const cacheHitDelta = Math.round(
        (afterBucket.cacheReadRatio - beforeBucket.cacheReadRatio) * 100
      );
      stepChange = {
        inputTokensPct: inputPct,
        cacheHitDeltaPts: cacheHitDelta,
      };
    }

    result[cli] = {
      windowStart,
      windowEnd,
      sessions,
      turns: cliTurns.length,
      before: beforeBucket,
      after: afterBucket,
      stepChange,
    };
  }

  return result;
}

module.exports = { summarize, rollingMedian, filterSince };
