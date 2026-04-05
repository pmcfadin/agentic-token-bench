"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { ingestClaudeDir } = require("../../src/tokenmax/bench/ingest-claude");
const { ingestGeminiDir } = require("../../src/tokenmax/bench/ingest-gemini");
const { ingestCodexDir } = require("../../src/tokenmax/bench/ingest-codex");
const { detectInstallDate } = require("../../src/tokenmax/bench/install-detect");

// Path to the hand-crafted fixture directory
const FIXTURES = path.join(__dirname, "fixtures", "bench");

// ---------------------------------------------------------------------------
// Claude ingester tests
// ---------------------------------------------------------------------------

test("claude ingester: returns 3 TurnRecords from fixture (skips line without usage)", () => {
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"));
  assert.equal(records.length, 3, "expected 3 records (4th line has no usage)");
});

test("claude ingester: all records have cli=claude", () => {
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"));
  assert.ok(records.every((r) => r.cli === "claude"));
});

test("claude ingester: first record has correct token fields", () => {
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"));
  // Sort by timestamp to get deterministic order
  records.sort((a, b) => a.timestamp - b.timestamp);
  const first = records[0];
  assert.equal(first.input_tokens, 100);
  assert.equal(first.output_tokens, 30);
  assert.equal(first.cache_read_tokens, 200);
  assert.equal(first.cache_creation_tokens, 50);
  assert.equal(first.tool_calls, 1); // 1 tool_use in content
  assert.equal(first.model, "claude-sonnet-4-6");
});

test("claude ingester: second record has correct tool_calls count", () => {
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"));
  records.sort((a, b) => a.timestamp - b.timestamp);
  const second = records[1];
  assert.equal(second.tool_calls, 2); // 2 tool_use items
});

test("claude ingester: session_id matches filename stem", () => {
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"));
  assert.ok(records.every((r) => r.session_id === "session-fixture-1"));
});

test("claude ingester: cwd is derived from slug", () => {
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"));
  // slug is -Users-me-proj → /Users/me/proj
  assert.ok(records.every((r) => r.cwd === "/Users/me/proj"));
});

test("claude ingester: since filter drops turns before cutoff", () => {
  // Cutoff just after the second turn (10:05), so only the third (10:10) should survive
  const since = new Date("2026-03-15T10:06:00.000Z");
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"), { since });
  assert.equal(records.length, 1);
  assert.equal(records[0].output_tokens, 10); // third record
});

test("claude ingester: since filter with cutoff before all turns returns all 3", () => {
  const since = new Date("2026-01-01T00:00:00.000Z");
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"), { since });
  assert.equal(records.length, 3);
});

test("claude ingester: cwd filter matches project", () => {
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"), {
    cwd: "/Users/me/proj",
  });
  assert.equal(records.length, 3);
});

test("claude ingester: cwd filter rejects non-matching path", () => {
  const records = ingestClaudeDir(path.join(FIXTURES, "claude"), {
    cwd: "/Users/other/project",
  });
  assert.equal(records.length, 0);
});

test("claude ingester: returns empty array for nonexistent home", () => {
  const records = ingestClaudeDir("/nonexistent/path/xyz");
  assert.equal(records.length, 0);
});

test("claude ingester: schema-drift — unparseable line does not throw", () => {
  const tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), "claude-test-"));
  const projDir = path.join(tmpHome, "projects", "-tmp-proj");
  fs.mkdirSync(projDir, { recursive: true });
  fs.writeFileSync(
    path.join(projDir, "sess.jsonl"),
    'NOT JSON\n{"message":{"role":"assistant","usage":{"input_tokens":5,"output_tokens":2}},"timestamp":"2026-01-01T00:00:00.000Z","sessionId":"sess"}\n'
  );
  let records;
  assert.doesNotThrow(() => {
    records = ingestClaudeDir(tmpHome);
  });
  assert.equal(records.length, 1);
  assert.equal(records[0].input_tokens, 5);
});

// ---------------------------------------------------------------------------
// Gemini ingester tests
// ---------------------------------------------------------------------------

test("gemini ingester: returns 2 TurnRecords from fixture (1 user, 1 gemini-no-tokens skipped)", () => {
  const records = ingestGeminiDir(path.join(FIXTURES, "gemini"));
  assert.equal(records.length, 2, "expected 2 records with tokens");
});

test("gemini ingester: all records have cli=gemini", () => {
  const records = ingestGeminiDir(path.join(FIXTURES, "gemini"));
  assert.ok(records.every((r) => r.cli === "gemini"));
});

test("gemini ingester: cwd is null for all records", () => {
  const records = ingestGeminiDir(path.join(FIXTURES, "gemini"));
  assert.ok(records.every((r) => r.cwd === null));
});

test("gemini ingester: first record token mapping", () => {
  const records = ingestGeminiDir(path.join(FIXTURES, "gemini"));
  records.sort((a, b) => a.timestamp - b.timestamp);
  const first = records[0];
  // input_tokens = 500 - 100 = 400
  assert.equal(first.input_tokens, 400);
  // output_tokens = 200 + 50 (thoughts) = 250
  assert.equal(first.output_tokens, 250);
  // cache_read_tokens = 100
  assert.equal(first.cache_read_tokens, 100);
  assert.equal(first.cache_creation_tokens, 0);
  assert.equal(first.tool_calls, 0);
});

