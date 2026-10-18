from __future__ import annotations

import sqlite3
from pathlib import Path

from app.models.contracts import AgentRun, FinancialFact


def _connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE IF NOT EXISTS financial_facts (fact_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, report_period TEXT NOT NULL, metric_code TEXT NOT NULL, payload TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS analysis_runs (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    return connection


def persist_run(path: Path, run: AgentRun, facts: list[FinancialFact]) -> None:
    connection = _connection(path)
    try:
        connection.execute("INSERT OR REPLACE INTO analysis_runs(run_id, payload) VALUES (?, ?)", (run.run_id, run.model_dump_json()))
        connection.executemany("INSERT OR REPLACE INTO financial_facts(fact_id, run_id, report_period, metric_code, payload) VALUES (?, ?, ?, ?, ?)", [(fact.fact_id, run.run_id, fact.report_period, fact.metric_code, fact.model_dump_json()) for fact in facts])
        connection.commit()
    finally:
        connection.close()

