"""Tests for the static HTML benchmark report."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from benchmarks.harness.cli import app
from benchmarks.harness.html_report import load_run_records, render_html_report
from benchmarks.harness.models import (
    RunRecord,
    RunStatus,
    RunValidity,
    ValidationStatus,
    Variant,
)


OFFICIAL_TASKS_DIR = (
    Path(__file__).resolve().parent.parent / "benchmarks" / "tasks" / "cassandra" / "official"
)


def _make_run(
    *,
    run_id: str,
    task_id: str,
    family: str,
    variant: Variant,
    agent_id: str,
    tokens: int | None,
    elapsed: float | None,
    validity: RunValidity = RunValidity.valid,
    validation_status: ValidationStatus = ValidationStatus.passed,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        task_id=task_id,
        family=family,
        variant=variant,
        agent_id=agent_id,
        adapter_version="1.0.0",
        repo_commit="0269fd5665751e8a6d8eab852e0f66c142b10ee6",
        status=RunStatus.passed,
        validity=validity,
        reported_total_tokens=tokens,
        elapsed_seconds=elapsed,
        repair_iterations=0,
        validation_status=validation_status,
    )


@pytest.fixture()
def sample_runs() -> list[RunRecord]:
    """Multi-agent, multi-task data for the HTML report."""
    runs: list[RunRecord] = []
    task_family = "ripgrep"
    tasks = ["cassandra-ripgrep-01", "cassandra-ripgrep-02"]
    agents = ["claude", "codex"]
    token_map = {
        ("claude", "cassandra-ripgrep-01", Variant.baseline): [100, 110],
        ("claude", "cassandra-ripgrep-01", Variant.tool_variant): [60, 70],
        ("codex", "cassandra-ripgrep-01", Variant.baseline): [120, 130],
        ("codex", "cassandra-ripgrep-01", Variant.tool_variant): [80, 90],
        ("claude", "cassandra-ripgrep-02", Variant.baseline): [200, 210],
        ("claude", "cassandra-ripgrep-02", Variant.tool_variant): [140, 150],
        ("codex", "cassandra-ripgrep-02", Variant.baseline): [220, 230],
        ("codex", "cassandra-ripgrep-02", Variant.tool_variant): [150, 160],
    }
    elapsed_map = {
        Variant.baseline: 30.0,
        Variant.tool_variant: 18.0,
    }

    idx = 0
    for task_id in tasks:
        for agent in agents:
            for variant in (Variant.baseline, Variant.tool_variant):
                for token_value in token_map[(agent, task_id, variant)]:
                    idx += 1
                    runs.append(
                        _make_run(
                            run_id=f"{task_id}-{agent}-{variant.value}-{idx}",
                            task_id=task_id,
                            family=task_family,
                            variant=variant,
                            agent_id=agent,
                            tokens=token_value,
                            elapsed=elapsed_map[variant],
                        )
                    )

    runs.append(
        _make_run(
            run_id="cassandra-ripgrep-01-claude-invalid",
            task_id="cassandra-ripgrep-01",
            family=task_family,
            variant=Variant.baseline,
            agent_id="claude",
            tokens=999999,
            elapsed=30.0,
            validity=RunValidity.invalid,
        )
    )
    return runs


def _write_runs(results_dir: Path, runs: list[RunRecord]) -> None:
    for run in runs:
        artifact_dir = results_dir / run.run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "run.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")


class TestRenderHtmlReport:
    def test_includes_before_after_and_agent_comparisons(self, sample_runs: list[RunRecord]) -> None:
        html = render_html_report(sample_runs, tasks_dir=OFFICIAL_TASKS_DIR)

        assert "<!doctype html>" in html
        assert "Token usage before and after" in html
        assert "claude" in html
        assert "codex" in html
        assert "cassandra-ripgrep-01" in html
        assert "cassandra-ripgrep-02" in html
        assert "Locate the implementation and config path for read repair behavior" in html
        assert "Agent-to-agent comparisons on identical tasks" in html
        assert "Before avg tokens" in html
        assert "After avg tokens" in html
        assert "Benchmark walkthrough" in html

    def test_excludes_invalid_runs_from_comparisons(self, sample_runs: list[RunRecord]) -> None:
        html = render_html_report(sample_runs, tasks_dir=OFFICIAL_TASKS_DIR)

        assert "999,999" not in html
        assert "Valid runs" in html
        assert "1 invalid run(s) excluded from 17 total" in html

    def test_overall_agent_averages_are_present(self, sample_runs: list[RunRecord]) -> None:
        html = render_html_report(sample_runs, tasks_dir=OFFICIAL_TASKS_DIR)

        # Claudes averages: baseline (100+110+200+210)/4 = 155, tool (60+70+140+150)/4 = 105
        assert "155" in html
        assert "105" in html

    def test_handles_zero_token_baseline_without_crashing(self) -> None:
        runs = [
            _make_run(
                run_id="zero-baseline",
                task_id="cassandra-ripgrep-01",
                family="ripgrep",
                variant=Variant.baseline,
                agent_id="claude",
                tokens=0,
                elapsed=12.0,
            ),
            _make_run(
                run_id="zero-tool",
                task_id="cassandra-ripgrep-01",
                family="ripgrep",
                variant=Variant.tool_variant,
                agent_id="claude",
                tokens=24,
                elapsed=9.0,
            ),
        ]

        html = render_html_report(runs, tasks_dir=OFFICIAL_TASKS_DIR)

        assert "0" in html
        assert "24" in html
        assert "N/A" in html


class TestHtmlReportCli:
    def test_generate_html_report_command_writes_file(
        self, tmp_path: Path, sample_runs: list[RunRecord]
    ) -> None:
        results_dir = tmp_path / "results"
        _write_runs(results_dir, sample_runs)

        output_path = tmp_path / "report.html"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "generate-html-report",
                str(results_dir),
                "--tasks-dir",
                str(OFFICIAL_TASKS_DIR),
                "--output-path",
                str(output_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert output_path.exists()

        html = output_path.read_text(encoding="utf-8")
        assert "agentic-token-bench" in html
        assert "Token usage before and after" in html
        assert "cassandra-ripgrep-01" in html

    def test_load_run_records_reads_written_json(self, tmp_path: Path, sample_runs: list[RunRecord]) -> None:
        results_dir = tmp_path / "results"
        _write_runs(results_dir, sample_runs)

        loaded = load_run_records(results_dir)
        assert len(loaded) == len(sample_runs)
        assert {run.agent_id for run in loaded} == {"claude", "codex"}
