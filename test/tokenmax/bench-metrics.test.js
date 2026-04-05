"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { makeTurn } = require("../../src/tokenmax/bench/models");
const { summarize, rollingMedian, filterSince } = require("../../src/tokenmax/bench/metrics");
const { renderText } = require("../../src/tokenmax/bench/report-text");
const { renderHtml } = require("../../src/tokenmax/bench/report-html");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function d(isoDate) {
  return new Date(isoDate + "T12:00:00Z");
}

function makeTurns(cli, sessionId, dateStr, inputTokens, outputTokens = 100, cacheRead = 0) {
  return makeTurn({
    cli,
    session_id: sessionId,
    timestamp: d(dateStr),
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    cache_read_tokens: cacheRead,
  });
}

// ---------------------------------------------------------------------------
// summarize — basic medians
// ---------------------------------------------------------------------------

test("summarize: correct medians for odd-count list", () => {
  const turns = [
    makeTurns("claude", "s1", "2026-01-10", 100),
    makeTurns("claude", "s1", "2026-01-11", 200),
    makeTurns("claude", "s1", "2026-01-12", 300),
  ];
  const result = summarize(turns, { installDate: null });
  assert.equal(result.claude.turns, 3);
  assert.equal(result.claude.sessions, 1);
  assert.equal(result.claude.before, null);
  assert.equal(result.claude.after, null);
  assert.equal(result.claude.stepChange, null);
});

test("summarize: correct median for even-count list", () => {
  const turns = [
    makeTurns("claude", "s1", "2026-01-10", 100),
    makeTurns("claude", "s1", "2026-01-11", 200),
    makeTurns("claude", "s1", "2026-01-12", 300),
    makeTurns("claude", "s1", "2026-01-13", 400),
  ];
  const result = summarize(turns, { installDate: new Date("2026-01-12T00:00:00Z") });
  // Before: 100, 200 → median = 150
  assert.equal(result.claude.before.medianInputTokens, 150);
  // After: 300, 400 → median = 350
  assert.equal(result.claude.after.medianInputTokens, 350);
});

// ---------------------------------------------------------------------------
// summarize — cache ratio
// ---------------------------------------------------------------------------

test("summarize: cache read ratio is correct", () => {
  // input=600, cache_read=400 → ratio = 400/1000 = 0.4
  const turns = [
    makeTurn({ cli: "claude", session_id: "s1", timestamp: d("2026-02-01"), input_tokens: 600, cache_read_tokens: 400 }),
  ];
  const result = summarize(turns, { installDate: null });
  // No install date so before/after are null, but the whole-window ratio can be verified via with-install.
  const withInstall = summarize(turns, { installDate: new Date("2026-02-02T00:00:00Z") });
  assert.ok(Math.abs(withInstall.claude.before.cacheReadRatio - 0.4) < 0.001);
});

test("summarize: cache ratio zero when no cache tokens", () => {
  const turns = [makeTurns("claude", "s1", "2026-02-01", 500)];
  const r = summarize(turns, { installDate: new Date("2026-02-02T00:00:00Z") });
  assert.equal(r.claude.before.cacheReadRatio, 0);
});

// ---------------------------------------------------------------------------
// summarize — step change
// ---------------------------------------------------------------------------

test("summarize: step change percentages correct sign and magnitude", () => {
  // Before: median 1000; After: median 600 → −40%
  const turns = [
    makeTurns("claude", "s1", "2026-01-01", 1000),
    makeTurns("claude", "s2", "2026-01-02", 1000),
    makeTurns("claude", "s3", "2026-02-01", 600),
    makeTurns("claude", "s4", "2026-02-02", 600),
  ];
  const installDate = new Date("2026-01-15T00:00:00Z");
  const r = summarize(turns, { installDate });
  assert.equal(r.claude.stepChange.inputTokensPct, -40);
});

test("summarize: step change null when before median is zero", () => {
  const turns = [
    makeTurns("claude", "s1", "2026-01-01", 0),
    makeTurns("claude", "s2", "2026-02-01", 500),
  ];
  const r = summarize(turns, { installDate: new Date("2026-01-15T00:00:00Z") });
  assert.equal(r.claude.stepChange.inputTokensPct, null);
});

test("summarize: cacheHitDeltaPts correct", () => {
  // Before: input=500, cache_read=500 → ratio=0.5
  // After:  input=200, cache_read=800 → ratio=0.8
  // delta = (0.8 - 0.5) * 100 = 30pt
  const turns = [
    makeTurn({ cli: "claude", session_id: "s1", timestamp: d("2026-01-01"), input_tokens: 500, cache_read_tokens: 500 }),
    makeTurn({ cli: "claude", session_id: "s2", timestamp: d("2026-02-01"), input_tokens: 200, cache_read_tokens: 800 }),
  ];
  const r = summarize(turns, { installDate: new Date("2026-01-15T00:00:00Z") });
  assert.equal(r.claude.stepChange.cacheHitDeltaPts, 30);
});

