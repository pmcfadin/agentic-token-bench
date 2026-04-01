"""Static HTML overview page for the benchmark.

This page explains the official run lifecycle and where token usage comes
from. It is intentionally self-contained so it can be opened beside the
results report without any extra assets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

_LIFECYCLE_STEPS: list[tuple[str, str, str]] = [
    (
        "1",
        "Load the task manifest",
        (
            "Each YAML manifest defines the repo, pinned commit, objective, step list, "
            "validation commands, and completion contract."
        ),
    ),
    (
        "2",
        "Prepare the same repository state",
        (
            "The harness checks out the pinned Cassandra commit into an isolated workspace, "
            "so every run starts from the same codebase."
        ),
    ),
    (
        "3",
        "Render the canonical prompt pack",
        (
            "The prompt includes repository context, the full phase list, the current step, "
            "tool rules, validation expectations, and the required output format."
        ),
    ),
    (
        "4",
        "Apply the variant rules",
        (
            "Baseline removes the tool under test from PATH. tool_variant exposes the wrapped "
            "tool so the agent can use it naturally."
        ),
    ),
    (
        "5",
        "Run the agent step by step",
        (
            "The adapter executes each step, the harness records tool calls and trace events, "
            "and the agent reads the resulting command output back into its context."
        ),
    ),
    (
        "6",
        "Validate and classify the run",
        (
            "Validation commands run after the steps finish. The harness then classifies the run "
            "as valid or invalid and stores the reported token counts from the final step."
        ),
    ),
]

_TOKEN_SOURCES: list[tuple[str, str]] = [
    (
        "Prompt context",
        (
            "Long task descriptions, phase lists, tool rules, and validation instructions are all "
            "part of the prompt the agent reads."
        ),
    ),
    (
        "Search and reading",
        (
            "Broad searches, file reads, and command output are fed back into the agent's context, "
            "so exploratory loops quickly add input tokens."
        ),
    ),
    (
        "Tool output",
        (
            "Verbose search results, test logs, and wrapper traces all become tokenized context for "
            "the next turn."
        ),
    ),
    (
        "Retries and repairs",
        (
            "Failed attempts, extra validation, and repair iterations keep the conversation going and "
            "increase both input and output tokens."
        ),
    ),
]

_FAQ: list[tuple[str, str]] = [
    (
        "What counts as tokens?",
        (
            "The benchmark records the agent CLI's reported input, output, and total token counts. "
            "It does not estimate token usage from the repository or the prompt."
        ),
    ),
    (
        "Why compare baseline and tool_variant?",
        (
            "They run the same task from the same commit. The only controlled difference is whether the "
            "tool under test is removed or exposed."
        ),
    ),
    (
        "Why can a failed run still appear in raw results?",
        (
            "The harness keeps status and validity separate. A run can fail the task and still be valid "
            "if the trace, enforcement, and validation artifacts are complete."
        ),
    ),
    (
        "Why do some runs use far more tokens than others?",
        (
            "Search-heavy loops, verbose command output, retries, and long final answers all push the "
            "reported total upward."
        ),
    ),
]


def _card(title: str, body: str, *, kicker: str | None = None) -> str:
    kicker_html = f'<div class="card-kicker">{escape(kicker)}</div>' if kicker else ""
    return (
        f'<article class="card">'
        f"{kicker_html}"
        f"<h3>{escape(title)}</h3>"
        f"<p>{escape(body)}</p>"
        f"</article>"
    )


def _step_card(index: str, title: str, body: str) -> str:
    return (
        f'<article class="step-card">'
        f'<div class="step-index">{escape(index)}</div>'
        f"<h3>{escape(title)}</h3>"
        f"<p>{escape(body)}</p>"
        f"</article>"
    )


def _faq_item(question: str, answer: str, *, open_item: bool = False) -> str:
    open_attr = " open" if open_item else ""
    return (
        f"<details{open_attr}>"
        f"<summary>{escape(question)}</summary>"
        f"<div class=\"faq-body\">{escape(answer)}</div>"
        f"</details>"
    )


def render_benchmark_overview_html(*, generated_at: datetime | None = None) -> str:
    """Render a standalone HTML page that explains the benchmark."""
    generated_at = generated_at or datetime.now(tz=timezone.utc)

    quick_facts = "".join(
        [
            _card(
                "Same task, same commit",
                "Every run starts from the pinned Cassandra revision recorded in the task manifest.",
                kicker="Controlled input",
            ),
            _card(
                "Two variants",
                "baseline removes the tool under test; tool_variant exposes the wrapped tool on PATH.",
                kicker="Comparison model",
            ),
            _card(
                "Tokens are reported",
                "The run record stores the adapter's reported input, output, and total token counts.",
                kicker="Measurement",
            ),
            _card(
                "Validity is separate",
                "A run can fail the task and still be retained if the trace and validation artifacts are complete.",
                kicker="Result filtering",
            ),
        ]
    )

    lifecycle_cards = "".join(_step_card(*step) for step in _LIFECYCLE_STEPS)
    token_cards = "".join(
        _card(title, body, kicker="Token source") for title, body in _TOKEN_SOURCES
    )
    faq_items = "".join(
        _faq_item(question, answer, open_item=index == 0)
        for index, (question, answer) in enumerate(_FAQ)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>agentic-token-bench overview</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --panel-soft: #eff6ff;
      --text: #0f172a;
      --muted: #475569;
      --border: #dbe4f0;
      --blue: #1e40af;
      --blue-2: #3b82f6;
      --amber: #f59e0b;
      --amber-soft: #fef3c7;
      --shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
      --radius: 22px;
    }}

    * {{
      box-sizing: border-box;
    }}

    html {{
      background:
        radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 28%),
        radial-gradient(circle at top right, rgba(245, 158, 11, 0.12), transparent 24%),
        var(--bg);
    }}

    body {{
      margin: 0;
      color: var(--text);
      font-family: "Fira Sans", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      line-height: 1.6;
    }}

    code, pre {{
      font-family: "Fira Code", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}

    .page {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}

    .hero {{
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #1d4ed8 100%);
      color: white;
      border-radius: 32px;
      padding: 32px;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }}

    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -36px -84px auto;
      width: 260px;
      height: 260px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(245, 158, 11, 0.28) 0%, rgba(245, 158, 11, 0) 68%);
      pointer-events: none;
    }}

    .eyebrow {{
      display: inline-flex;
      gap: 10px;
      align-items: center;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.16);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-weight: 700;
    }}

    h1 {{
      margin: 16px 0 10px;
      font-size: clamp(2.1rem, 4vw, 4rem);
      line-height: 1.02;
      max-width: 12ch;
    }}

    .hero p {{
      max-width: 76ch;
      margin: 0;
      color: rgba(255, 255, 255, 0.86);
      font-size: 1.04rem;
    }}

    .hero-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 20px;
    }}

    .hero-link {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      color: white;
      text-decoration: none;
      border: 1px solid rgba(255, 255, 255, 0.16);
      background: rgba(255, 255, 255, 0.09);
      transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
    }}

    .hero-link:hover {{
      transform: translateY(-1px);
      border-color: rgba(255, 255, 255, 0.3);
      background: rgba(255, 255, 255, 0.14);
    }}

    .fact-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 26px;
    }}

    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
      padding: 18px;
    }}

    .card-kicker {{
      display: inline-flex;
      margin-bottom: 10px;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      background: var(--panel-soft);
      color: var(--blue);
      font-weight: 700;
    }}

    .card h3 {{
      margin: 0 0 8px;
      font-size: 1rem;
    }}

    .card p {{
      margin: 0;
      color: var(--muted);
      font-size: 0.94rem;
    }}

    .panel {{
      margin-top: 22px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .section-heading {{
      padding: 24px 24px 0;
    }}

    .section-kicker {{
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--blue);
      font-weight: 700;
      font-size: 0.75rem;
    }}

    .section-heading h2 {{
      margin: 6px 0 8px;
      font-size: 1.52rem;
    }}

    .subtle {{
      margin: 0;
      max-width: 72ch;
      color: var(--muted);
    }}

    .split-grid {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 18px;
      padding: 24px;
    }}

    .step-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}

    .step-card {{
      position: relative;
      border: 1px solid var(--border);
      border-radius: 18px;
      background: linear-gradient(180deg, #ffffff, #f8fbff);
      padding: 18px;
      min-height: 170px;
    }}

    .step-index {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 36px;
      border-radius: 999px;
      background: linear-gradient(180deg, var(--blue), #60a5fa);
      color: white;
      font-weight: 700;
      margin-bottom: 12px;
    }}

    .step-card h3 {{
      margin: 0 0 8px;
      font-size: 1.05rem;
    }}

    .step-card p {{
      margin: 0;
      color: var(--muted);
    }}

    .token-panel {{
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 18px;
      background: linear-gradient(180deg, #ffffff, #fffaf0);
    }}

    .token-panel h3 {{
      margin: 0 0 10px;
      font-size: 1.06rem;
    }}

    .token-panel p {{
      margin: 0 0 14px;
      color: var(--muted);
    }}

    .token-list {{
      display: grid;
      gap: 12px;
    }}

    .token-item {{
      border: 1px solid #fde68a;
      border-radius: 16px;
      background: rgba(255, 251, 235, 0.86);
      padding: 14px;
    }}

    .token-item strong {{
      display: block;
      margin-bottom: 6px;
      color: #92400e;
    }}

    .token-item span {{
      color: var(--muted);
      font-size: 0.94rem;
    }}

    .faq-grid {{
      display: grid;
      gap: 10px;
      padding: 24px;
    }}

    details {{
      border: 1px solid var(--border);
      border-radius: 16px;
      background: #fff;
      overflow: hidden;
    }}

    summary {{
      list-style: none;
      cursor: pointer;
      padding: 16px 18px;
      font-weight: 700;
      color: var(--text);
    }}

    summary::-webkit-details-marker {{
      display: none;
    }}

    summary::after {{
      content: "+";
      float: right;
      color: var(--blue);
      font-size: 1.2rem;
      line-height: 1;
    }}

    details[open] summary::after {{
      content: "−";
    }}

    .faq-body {{
      padding: 0 18px 16px;
      color: var(--muted);
    }}

    .footer {{
      padding: 24px 8px 0;
      color: var(--muted);
      font-size: 0.92rem;
    }}

    .footer a {{
      color: var(--blue);
      text-decoration: none;
      font-weight: 700;
    }}

    .footer a:hover {{
      text-decoration: underline;
    }}

    @media (max-width: 1080px) {{
      .fact-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}

      .split-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    @media (max-width: 720px) {{
      .page {{
        padding-inline: 14px;
      }}

      .hero {{
        padding: 22px;
        border-radius: 24px;
      }}

      .fact-grid,
      .step-grid {{
        grid-template-columns: 1fr;
      }}

      .section-heading,
      .split-grid,
      .faq-grid {{
        padding-inline: 16px;
      }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{
        scroll-behavior: auto;
        transition-duration: 0.01ms !important;
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <div class="eyebrow">agentic-token-bench</div>
      <h1>What the benchmark does</h1>
      <p>
        The benchmark runs the same Cassandra task under two controlled variants, then compares the
        adapter-reported token totals. baseline removes the tool under test, tool_variant exposes it.
        That lets you see how tool access changes the cost of solving the same work.
      </p>
      <div class="hero-links">
        <a class="hero-link" href="report.html">Open results report</a>
        <a class="hero-link" href="../../docs/reproduction.md">Read reproduction docs</a>
      </div>
      <div class="fact-grid">
        {quick_facts}
      </div>
    </header>

    <section class="panel" id="lifecycle">
      <div class="section-heading">
        <div class="section-kicker">Run lifecycle</div>
        <h2>How one official run is executed</h2>
        <p class="subtle">
          The benchmark keeps the repository state, task instructions, and validation commands fixed.
          The harness changes only the tool access and records what happens.
        </p>
      </div>
      <div class="split-grid">
        <div class="step-grid">
          {lifecycle_cards}
        </div>
        <aside class="token-panel">
          <h3>Where tokens actually go</h3>
          <p>
            The harness does not estimate tokens. It captures the agent CLI's reported
            <code>reported_input_tokens</code>, <code>reported_output_tokens</code>, and
            <code>reported_total_tokens</code> from the final step result and stores them in
            <code>run.json</code>.
          </p>
          <div class="token-list">
            {token_cards}
          </div>
        </aside>
      </div>
    </section>

    <section class="panel" id="faq">
      <div class="section-heading">
        <div class="section-kicker">FAQ</div>
        <h2>Common questions about the token numbers</h2>
        <p class="subtle">
          These answers explain why the same family can still show very different totals across agents
          or across individual runs.
        </p>
      </div>
      <div class="faq-grid">
        {faq_items}
      </div>
    </section>

    <div class="footer">
      Pair this page with <a href="report.html">report.html</a> for before/after comparisons, and with
      <a href="../../docs/reproduction.md">docs/reproduction.md</a> for the full run instructions.
      Generated at {escape(generated_at.strftime("%Y-%m-%d %H:%M UTC"))}.
    </div>
  </main>
</body>
</html>"""


def write_benchmark_overview_html(output_path: Path) -> Path:
    """Write the benchmark overview page to *output_path*."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_benchmark_overview_html(), encoding="utf-8")
    return output_path
