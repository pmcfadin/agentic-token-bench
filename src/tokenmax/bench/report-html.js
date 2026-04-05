/**
 * report-html.js — single-file HTML report renderer for tokenmax bench output.
 * Produces a self-contained HTML document with inline CSS, inline JS, and
 * hand-rolled SVG charts. No CDN dependencies, no external resources.
 *
 * <!-- Privacy: this document contains NO message content, no file paths beyond
 *      the cwd root, and no prompts. Only aggregate numeric statistics are included. -->
 */

"use strict";

const CLI_LABELS = {
  claude: "Claude Code",
  gemini: "Gemini CLI",
  codex: "Codex CLI",
};

const MINUS = "\u2212";
const ENDASH = "\u2013";

function fmtDate(d) {
  return d instanceof Date ? d.toISOString().slice(0, 10) : String(d);
}

function fmtNum(n) {
  return Number(n).toLocaleString("en-US");
}

function fmtPct(n) {
  if (n === null || n === undefined) return null;
  const sign = n < 0 ? MINUS : "+";
  return `${sign}${Math.abs(n)}%`;
}

function fmtPts(n) {
  if (n === null || n === undefined) return null;
  const sign = n < 0 ? MINUS : "+";
  return `${sign}${Math.abs(n)}pt`;
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ---------------------------------------------------------------------------
// SVG chart builder
// ---------------------------------------------------------------------------

const SVG_W = 480;
const SVG_H = 160;
const PAD = { top: 12, right: 12, bottom: 28, left: 56 };

function buildSvg(rollingPoints, installDate) {
  if (!rollingPoints || rollingPoints.length === 0) return "";

  const xs = rollingPoints.map((p) => p.date.getTime());
  const ys = rollingPoints.map((p) => p.median);

  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = 0;
  const yMax = Math.max(...ys) * 1.1 || 1;

  const chartW = SVG_W - PAD.left - PAD.right;
  const chartH = SVG_H - PAD.top - PAD.bottom;

  function toX(t) {
    if (xMax === xMin) return PAD.left + chartW / 2;
    return PAD.left + ((t - xMin) / (xMax - xMin)) * chartW;
  }

  function toY(v) {
    return PAD.top + chartH - ((v - yMin) / (yMax - yMin)) * chartH;
  }

  // Polyline points.
  const pts = rollingPoints.map((p) => `${toX(p.date.getTime()).toFixed(1)},${toY(p.median).toFixed(1)}`).join(" ");

  // Y-axis ticks (3 ticks: 0, mid, max).
  const yTicks = [0, Math.round(yMax / 2), Math.round(yMax)];
  const yTickLines = yTicks
    .map((v) => {
      const cy = toY(v).toFixed(1);
      const label = v >= 1000 ? `${Math.round(v / 1000)}k` : String(v);
      return `<line x1="${PAD.left}" y1="${cy}" x2="${PAD.left + chartW}" y2="${cy}" stroke="#e5e7eb" stroke-width="1"/>
<text x="${(PAD.left - 4).toFixed(1)}" y="${cy}" text-anchor="end" dominant-baseline="middle" font-size="9" fill="#6b7280">${esc(label)}</text>`;
    })
    .join("\n");

  // X-axis label: first and last date.
  const xAxisLabels = `
<text x="${PAD.left.toFixed(1)}" y="${(SVG_H - 6).toFixed(1)}" text-anchor="middle" font-size="9" fill="#6b7280">${esc(fmtDate(rollingPoints[0].date))}</text>
<text x="${(PAD.left + chartW).toFixed(1)}" y="${(SVG_H - 6).toFixed(1)}" text-anchor="middle" font-size="9" fill="#6b7280">${esc(fmtDate(rollingPoints[rollingPoints.length - 1].date))}</text>`;

  // Install date vertical line.
  let installLine = "";
  if (installDate && installDate instanceof Date) {
    const ix = toX(installDate.getTime());
    if (ix >= PAD.left && ix <= PAD.left + chartW) {
      installLine = `<line x1="${ix.toFixed(1)}" y1="${PAD.top}" x2="${ix.toFixed(1)}" y2="${(PAD.top + chartH).toFixed(1)}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>
<text x="${(ix + 3).toFixed(1)}" y="${(PAD.top + 8).toFixed(1)}" font-size="8" fill="#f59e0b">install</text>`;
    }
  }

  return `<svg viewBox="0 0 ${SVG_W} ${SVG_H}" width="${SVG_W}" height="${SVG_H}" xmlns="http://www.w3.org/2000/svg" style="display:block;max-width:100%">
${yTickLines}
${xAxisLabels}
${installLine}
<polyline points="${pts}" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
</svg>`;
}

// ---------------------------------------------------------------------------
// Table builder
// ---------------------------------------------------------------------------

function buildTable(summary) {
  const rows = ["claude", "gemini", "codex"]
    .map((cli) => {
      const s = summary[cli];
      if (!s || s.turns === 0) {
        return `<tr><td>${esc(CLI_LABELS[cli])}</td><td colspan="7" style="color:#9ca3af;font-style:italic">no sessions in window</td></tr>`;
      }

      const beforeMedian = s.before ? fmtNum(s.before.medianInputTokens) : "—";
      const afterMedian = s.after ? fmtNum(s.after.medianInputTokens) : "—";
      const beforeCache = s.before && s.before.cacheReadRatio > 0 ? `${Math.round(s.before.cacheReadRatio * 100)}%` : "—";
      const afterCache = s.after && s.after.cacheReadRatio > 0 ? `${Math.round(s.after.cacheReadRatio * 100)}%` : "—";

      let inputDelta = "—";
      let cacheDelta = "—";
      if (s.stepChange) {
        if (s.stepChange.inputTokensPct !== null) {
          const v = fmtPct(s.stepChange.inputTokensPct);
          const cls = s.stepChange.inputTokensPct < 0 ? "good" : "bad";
          inputDelta = `<span class="${cls}">${esc(v)}</span>`;
        }
        if (s.stepChange.cacheHitDeltaPts !== null && s.stepChange.cacheHitDeltaPts !== 0) {
          const v = fmtPts(s.stepChange.cacheHitDeltaPts);
          const cls = s.stepChange.cacheHitDeltaPts > 0 ? "good" : "bad";
          cacheDelta = `<span class="${cls}">${esc(v)}</span>`;
        }
      }

      const dateRange =
        s.windowStart && s.windowEnd
          ? `${fmtDate(s.windowStart)} ${ENDASH} ${fmtDate(s.windowEnd)}`
          : "";

      return `<tr>
  <td>${esc(CLI_LABELS[cli])}</td>
  <td>${esc(dateRange)}</td>
  <td>${fmtNum(s.sessions)}</td>
  <td>${fmtNum(s.turns)}</td>
  <td>${esc(beforeMedian)}</td>
  <td>${esc(afterMedian)}</td>
  <td>${inputDelta}</td>
  <td>${beforeCache} / ${afterCache}</td>
</tr>`;
    })
    .join("\n");

  return `<table>
<thead>
<tr>
  <th>CLI</th>
  <th>Window</th>
  <th>Sessions</th>
  <th>Turns</th>
  <th>Median input (before)</th>
  <th>Median input (after)</th>
  <th>Input &Delta;</th>
  <th>Cache hit (before/after)</th>
</tr>
</thead>
<tbody>
${rows}
</tbody>
</table>`;
}

// ---------------------------------------------------------------------------
// renderHtml
// ---------------------------------------------------------------------------

/**
 * renderHtml({ summary, rolling, installDate, installSource, windowSince }) → string
 *
 * @param {object} summary        - PerCliSummary from metrics.summarize()
 * @param {object} rolling        - { claude: [...], gemini: [...], codex: [...] } from rollingMedian
 * @param {Date|null} installDate
 * @param {string|null} installSource
 * @param {Date|null} windowSince
 * @returns {string} full HTML document
 */
function renderHtml({ summary, rolling = {}, installDate = null, installSource = null, windowSince = null }) {
  const cliOrder = ["claude", "gemini", "codex"];

  const charts = cliOrder
    .filter((cli) => summary[cli] && summary[cli].turns > 0)
    .map((cli) => {
      const s = summary[cli];
      const svg = buildSvg(rolling[cli] || [], installDate);

      let stepAnnotation = "";
      if (s.stepChange && s.stepChange.inputTokensPct !== null) {
        const v = fmtPct(s.stepChange.inputTokensPct);
        const cls = s.stepChange.inputTokensPct < 0 ? "good" : "bad";
        stepAnnotation = `<span class="${cls} step-annotation">${esc(v)} input tokens/turn</span>`;
      }

      return `<section class="chart-section">
  <h2>${esc(CLI_LABELS[cli])}</h2>
  <p class="chart-subtitle">7-day rolling median input tokens/turn</p>
  ${svg}
  <div class="annotation">${stepAnnotation}</div>
</section>`;
    })
    .join("\n");

  const table = buildTable(summary);

  const installInfo = installDate
    ? `<p class="meta">tokenmax installed: <strong>${esc(fmtDate(installDate))}</strong>${installSource ? ` (detected from ${esc(installSource)})` : ""}</p>`
    : `<p class="meta warn">No install date detected. Run <code>tokenmax install</code> to set a marker.</p>`;

  const windowInfo = windowSince
    ? `<p class="meta">Window start: <strong>${esc(fmtDate(windowSince))}</strong></p>`
    : "";

  const generatedAt = new Date().toISOString().slice(0, 10);

  return `<!DOCTYPE html>
<!-- Privacy: this document contains NO message content, no file paths beyond
     the cwd root, and no prompts. Only aggregate numeric statistics are included. -->
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>tokenmax bench report</title>
<style>
*, *::before, *::after { box-sizing: border-box; }
body { font-family: system-ui, sans-serif; margin: 0; padding: 24px 32px; background: #f9fafb; color: #111827; }
h1 { font-size: 1.5rem; margin-bottom: 4px; }
.meta { color: #6b7280; font-size: 0.875rem; margin: 2px 0; }
.meta.warn { color: #d97706; }
.charts { display: flex; flex-wrap: wrap; gap: 24px; margin: 24px 0; }
.chart-section { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; min-width: 280px; }
.chart-section h2 { font-size: 1rem; margin: 0 0 2px; }
.chart-subtitle { font-size: 0.75rem; color: #9ca3af; margin: 0 0 8px; }
.annotation { font-size: 0.85rem; margin-top: 6px; }
.step-annotation { font-weight: 600; }
.good { color: #16a34a; }
.bad  { color: #dc2626; }
table { border-collapse: collapse; width: 100%; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
th, td { text-align: left; padding: 10px 14px; font-size: 0.875rem; border-bottom: 1px solid #f3f4f6; }
th { background: #f9fafb; font-weight: 600; color: #374151; }
tr:last-child td { border-bottom: none; }
footer { margin-top: 24px; font-size: 0.75rem; color: #9ca3af; }
</style>
</head>
<body>
<h1>tokenmax bench report</h1>
${installInfo}
${windowInfo}
<p class="meta">Generated: ${esc(generatedAt)}</p>
<div class="charts">
${charts}
</div>
<h2>Summary table</h2>
${table}
<footer>
  Generated by tokenmax bench &mdash; aggregate statistics only, no message content.
</footer>
<script>
// No external scripts. Chart rendering is inline SVG above.
</script>
</body>
</html>`;
}

module.exports = { renderHtml };
