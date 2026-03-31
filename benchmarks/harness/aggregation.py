"""benchmarks.harness.aggregation — DuckDB-backed result aggregation for benchmark runs."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from benchmarks.harness.models import RunRecord


def load_runs_to_duckdb(
    runs: list[RunRecord] | None = None,
    results_dir: Path | None = None,
) -> duckdb.DuckDBPyConnection:
    """Load RunRecord data into an in-memory DuckDB database.

    Provide either a list of RunRecord objects or a directory path to scan for
    run.json files. If both are provided, both sources are loaded.

    Returns an open DuckDB connection with a ``runs`` table populated.
    """
    if runs is None and results_dir is None:
        raise ValueError("Either runs or results_dir must be provided.")

    all_records: list[RunRecord] = list(runs) if runs else []

    if results_dir is not None:
        results_dir = Path(results_dir)
        for json_path in results_dir.rglob("run.json"):
            try:
                data = json.loads(json_path.read_text())
                all_records.append(RunRecord.model_validate(data))
            except Exception:
                # Skip files that do not parse as valid RunRecords
                continue

    conn = duckdb.connect(":memory:")

    conn.execute("""
        CREATE TABLE runs (
            run_id VARCHAR,
            task_id VARCHAR,
            family VARCHAR,
            variant VARCHAR,
            agent_id VARCHAR,
            adapter_version VARCHAR,
            repo_commit VARCHAR,
            status VARCHAR,
            validity VARCHAR,
            reported_input_tokens INTEGER,
            reported_output_tokens INTEGER,
            reported_total_tokens INTEGER,
            elapsed_seconds DOUBLE,
            repair_iterations INTEGER,
            validation_status VARCHAR,
            files_changed INTEGER,
            diff_size INTEGER,
            artifact_dir VARCHAR,
            started_at VARCHAR,
            finished_at VARCHAR
        )
    """)

    if all_records:
        rows = [
            (
                r.run_id,
                r.task_id,
                r.family,
                r.variant.value,
                r.agent_id,
                r.adapter_version,
                r.repo_commit,
                r.status.value,
                r.validity.value,
                r.reported_input_tokens,
                r.reported_output_tokens,
                r.reported_total_tokens,
                r.elapsed_seconds,
                r.repair_iterations,
                r.validation_status.value,
                r.files_changed,
                r.diff_size,
                r.artifact_dir,
                r.started_at.isoformat() if r.started_at is not None else None,
                r.finished_at.isoformat() if r.finished_at is not None else None,
            )
            for r in all_records
        ]
        conn.executemany("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)

    return conn


def query_runs(
    conn: duckdb.DuckDBPyConnection,
    family: str | None = None,
    agent: str | None = None,
    variant: str | None = None,
    valid_only: bool = True,
) -> list[dict]:
    """Query the runs table with optional filters.

    Parameters
    ----------
    conn:
        An open DuckDB connection returned by :func:`load_runs_to_duckdb`.
    family:
        Optional family name to filter on.
    agent:
        Optional agent_id to filter on.
    variant:
        Optional variant value (``"baseline"`` or ``"tool_variant"``) to filter on.
    valid_only:
        When ``True`` (default) only rows with ``validity = 'valid'`` are returned.

    Returns
    -------
    list[dict]
        Each dict represents one row with column names as keys.
    """
    conditions: list[str] = []
    if valid_only:
        conditions.append("validity = 'valid'")
    if family is not None:
        conditions.append(f"family = '{family}'")
    if agent is not None:
        conditions.append(f"agent_id = '{agent}'")
    if variant is not None:
        conditions.append(f"variant = '{variant}'")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM runs {where_clause}"

    result = conn.execute(sql).fetchall()
    columns = [desc[0] for desc in conn.execute(sql).description]  # type: ignore[union-attr]
    return [dict(zip(columns, row)) for row in result]


def compute_family_summary(conn: duckdb.DuckDBPyConnection, family: str) -> dict:
    """Compute per-variant averages and token delta/reduction for a family.

    Only valid runs (``validity = 'valid'``) are included in the averages.

    Returns a dict with the following keys:

    * ``family`` – the family name
    * ``baseline`` – sub-dict with ``run_count``, ``avg_tokens``,
      ``avg_elapsed_seconds``, ``avg_repair_iterations``, ``pass_rate``
    * ``tool_variant`` – same structure as ``baseline``
    * ``token_delta`` – ``tool_variant.avg_tokens - baseline.avg_tokens``
      (``None`` when either side has no token data)
    * ``token_reduction_pct`` – ``token_delta / baseline.avg_tokens * 100``
      (``None`` when ``token_delta`` is ``None``)
    """
    sql = """
        SELECT
            variant,
            COUNT(*) AS run_count,
            AVG(reported_total_tokens) AS avg_tokens,
            AVG(elapsed_seconds) AS avg_elapsed_seconds,
            AVG(repair_iterations) AS avg_repair_iterations,
            AVG(CASE WHEN validation_status = 'passed' THEN 1.0 ELSE 0.0 END) AS pass_rate
        FROM runs
        WHERE validity = 'valid'
          AND family = ?
        GROUP BY variant
    """
    rows = conn.execute(sql, [family]).fetchall()
    columns = [desc[0] for desc in conn.execute(sql, [family]).description]  # type: ignore[union-attr]

    variant_data: dict[str, dict] = {}
    for row in rows:
        row_dict = dict(zip(columns, row))
        variant_data[row_dict["variant"]] = row_dict

    def _variant_summary(name: str) -> dict:
        data = variant_data.get(name, {})
        return {
            "run_count": int(data.get("run_count", 0)),
            "avg_tokens": data.get("avg_tokens"),
            "avg_elapsed_seconds": data.get("avg_elapsed_seconds"),
            "avg_repair_iterations": data.get("avg_repair_iterations"),
            "pass_rate": data.get("pass_rate"),
        }

    baseline = _variant_summary("baseline")
    tool_variant = _variant_summary("tool_variant")

    token_delta: float | None = None
    token_reduction_pct: float | None = None
    if baseline["avg_tokens"] is not None and tool_variant["avg_tokens"] is not None:
        token_delta = tool_variant["avg_tokens"] - baseline["avg_tokens"]
        token_reduction_pct = token_delta / baseline["avg_tokens"] * 100

    return {
        "family": family,
        "baseline": baseline,
        "tool_variant": tool_variant,
        "token_delta": token_delta,
        "token_reduction_pct": token_reduction_pct,
    }


def export_csv(
    conn: duckdb.DuckDBPyConnection,
    output_path: Path,
    query: str | None = None,
) -> Path:
    """Export query results (or the full ``runs`` table) to a CSV file.

    Parameters
    ----------
    conn:
        An open DuckDB connection returned by :func:`load_runs_to_duckdb`.
    output_path:
        Destination path for the CSV file.
    query:
        Optional SQL query whose results are exported. When ``None`` the full
        ``runs`` table is exported.

    Returns
    -------
    Path
        The resolved path of the written CSV file.
    """
    output_path = Path(output_path)
    sql = query if query is not None else "SELECT * FROM runs"

    # DuckDB COPY … TO … writes the CSV directly from within the engine.
    conn.execute(f"COPY ({sql}) TO '{output_path}' (HEADER, DELIMITER ',')")
    return output_path.resolve()
