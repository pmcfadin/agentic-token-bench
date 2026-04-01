"""Tests for the standalone benchmark overview page."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from benchmarks.harness.benchmark_overview import render_benchmark_overview_html
from benchmarks.harness.cli import app


class TestBenchmarkOverview:
    def test_render_benchmark_overview_includes_walkthrough_and_token_model(self) -> None:
        html = render_benchmark_overview_html()

        assert "<!doctype html>" in html
        assert "What the benchmark does" in html
        assert "How one official run is executed" in html
        assert "Load the task manifest" in html
        assert "baseline removes the tool under test" in html
        assert "reported_total_tokens" in html
        assert "Search and reading" in html
        assert "Why do some runs use far more tokens than others?" in html
        assert "Open results report" in html
        assert "Read reproduction docs" in html

    def test_generate_benchmark_overview_command_writes_file(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "results"
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "generate-benchmark-overview",
                str(results_dir),
            ],
        )

        assert result.exit_code == 0, result.output
        output_path = results_dir / "benchmark-overview.html"
        assert output_path.exists()

        html = output_path.read_text(encoding="utf-8")
        assert "What the benchmark does" in html
        assert "Open results report" in html