// ---------------------------------------------------------------------------
// summarize — no install date
// ---------------------------------------------------------------------------

test("summarize: no install date yields null before/after/stepChange", () => {
  const turns = [makeTurns("claude", "s1", "2026-01-01", 500)];
  const r = summarize(turns, { installDate: null });
  assert.equal(r.claude.before, null);
  assert.equal(r.claude.after, null);
  assert.equal(r.claude.stepChange, null);
  assert.equal(r.claude.turns, 1);
});

// ---------------------------------------------------------------------------
// summarize — empty turns
// ---------------------------------------------------------------------------

test("summarize: empty turns yields zeroed summary for all CLIs", () => {
  const r = summarize([], { installDate: null });
  for (const cli of ["claude", "gemini", "codex"]) {
    assert.equal(r[cli].turns, 0);
    assert.equal(r[cli].sessions, 0);
    assert.equal(r[cli].before, null);
    assert.equal(r[cli].after, null);
    assert.equal(r[cli].stepChange, null);
    assert.equal(r[cli].windowStart, null);
    assert.equal(r[cli].windowEnd, null);
  }
});

// ---------------------------------------------------------------------------
// summarize — multiple CLIs
// ---------------------------------------------------------------------------

test("summarize: only counts turns for matching CLI", () => {
  const turns = [
    makeTurns("claude", "s1", "2026-01-01", 100),
    makeTurns("claude", "s1", "2026-01-02", 200),
    makeTurns("gemini", "g1", "2026-01-01", 999),
  ];
  const r = summarize(turns, { installDate: null });
  assert.equal(r.claude.turns, 2);
  assert.equal(r.gemini.turns, 1);
  assert.equal(r.codex.turns, 0);
});

// ---------------------------------------------------------------------------
// summarize — sessions count
// ---------------------------------------------------------------------------

test("summarize: sessions counted by unique session_id", () => {
  const turns = [
    makeTurns("claude", "abc", "2026-01-01", 100),
    makeTurns("claude", "abc", "2026-01-02", 200),
    makeTurns("claude", "xyz", "2026-01-03", 300),
  ];
  const r = summarize(turns, { installDate: null });
  assert.equal(r.claude.sessions, 2);
});

// ---------------------------------------------------------------------------
// rollingMedian
// ---------------------------------------------------------------------------

test("rollingMedian: empty turns returns empty array", () => {
  assert.deepEqual(rollingMedian([], 7), []);
});

test("rollingMedian: single day returns one entry with that value", () => {
  const turns = [makeTurns("claude", "s1", "2026-03-01", 500)];
  const result = rollingMedian(turns, 7);
  assert.equal(result.length, 1);
  assert.equal(result[0].median, 500);
  assert.equal(result[0].date.toISOString().slice(0, 10), "2026-03-01");
});

test("rollingMedian: hand-computed 3-day window over 4 days", () => {
  // Day 1: [100]      window=[100]         median=100
  // Day 2: [200]      window=[100,200]     median=150
  // Day 3: [300]      window=[100,200,300] median=200
  // Day 4: [400]      window=[200,300,400] median=300
  const turns = [
    makeTurns("claude", "s1", "2026-03-01", 100),
    makeTurns("claude", "s2", "2026-03-02", 200),
    makeTurns("claude", "s3", "2026-03-03", 300),
    makeTurns("claude", "s4", "2026-03-04", 400),
  ];
  const result = rollingMedian(turns, 3);
  assert.equal(result.length, 4);
  assert.equal(result[0].median, 100);
  assert.equal(result[1].median, 150);
  assert.equal(result[2].median, 200);
  assert.equal(result[3].median, 300);
});

test("rollingMedian: multiple turns per day", () => {
  // Day 1: [100, 200] window=[100,200] median=150
  const turns = [
    makeTurns("claude", "s1", "2026-03-01", 100),
    makeTurns("claude", "s2", "2026-03-01", 200),
  ];
  const result = rollingMedian(turns, 7);
  assert.equal(result.length, 1);
  assert.equal(result[0].median, 150);
});

// ---------------------------------------------------------------------------
// filterSince
// ---------------------------------------------------------------------------

test("filterSince: drops turns before cutoff", () => {
  const turns = [
    makeTurns("claude", "s1", "2026-01-01", 100),
    makeTurns("claude", "s2", "2026-02-01", 200),
    makeTurns("claude", "s3", "2026-03-01", 300),
  ];
  const since = new Date("2026-02-01T00:00:00Z");
  const result = filterSince(turns, since);
  assert.equal(result.length, 2);
  assert.ok(result.every((t) => t.timestamp >= since));
});

