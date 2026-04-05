const assert = require("node:assert/strict");
const fs = require("fs");
const os = require("os");
const path = require("path");
const test = require("node:test");

const { parseCommand } = require("../../src/tokenmax/utils");
const { bench, parseSince, parseCliFilter, runBench } = require("../../src/tokenmax/bench/bench");

const FIXTURES = path.join(__dirname, "fixtures", "bench");

function makeFixtureHome() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "tokenmax-bench-home-"));
  fs.symlinkSync(path.join(FIXTURES, "claude"), path.join(home, ".claude"));
  fs.symlinkSync(path.join(FIXTURES, "gemini"), path.join(home, ".gemini"));
  fs.symlinkSync(path.join(FIXTURES, "codex"), path.join(home, ".codex"));
  return home;
}

test("parseCommand parses 'bench' action with flags", () => {
  const c = parseCommand(["bench", "--since", "30d", "--cli", "claude,codex", "--html", "r.html", "--json"]);
  assert.equal(c.action, "bench");
  assert.equal(c.flags.since, "30d");
  assert.equal(c.flags.cli, "claude,codex");
  assert.equal(c.flags.html, "r.html");
  assert.equal(c.flags.json, true);
});

test("parseCommand parses --flag=value form", () => {
  const c = parseCommand(["bench", "--since=7d", "--cli=gemini"]);
  assert.equal(c.flags.since, "7d");
  assert.equal(c.flags.cli, "gemini");
});

test("parseCommand rejects missing value for --since", () => {
  assert.throws(() => parseCommand(["bench", "--since"]));
});

test("parseSince handles relative and absolute", () => {
  const now = new Date("2026-04-04T00:00:00Z");
  assert.equal(parseSince("30d", now).toISOString(), "2026-03-05T00:00:00.000Z");
  assert.equal(parseSince("2026-02-01", now).toISOString().slice(0, 10), "2026-02-01");
  assert.equal(parseSince(null), null);
  assert.throws(() => parseSince("bogus"));
});

test("parseCliFilter default returns all three CLIs", () => {
  assert.deepEqual(parseCliFilter(null).sort(), ["claude", "codex", "gemini"]);
  assert.deepEqual(parseCliFilter("claude, codex"), ["claude", "codex"]);
  assert.throws(() => parseCliFilter("bogus"));
});

test("runBench against fixture home returns turns from all three CLIs", () => {
  const home = makeFixtureHome();
  const result = runBench({
    homeDir: home,
    clis: ["claude", "gemini", "codex"],
    since: null,
    cwd: null,
  });
  assert.ok(result.turns.length > 0, "should have ingested turns");
  const byCli = new Set(result.turns.map((t) => t.cli));
  assert.ok(byCli.has("claude"));
  assert.ok(byCli.has("gemini"));
  assert.ok(byCli.has("codex"));
  assert.equal(result.installSource, "none");
  assert.equal(result.installDate, null);
});

test("bench() text output lists all three CLIs", () => {
  const home = makeFixtureHome();
  const out = bench({ homeDir: home });
  assert.equal(out.ok, true);
  assert.match(out.text, /Claude Code/);
  assert.match(out.text, /Gemini CLI/);
  assert.match(out.text, /Codex CLI/);
});

test("bench() --json returns structured payload", () => {
  const home = makeFixtureHome();
  const out = bench({ homeDir: home, json: true });
  assert.equal(out.ok, true);
  assert.equal(out.json.command, "bench");
  assert.equal(out.json.status, "ok");
  assert.ok("claude" in out.json.agents);
  assert.ok("gemini" in out.json.agents);
  assert.ok("codex" in out.json.agents);
});

test("bench() --html writes a self-contained HTML file", () => {
  const home = makeFixtureHome();
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "tokenmax-bench-html-"));
  const htmlPath = path.join(tmp, "report.html");
  bench({ homeDir: home, htmlPath });
  const content = fs.readFileSync(htmlPath, "utf8");
  assert.match(content, /<svg/);
  assert.match(content, /<!DOCTYPE html>/i);
  // Privacy: no message content leaks
  assert.doesNotMatch(content, /SizeTieredCompactionStrategy/);
});

test("bench() --cli filter restricts to requested CLIs", () => {
  const home = makeFixtureHome();
  const out = bench({ homeDir: home, cliFilter: "claude", json: true });
  assert.ok(out.json.agents.claude.turns > 0);
  // Other CLIs get a zeroed summary because they weren't ingested
  assert.equal(out.json.agents.gemini.turns, 0);
  assert.equal(out.json.agents.codex.turns, 0);
});

test("bench() writes installed_at marker and detects it", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "tokenmax-bench-marker-"));
  fs.symlinkSync(path.join(FIXTURES, "claude"), path.join(home, ".claude"));
  fs.mkdirSync(path.join(home, ".tokenmax"), { recursive: true });
  fs.writeFileSync(path.join(home, ".tokenmax", "installed_at"), "2026-03-01T00:00:00Z");
  const out = bench({ homeDir: home, cliFilter: "claude", json: true });
  assert.equal(out.json.install_source, "marker");
  assert.equal(out.json.install_date, "2026-03-01T00:00:00.000Z");
});