test("gemini ingester: second record token mapping", () => {
  const records = ingestGeminiDir(path.join(FIXTURES, "gemini"));
  records.sort((a, b) => a.timestamp - b.timestamp);
  const second = records[1];
  // input_tokens = 600 - 200 = 400
  assert.equal(second.input_tokens, 400);
  // output_tokens = 150 + 0 (thoughts=0) = 150
  assert.equal(second.output_tokens, 150);
  assert.equal(second.cache_read_tokens, 200);
});

test("gemini ingester: session_id from sessionId field", () => {
  const records = ingestGeminiDir(path.join(FIXTURES, "gemini"));
  assert.ok(records.every((r) => r.session_id === "gemini-session-fixture-1"));
});

test("gemini ingester: cwd filter returns empty (Gemini cwd is always null)", () => {
  const records = ingestGeminiDir(path.join(FIXTURES, "gemini"), {
    cwd: "/Users/me/proj",
  });
  assert.equal(records.length, 0);
});

test("gemini ingester: since filter drops old turns", () => {
  // Cutoff between first (09:06) and second (09:15) turn
  const since = new Date("2026-03-15T09:10:00.000Z");
  const records = ingestGeminiDir(path.join(FIXTURES, "gemini"), { since });
  assert.equal(records.length, 1);
  assert.equal(records[0].input_tokens, 400); // second record: 600-200
});

test("gemini ingester: returns empty array for nonexistent home", () => {
  const records = ingestGeminiDir("/nonexistent/path/xyz");
  assert.equal(records.length, 0);
});

test("gemini ingester: schema-drift — session with no tokens-bearing messages produces 0 records", () => {
  const tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), "gemini-test-"));
  const chatsDir = path.join(tmpHome, "tmp", "hash1", "chats");
  fs.mkdirSync(chatsDir, { recursive: true });
  fs.writeFileSync(
    path.join(chatsDir, "session-x.json"),
    JSON.stringify({
      sessionId: "sess-x",
      projectHash: "hash1",
      startTime: "2026-01-01T00:00:00.000Z",
      lastUpdated: "2026-01-01T00:01:00.000Z",
      messages: [
        { id: "m1", timestamp: "2026-01-01T00:00:30.000Z", type: "user", content: "hi" },
        { id: "m2", timestamp: "2026-01-01T00:00:45.000Z", type: "gemini", content: "hello" },
      ],
    })
  );
  const records = ingestGeminiDir(tmpHome);
  assert.equal(records.length, 0);
});

// ---------------------------------------------------------------------------
// Codex ingester tests
// ---------------------------------------------------------------------------

test("codex ingester: returns 2 TurnRecords from fixture (info:null skipped)", () => {
  const records = ingestCodexDir(path.join(FIXTURES, "codex"));
  assert.equal(records.length, 2, "expected 2 records (null info skipped)");
});

test("codex ingester: all records have cli=codex", () => {
  const records = ingestCodexDir(path.join(FIXTURES, "codex"));
  assert.ok(records.every((r) => r.cli === "codex"));
});

test("codex ingester: first record token mapping", () => {
  const records = ingestCodexDir(path.join(FIXTURES, "codex"));
  records.sort((a, b) => a.timestamp - b.timestamp);
  const first = records[0];
  // input = 40000 - 5000 = 35000
  assert.equal(first.input_tokens, 35000);
  // output = 2500 + 800 = 3300
  assert.equal(first.output_tokens, 3300);
  assert.equal(first.cache_read_tokens, 5000);
  assert.equal(first.cache_creation_tokens, 0);
  assert.equal(first.tool_calls, 0);
});

test("codex ingester: model comes from session_meta", () => {
  const records = ingestCodexDir(path.join(FIXTURES, "codex"));
  assert.ok(records.every((r) => r.model === "o3"));
});

test("codex ingester: cwd comes from session_meta", () => {
  const records = ingestCodexDir(path.join(FIXTURES, "codex"));
  assert.ok(records.every((r) => r.cwd === "/Users/me/proj"));
});

test("codex ingester: session_id comes from session_meta payload.id", () => {
  const records = ingestCodexDir(path.join(FIXTURES, "codex"));
  assert.ok(records.every((r) => r.session_id === "codex-session-fixture-1"));
});

test("codex ingester: since filter drops old turns", () => {
  // First event is at 08:05, second at 08:15; cutoff at 08:10 → 1 record
  const since = new Date("2026-03-15T08:10:00.000Z");
  const records = ingestCodexDir(path.join(FIXTURES, "codex"), { since });
  assert.equal(records.length, 1);
  // The surviving record (08:15): input = 50000 - 8000 = 42000
  assert.equal(records[0].input_tokens, 42000);
});

test("codex ingester: cwd filter matches session cwd", () => {
  const records = ingestCodexDir(path.join(FIXTURES, "codex"), {
    cwd: "/Users/me",
  });
  assert.equal(records.length, 2);
});