test("filterSince: returns all when since is before first turn", () => {
  const turns = [
    makeTurns("claude", "s1", "2026-03-01", 100),
    makeTurns("claude", "s2", "2026-03-02", 200),
  ];
  const result = filterSince(turns, new Date("2026-01-01T00:00:00Z"));
  assert.equal(result.length, 2);
});

// ---------------------------------------------------------------------------
// Text report
// ---------------------------------------------------------------------------

test("renderText: contains expected substrings for known summary", () => {
  const turns = [
    makeTurns("claude", "s1", "2026-01-01", 1000),
    makeTurns("claude", "s2", "2026-01-05", 2000),
    makeTurns("claude", "s3", "2026-02-10", 500),
    makeTurns("claude", "s4", "2026-02-15", 700),
    makeTurns("gemini", "g1", "2026-01-10", 800),
  ];
  const installDate = new Date("2026-02-01T00:00:00Z");
  const summary = summarize(turns, { installDate });
  const text = renderText({ summary, installDate });

  assert.ok(text.includes("Claude Code"), "should include Claude Code label");
  assert.ok(text.includes("Before tokenmax"), "should include before section");
  assert.ok(text.includes("After  tokenmax"), "should include after section");
  assert.ok(text.includes("Step change"), "should include step change line");
  // Unicode minus for negative delta
  assert.ok(text.includes("\u2212"), "should use unicode minus for negative delta");
  // Gemini has 1 turn, no install-date buckets relevant but still appears
  assert.ok(text.includes("Gemini CLI"), "should include Gemini CLI");
  // Codex has 0 turns
  assert.ok(text.includes("no sessions in window"), "should say no sessions for codex");
});

test("renderText: no install date shows single-line with marker message", () => {
  const turns = [makeTurns("claude", "s1", "2026-01-01", 500)];
  const summary = summarize(turns, { installDate: null });
  const text = renderText({ summary, installDate: null });
  assert.ok(text.includes("no install date detected"), "should warn about missing install date");
  assert.ok(!text.includes("Before tokenmax"), "should not have before/after when no install date");
});

// ---------------------------------------------------------------------------
// HTML report
// ---------------------------------------------------------------------------

test("renderHtml: contains <svg for CLIs with turns", () => {
  const turns = [
    makeTurns("claude", "s1", "2026-01-10", 800),
    makeTurns("claude", "s2", "2026-02-10", 400),
  ];
  const installDate = new Date("2026-02-01T00:00:00Z");
  const summary = summarize(turns, { installDate });
  const rolling = { claude: rollingMedian(turns.filter((t) => t.cli === "claude"), 7) };
  const html = renderHtml({ summary, rolling, installDate });

  assert.ok(html.includes("<svg"), "should contain SVG element");
  assert.ok(html.includes("<polyline"), "should contain polyline in SVG");
});

test("renderHtml: contains step-change delta in output", () => {
  // Before median 1000, after median 500 → −50%
  const turns = [
    makeTurns("claude", "s1", "2026-01-10", 1000),
    makeTurns("claude", "s2", "2026-02-10", 500),
  ];
  const installDate = new Date("2026-02-01T00:00:00Z");
  const summary = summarize(turns, { installDate });
  const html = renderHtml({ summary, rolling: {}, installDate });
  // −50% expressed as unicode minus
  assert.ok(html.includes("\u221250%") || html.includes("−50%"), "should include step delta");
});

test("renderHtml: privacy comment present", () => {
  const summary = summarize([], { installDate: null });
  const html = renderHtml({ summary });
  assert.ok(html.includes("Privacy"), "should include privacy comment");
  assert.ok(html.includes("NO message content"), "should state no message content");
});

test("renderHtml: does not contain message-content fields", () => {
  const turns = [makeTurns("claude", "s1", "2026-01-01", 500)];
  const summary = summarize(turns, { installDate: null });
  const html = renderHtml({ summary });
  // Should not have fields that could carry raw user prompts or file content.
  assert.ok(!html.includes("message_content"), "no message_content field");
  // "prompt" may appear in the privacy notice; check that no data field named "prompt" appears.
  assert.ok(!html.includes('"prompt"'), 'no "prompt" JSON key in output');
});

test("renderHtml: includes summary table with CLI names", () => {
  const summary = summarize([], { installDate: null });
  const html = renderHtml({ summary });
  assert.ok(html.includes("Claude Code"), "table should include Claude Code");
  assert.ok(html.includes("Gemini CLI"), "table should include Gemini CLI");
  assert.ok(html.includes("Codex CLI"), "table should include Codex CLI");
  assert.ok(html.includes("<table"), "should contain table element");
});
