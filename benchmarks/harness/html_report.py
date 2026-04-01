"""Static HTML report generation for benchmark comparisons."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from statistics import mean

import yaml

from benchmarks.harness.models import RunRecord, RunValidity, Variant, ValidationStatus

_VARIANTS = (Variant.baseline, Variant.tool_variant)


@dataclass(frozen=True)
class Metrics:
    """Aggregated metrics for one group of runs."""

    run_count: int
    avg_tokens: float | None
    validation_pass_rate: float | None
    first_pass_success_rate: float | None
    avg_repair_iterations: float | None
    avg_elapsed_seconds: float | None


@dataclass(frozen=True)
class TaskInfo:
    """Lightweight metadata loaded from task manifests."""

    task_id: str
    title: str
    family: str


@dataclass(frozen=True)
class AgentTaskComparison:
    """Comparison row for one agent on one task."""

    agent_id: str
    baseline: Metrics
    tool_variant: Metrics
    token_delta: float | None
    token_reduction_pct: float | None
    task_scale: float | None


@dataclass(frozen=True)
class TaskComparison:
    """All agent comparisons for a single task."""

    task_info: TaskInfo
    agent_rows: list[AgentTaskComparison]


@dataclass(frozen=True)
class FamilyComparison:
    """All task comparisons for a single family."""

    family: str
    tasks: list[TaskComparison]


def load_run_records(results_dir: Path) -> list[RunRecord]:
    """Load every valid run.json file under *results_dir*."""
    runs: list[RunRecord] = []
    for json_path in sorted(Path(results_dir).rglob("run.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            runs.append(RunRecord.model_validate(data))
        except Exception:
            continue
    return runs


def load_task_index(tasks_dir: Path) -> dict[str, TaskInfo]:
    """Load task metadata from YAML manifests."""
    task_index: dict[str, TaskInfo] = {}
    for task_path in sorted(Path(tasks_dir).glob("*.yaml")):
        try:
            raw = yaml.safe_load(task_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        task_id = raw.get("task_id")
        title = raw.get("title")
        family = raw.get("family")
        if isinstance(task_id, str) and isinstance(title, str) and isinstance(family, str):
            task_index[task_id] = TaskInfo(task_id=task_id, title=title, family=family)
    return task_index


def _aggregate_metrics(runs: list[RunRecord]) -> Metrics:
    """Aggregate a list of runs into a compact metrics bundle."""
    valid_runs = [run for run in runs if run.validity == RunValidity.valid]
    if not valid_runs:
        return Metrics(
            run_count=0,
            avg_tokens=None,
            validation_pass_rate=None,
            first_pass_success_rate=None,
            avg_repair_iterations=None,
            avg_elapsed_seconds=None,
        )

    token_values = [
        run.reported_total_tokens
        for run in valid_runs
        if run.reported_total_tokens is not None
    ]
    elapsed_values = [
        run.elapsed_seconds for run in valid_runs if run.elapsed_seconds is not None
    ]

    return Metrics(
        run_count=len(valid_runs),
        avg_tokens=mean(token_values) if token_values else None,
        validation_pass_rate=sum(
            1 for run in valid_runs if run.validation_status == ValidationStatus.passed
        )
        / len(valid_runs),
        first_pass_success_rate=sum(
            1
            for run in valid_runs
            if run.validation_status == ValidationStatus.passed and run.repair_iterations == 0
        )
        / len(valid_runs),
        avg_repair_iterations=mean(run.repair_iterations for run in valid_runs),
        avg_elapsed_seconds=mean(elapsed_values) if elapsed_values else None,
    )


def _format_number(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "N/A"
    if digits == 0:
        return f"{value:,.0f}"
    return f"{value:,.{digits}f}"


def _format_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def _format_status(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _delta_and_reduction(
    before: float | None,
    after: float | None,
) -> tuple[float | None, float | None]:
    if before is None or after is None:
        return None, None

    delta = after - before
    if before == 0:
        return delta, None

    return delta, delta / before * 100


def _group_runs(runs: list[RunRecord]) -> tuple[list[str], dict[str, dict[str, dict[Variant, list[RunRecord]]]]]:
    agents = sorted({run.agent_id for run in runs})
    grouped: dict[str, dict[str, dict[Variant, list[RunRecord]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for run in runs:
        grouped[run.family][run.task_id][run.variant].append(run)
    return agents, grouped


def _build_family_comparisons(
    runs: list[RunRecord],
    task_index: dict[str, TaskInfo],
) -> list[FamilyComparison]:
    agents, grouped = _group_runs(runs)
    family_names = sorted(grouped)
    families: list[FamilyComparison] = []

    for family in family_names:
        task_ids = sorted(grouped[family])
        tasks: list[TaskComparison] = []
        for task_id in task_ids:
            task_info = task_index.get(
                task_id,
                TaskInfo(task_id=task_id, title=task_id, family=family),
            )
            agent_rows: list[AgentTaskComparison] = []
            task_max_tokens: float | None = None

            for agent_id in agents:
                agent_runs = [
                    run
                    for variant_runs in grouped[family][task_id].values()
                    for run in variant_runs
                    if run.agent_id == agent_id
                ]
                if not agent_runs:
                    continue

                baseline_runs = [
                    run
                    for run in grouped[family][task_id][Variant.baseline]
                    if run.agent_id == agent_id
                ]
                tool_runs = [
                    run
                    for run in grouped[family][task_id][Variant.tool_variant]
                    if run.agent_id == agent_id
                ]

                baseline = _aggregate_metrics(baseline_runs)
                tool_variant = _aggregate_metrics(tool_runs)

                token_delta, token_reduction_pct = _delta_and_reduction(
                    baseline.avg_tokens,
                    tool_variant.avg_tokens,
                )

                for value in (baseline.avg_tokens, tool_variant.avg_tokens):
                    if value is not None:
                        task_max_tokens = value if task_max_tokens is None else max(task_max_tokens, value)

                agent_rows.append(
                    AgentTaskComparison(
                        agent_id=agent_id,
                        baseline=baseline,
                        tool_variant=tool_variant,
                        token_delta=token_delta,
                        token_reduction_pct=token_reduction_pct,
                        task_scale=None,
                    )
                )

            scaled_rows = [
                AgentTaskComparison(
                    agent_id=row.agent_id,
                    baseline=row.baseline,
                    tool_variant=row.tool_variant,
                    token_delta=row.token_delta,
                    token_reduction_pct=row.token_reduction_pct,
                    task_scale=task_max_tokens,
                )
                for row in agent_rows
            ]
            tasks.append(TaskComparison(task_info=task_info, agent_rows=scaled_rows))
        families.append(FamilyComparison(family=family, tasks=tasks))

    return families


def _aggregate_by_agent(runs: list[RunRecord]) -> dict[str, dict[Variant, Metrics]]:
    by_agent: dict[str, dict[Variant, list[RunRecord]]] = defaultdict(lambda: defaultdict(list))
    for run in runs:
        by_agent[run.agent_id][run.variant].append(run)

    result: dict[str, dict[Variant, Metrics]] = {}
    for agent_id, variants in by_agent.items():
        result[agent_id] = {variant: _aggregate_metrics(variant_runs) for variant, variant_runs in variants.items()}
        for variant in _VARIANTS:
            result[agent_id].setdefault(variant, _aggregate_metrics([]))
    return result


def _render_metric_card(label: str, value: str, note: str | None = None, accent: str = "blue") -> str:
    note_html = f'<div class="card-note">{escape(note)}</div>' if note else ""
    return (
        f'<section class="metric-card metric-card--{accent}">'
        f'<div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(value)}</div>'
        f"{note_html}"
        f"</section>"
    )


def _render_bar(value: float | None, scale: float | None, tone: str, label: str) -> str:
    if value is None or scale is None or scale <= 0:
        width = 0.0
    else:
        width = max(6.0, min(100.0, value / scale * 100.0))
    bar_value = "N/A" if value is None else f"{value:,.0f}"
    return (
        f'<div class="bar-row">'
        f'<div class="bar-row__label">{escape(label)}</div>'
        f'<div class="bar-track">'
        f'<div class="bar bar--{tone}" style="width: {width:.1f}%"><span>{escape(bar_value)}</span></div>'
        f'</div>'
        f'</div>'
    )


def _render_task_table(task: TaskComparison) -> str:
    rows: list[str] = []
    for row in task.agent_rows:
        before = _render_bar(row.baseline.avg_tokens, row.task_scale, "baseline", "Before")
        after = _render_bar(row.tool_variant.avg_tokens, row.task_scale, "tool", "After")
        rows.append(
            "<tr>"
            f"<td data-label=\"Agent\"><span class=\"agent-pill\">{escape(row.agent_id)}</span></td>"
            f"<td data-label=\"Before\">{before}</td>"
            f"<td data-label=\"After\">{after}</td>"
            f"<td data-label=\"Delta\" class=\"metric-cell\">{_format_number(row.token_delta, 0)}</td>"
            f"<td data-label=\"Reduction\" class=\"metric-cell\">{_format_pct(row.token_reduction_pct)}</td>"
            f"<td data-label=\"Validation\" class=\"metric-cell\">{_format_status(row.baseline.validation_pass_rate)}</td>"
            f"<td data-label=\"Elapsed\" class=\"metric-cell\">{_format_number(row.baseline.avg_elapsed_seconds, 1)}</td>"
            f"<td data-label=\"Runs\" class=\"metric-cell\">{row.baseline.run_count}/{row.tool_variant.run_count}</td>"
            "</tr>"
        )

    return (
        "<table>"
        "<thead><tr>"
        "<th>Agent</th>"
        "<th>Before</th>"
        "<th>After</th>"
        "<th>Delta</th>"
        "<th>Reduction</th>"
        "<th>Validation</th>"
        "<th>Elapsed</th>"
        "<th>Runs</th>"
        "</tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _render_family_section(family: FamilyComparison) -> str:
    task_cards: list[str] = []
    for task in family.tasks:
        task_cards.append(
            "<article class=\"task-card\">"
            f"<div class=\"task-card__header\">"
            f"<div>"
            f"<div class=\"task-kicker\">{escape(task.task_info.family)}</div>"
            f"<h3>{escape(task.task_info.title)}</h3>"
            f"<div class=\"task-subtitle\"><code>{escape(task.task_info.task_id)}</code></div>"
            f"</div>"
            "</div>"
            f"{_render_task_table(task)}"
            "</article>"
        )

    return (
        f'<section class="family-section" id="family-{escape(family.family)}">'
        f'<div class="family-heading">'
        f'<div>'
        f'<div class="section-kicker">Family</div>'
        f'<h2>{escape(family.family)}</h2>'
        f'</div>'
        f'</div>'
        f"{''.join(task_cards)}"
        f"</section>"
    )


def render_html_report(
    runs: list[RunRecord],
    *,
    tasks_dir: Path,
    generated_at: datetime | None = None,
    source_results_dir: Path | None = None,
) -> str:
    """Render a standalone HTML report from benchmark run records."""
    generated_at = generated_at or datetime.now(tz=timezone.utc)
    valid_runs = [run for run in runs if run.validity == RunValidity.valid]
    invalid_runs = len(runs) - len(valid_runs)
    task_index = load_task_index(tasks_dir)
    families = _build_family_comparisons(valid_runs, task_index)
    agents = sorted({run.agent_id for run in valid_runs})
    by_agent = _aggregate_by_agent(valid_runs)

    overall_by_variant = {
        variant: _aggregate_metrics([run for run in valid_runs if run.variant == variant])
        for variant in _VARIANTS
    }

    overall_delta: float | None = None
    overall_reduction: float | None = None
    overall_delta, overall_reduction = _delta_and_reduction(
        overall_by_variant[Variant.baseline].avg_tokens,
        overall_by_variant[Variant.tool_variant].avg_tokens,
    )

    overall_scale_candidates = [
        metrics.avg_tokens
        for metrics in overall_by_variant.values()
        if metrics.avg_tokens is not None
    ]
    overall_scale = max(overall_scale_candidates) if overall_scale_candidates else None

    task_count = len({run.task_id for run in valid_runs})
    family_count = len(families)
    agent_count = len(agents)
    total_runs = len(runs)
    overall_validation_pass_rate = _aggregate_metrics(valid_runs).validation_pass_rate
    overall_validation_text = _format_status(overall_validation_pass_rate)

    agent_rows: list[str] = []
    for agent_id in agents:
        baseline = by_agent.get(agent_id, {}).get(Variant.baseline, _aggregate_metrics([]))
        tool_variant = by_agent.get(agent_id, {}).get(
            Variant.tool_variant, _aggregate_metrics([])
        )
        delta, reduction = _delta_and_reduction(baseline.avg_tokens, tool_variant.avg_tokens)
        agent_rows.append(
            "<tr>"
            f"<td data-label=\"Agent\"><span class=\"agent-pill\">{escape(agent_id)}</span></td>"
            f"<td data-label=\"Before\" class=\"metric-cell\">{_format_number(baseline.avg_tokens)}</td>"
            f"<td data-label=\"After\" class=\"metric-cell\">{_format_number(tool_variant.avg_tokens)}</td>"
            f"<td data-label=\"Delta\" class=\"metric-cell\">{_format_number(delta)}</td>"
            f"<td data-label=\"Reduction\" class=\"metric-cell\">{_format_pct(reduction)}</td>"
            f"<td data-label=\"Validation\" class=\"metric-cell\">{_format_status(tool_variant.validation_pass_rate)}</td>"
            f"<td data-label=\"Elapsed\" class=\"metric-cell\">{_format_number(tool_variant.avg_elapsed_seconds, 1)}</td>"
            f"<td data-label=\"Runs\" class=\"metric-cell\">{baseline.run_count}/{tool_variant.run_count}</td>"
            "</tr>"
        )

    family_nav = "".join(
        f'<a class="nav-pill" href="#family-{escape(family.family)}">{escape(family.family)}</a>'
        for family in families
    )

    family_sections = "".join(_render_family_section(family) for family in families)

    overall_before = _render_bar(
        overall_by_variant[Variant.baseline].avg_tokens,
        overall_scale,
        "baseline",
        "Before",
    )
    overall_after = _render_bar(
        overall_by_variant[Variant.tool_variant].avg_tokens,
        overall_scale,
        "tool",
        "After",
    )

    source_note = (
        f"<div class=\"source-note\">Source: {escape(str(source_results_dir))}</div>"
        if source_results_dir is not None
        else ""
    )
    overview_link = (
        '<div class="nav-strip">'
        '<a class="nav-pill" href="benchmark-overview.html">Benchmark walkthrough</a>'
        "</div>"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>agentic-token-bench report</title>
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
      --baseline: #2563eb;
      --tool: #d97706;
      --shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
      --radius: 22px;
    }}

    * {{
      box-sizing: border-box;
    }}

    html {{
      background:
        radial-gradient(circle at top left, rgba(59, 130, 246, 0.16), transparent 30%),
        radial-gradient(circle at top right, rgba(245, 158, 11, 0.12), transparent 24%),
        var(--bg);
    }}

    body {{
      margin: 0;
      color: var(--text);
      font-family: "Fira Sans", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      line-height: 1.55;
    }}

    code, pre {{
      font-family: "Fira Code", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}

    .page {{
      max-width: 1440px;
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
      inset: auto -40px -80px auto;
      width: 260px;
      height: 260px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(245, 158, 11, 0.26) 0%, rgba(245, 158, 11, 0) 68%);
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
      margin: 16px 0 8px;
      font-size: clamp(2rem, 4vw, 4rem);
      line-height: 1.04;
      max-width: 12ch;
    }}

    .hero p {{
      max-width: 72ch;
      margin: 0;
      color: rgba(255, 255, 255, 0.84);
      font-size: 1.04rem;
    }}

    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 14px;
      margin-top: 28px;
    }}

    .metric-card {{
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.14);
      border-radius: 20px;
      padding: 18px;
      min-height: 108px;
      backdrop-filter: blur(8px);
    }}

    .metric-card--blue {{
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.11), rgba(255, 255, 255, 0.05));
    }}

    .metric-card--amber {{
      background: rgba(245, 158, 11, 0.16);
    }}

    .metric-label {{
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: rgba(255, 255, 255, 0.72);
      margin-bottom: 10px;
    }}

    .metric-value {{
      font-size: 1.8rem;
      font-weight: 700;
      line-height: 1;
    }}

    .card-note {{
      margin-top: 10px;
      color: rgba(255, 255, 255, 0.72);
      font-size: 0.88rem;
    }}

    .summary-panel {{
      margin-top: 22px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 24px;
    }}

    .summary-grid {{
      display: grid;
      grid-template-columns: 1.05fr 1fr;
      gap: 22px;
      align-items: center;
    }}

    .summary-grid h2,
    .section-heading h2 {{
      margin: 0 0 8px;
      font-size: 1.5rem;
    }}

    .subtle {{
      color: var(--muted);
      margin: 0;
      max-width: 68ch;
    }}

    .comparison-stack {{
      display: grid;
      gap: 14px;
    }}

    .bar-row {{
      display: grid;
      grid-template-columns: 72px minmax(0, 1fr);
      gap: 12px;
      align-items: center;
    }}

    .bar-row__label {{
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--muted);
      font-weight: 700;
    }}

    .bar-track {{
      background: #e2e8f0;
      border-radius: 999px;
      overflow: hidden;
      min-height: 36px;
      position: relative;
    }}

    .bar {{
      min-height: 36px;
      display: flex;
      align-items: center;
      padding: 0 14px;
      color: white;
      font-weight: 700;
      border-radius: 999px;
      white-space: nowrap;
    }}

    .bar--baseline {{
      background: linear-gradient(90deg, var(--baseline), #60a5fa);
    }}

    .bar--tool {{
      background: linear-gradient(90deg, var(--tool), #fbbf24);
    }}

    .bar span {{
      mix-blend-mode: normal;
    }}

    .nav-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}

    .nav-pill,
    .agent-pill {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 0.84rem;
      font-weight: 700;
      text-decoration: none;
    }}

    .nav-pill {{
      background: white;
      color: var(--blue);
      border: 1px solid var(--border);
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.04);
    }}

    .nav-pill:hover {{
      border-color: var(--blue-2);
      transform: translateY(-1px);
    }}

    .agent-pill {{
      background: #eff6ff;
      color: var(--blue);
      border: 1px solid #bfdbfe;
    }}

    .table-panel,
    .family-section {{
      margin-top: 22px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .section-heading,
    .family-heading {{
      padding: 24px 24px 0;
    }}

    .section-kicker,
    .task-kicker {{
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--blue);
      font-weight: 700;
      font-size: 0.75rem;
    }}

    .source-note {{
      margin-top: 10px;
      color: rgba(255, 255, 255, 0.74);
      font-size: 0.88rem;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
    }}

    th, td {{
      padding: 14px 16px;
      border-top: 1px solid var(--border);
      vertical-align: middle;
    }}

    th {{
      background: #f8fbff;
      color: var(--muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      text-align: left;
    }}

    td {{
      font-size: 0.95rem;
    }}

    .metric-cell {{
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }}

    .task-card {{
      margin: 24px;
      border: 1px solid var(--border);
      border-radius: 20px;
      overflow: hidden;
      background: linear-gradient(180deg, #ffffff, #fbfdff);
    }}

    .task-card__header {{
      padding: 20px 20px 4px;
      border-bottom: 1px solid var(--border);
    }}

    .task-card h3 {{
      margin: 6px 0 6px;
      font-size: 1.15rem;
    }}

    .task-subtitle {{
      color: var(--muted);
      font-size: 0.92rem;
    }}

    .task-subtitle code {{
      background: #eff6ff;
      padding: 2px 6px;
      border-radius: 6px;
      color: var(--blue);
    }}

    .task-card table th,
    .task-card table td {{
      padding-left: 16px;
      padding-right: 16px;
    }}

    .task-card table th {{
      background: #fbfdff;
    }}

    .footer {{
      padding: 26px 6px 0;
      color: var(--muted);
      font-size: 0.92rem;
    }}

    @media (max-width: 1100px) {{
      .meta-grid {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}

      .summary-grid {{
        grid-template-columns: 1fr;
      }}
    }}

    @media (max-width: 760px) {{
      .page {{
        padding-inline: 14px;
      }}

      .hero {{
        padding: 22px;
        border-radius: 24px;
      }}

      .meta-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}

      .bar-row {{
        grid-template-columns: 1fr;
      }}

      .bar-row__label {{
        margin-bottom: -4px;
      }}

      .task-card {{
        margin: 16px;
      }}

      table,
      thead,
      tbody,
      th,
      td,
      tr {{
        display: block;
      }}

      thead {{
        position: absolute;
        left: -9999px;
      }}

      tr {{
        border-top: 1px solid var(--border);
      }}

      td {{
        border-top: none;
        padding: 10px 16px;
      }}

      td::before {{
        content: attr(data-label);
        display: block;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--muted);
        margin-bottom: 6px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="hero">
      <div class="eyebrow">agentic-token-bench</div>
      <h1>Token usage before and after</h1>
      <p>Compare baseline versus tool_variant on the same Cassandra tasks, then inspect how different agents behave on the exact same work.</p>
      <div class="meta-grid">
        {_render_metric_card("Agents", str(agent_count), "Agents with valid runs in this report", "blue")}
        {_render_metric_card("Families", str(family_count), "Tool families represented", "blue")}
        {_render_metric_card("Tasks", str(task_count), "Unique task ids across the data", "blue")}
        {_render_metric_card(
            "Valid runs",
            str(len(valid_runs)),
            f"{invalid_runs} invalid run(s) excluded from {total_runs} total",
            "amber",
        )}
        {_render_metric_card("Validation", overall_validation_text, "Pass rate across valid runs", "amber")}
        {_render_metric_card(
            "Reduction",
            _format_pct(overall_reduction),
            f"Delta: {_format_number(overall_delta, 0)} tokens",
            "amber",
        )}
      </div>
      {source_note}
      {overview_link}
    </header>

    <section class="summary-panel">
      <div class="section-heading">
        <div class="section-kicker">Overview</div>
        <h2>Before / after across all valid runs</h2>
        <p class="subtle">These totals are aggregated from the selected results directory. The baseline bars are blue; tool_variant bars are amber.</p>
      </div>
      <div class="summary-grid">
        <div class="comparison-stack">
          {overall_before}
          {overall_after}
        </div>
        <table>
          <thead>
            <tr>
              <th>Agent</th>
              <th>Before avg tokens</th>
              <th>After avg tokens</th>
              <th>Delta</th>
              <th>Reduction</th>
              <th>Validation</th>
              <th>Elapsed</th>
              <th>Runs</th>
            </tr>
          </thead>
          <tbody>
            {''.join(agent_rows) if agent_rows else '<tr><td colspan="8">No valid runs found.</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>

    <nav class="nav-strip" aria-label="Family navigation">
      {family_nav if family_nav else '<span class="subtle">No family data found.</span>'}
    </nav>

    <div class="table-panel">
      <div class="section-heading">
        <div class="section-kicker">Same tasks</div>
        <h2>Agent-to-agent comparisons on identical tasks</h2>
        <p class="subtle">Each task section shows the same task across every agent present in the data. If you add another agent’s runs, it will appear in the same rows without changing the report structure.</p>
      </div>
    </div>

    {family_sections if family_sections else '<div class="summary-panel"><p class="subtle">No family sections available.</p></div>'}

    <footer class="footer">
      Generated {escape(generated_at.isoformat())}. Valid runs only are included in comparisons, matching the benchmark scorecard rules.
    </footer>
  </div>
</body>
</html>
"""