test("codex ingester: cwd filter rejects non-matching", () => {
  const records = ingestCodexDir(path.join(FIXTURES, "codex"), {
    cwd: "/Users/other",
  });
  assert.equal(records.length, 0);
});

test("codex ingester: returns empty for nonexistent home", () => {
  const records = ingestCodexDir("/nonexistent/path/xyz");
  assert.equal(records.length, 0);
});

test("codex ingester: schema-drift — info:null lines do not throw and are skipped", () => {
  const tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), "codex-test-"));
  const dayDir = path.join(tmpHome, "sessions", "2026", "01", "01");
  fs.mkdirSync(dayDir, { recursive: true });
  fs.writeFileSync(
    path.join(dayDir, "rollout-x.jsonl"),
    '{"timestamp":"2026-01-01T00:00:00.000Z","type":"session_meta","payload":{"id":"s1","cwd":"/tmp"}}\n' +
    '{"timestamp":"2026-01-01T00:01:00.000Z","type":"event_msg","payload":{"type":"token_count","info":null}}\n'
  );
  let records;
  assert.doesNotThrow(() => {
    records = ingestCodexDir(tmpHome);
  });
  assert.equal(records.length, 0);
});

// ---------------------------------------------------------------------------
// install-detect tests
// ---------------------------------------------------------------------------

function makeTmpHome() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "tokenmax-detect-"));
}

test("install-detect: returns marker when installed_at file exists", () => {
  const home = makeTmpHome();
  const tokenmaxDir = path.join(home, ".tokenmax");
  fs.mkdirSync(tokenmaxDir, { recursive: true });
  fs.writeFileSync(
    path.join(tokenmaxDir, "installed_at"),
    "2026-02-14T12:00:00.000Z"
  );
  const result = detectInstallDate(home);
  assert.equal(result.source, "marker");
  assert.ok(result.date instanceof Date);
  assert.equal(result.date.toISOString(), "2026-02-14T12:00:00.000Z");
});

test("install-detect: returns none when no artifacts exist", () => {
  const home = makeTmpHome();
  const result = detectInstallDate(home);
  assert.equal(result.source, "none");
  assert.equal(result.date, null);
});

test("install-detect: returns hook when settings.json has PreToolUse rtk hook", () => {
  const home = makeTmpHome();
  const claudeDir = path.join(home, ".claude");
  fs.mkdirSync(claudeDir, { recursive: true });
  const settingsPath = path.join(claudeDir, "settings.json");
  fs.writeFileSync(
    settingsPath,
    JSON.stringify({
      hooks: {
        PreToolUse: [{ command: "rtk hook" }],
      },
    })
  );
  const result = detectInstallDate(home);
  assert.equal(result.source, "hook");
  assert.ok(result.date instanceof Date);
});

test("install-detect: hook source not triggered when settings.json lacks rtk hook", () => {
  const home = makeTmpHome();
  const claudeDir = path.join(home, ".claude");
  fs.mkdirSync(claudeDir, { recursive: true });
  fs.writeFileSync(
    path.join(claudeDir, "settings.json"),
    JSON.stringify({ hooks: { PreToolUse: [{ command: "some-other-tool" }] } })
  );
  const result = detectInstallDate(home);
  // No marker, no rtk hook — should be "none"
  assert.equal(result.source, "none");
  assert.equal(result.date, null);
});

test("install-detect: marker takes priority over hook when both present", () => {
  const home = makeTmpHome();
  // Write marker
  const tokenmaxDir = path.join(home, ".tokenmax");
  fs.mkdirSync(tokenmaxDir, { recursive: true });
  fs.writeFileSync(
    path.join(tokenmaxDir, "installed_at"),
    "2026-01-01T00:00:00.000Z"
  );
  // Write settings.json with hook
  const claudeDir = path.join(home, ".claude");
  fs.mkdirSync(claudeDir, { recursive: true });
  fs.writeFileSync(
    path.join(claudeDir, "settings.json"),
    JSON.stringify({ hooks: { PreToolUse: ["rtk hook"] } })
  );
  const result = detectInstallDate(home);
  assert.equal(result.source, "marker");
  assert.equal(result.date.toISOString(), "2026-01-01T00:00:00.000Z");
});

test("install-detect: hook accepts string hook entries (not just objects)", () => {
  const home = makeTmpHome();
  const claudeDir = path.join(home, ".claude");
  fs.mkdirSync(claudeDir, { recursive: true });
  fs.writeFileSync(
    path.join(claudeDir, "settings.json"),
    JSON.stringify({
      hooks: {
        PreToolUse: ["rtk hook"],
      },
    })
  );
  const result = detectInstallDate(home);
  assert.equal(result.source, "hook");
});

test("install-detect: malformed installed_at falls through to next priority", () => {
  const home = makeTmpHome();
  const tokenmaxDir = path.join(home, ".tokenmax");
  fs.mkdirSync(tokenmaxDir, { recursive: true });
  fs.writeFileSync(path.join(tokenmaxDir, "installed_at"), "not-a-date");
  const result = detectInstallDate(home);
  // Malformed marker → fall through → no hook → none
  assert.equal(result.source, "none");
});
