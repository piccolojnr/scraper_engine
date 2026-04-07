from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS scrape_runs (
        id TEXT PRIMARY KEY,
        university_id TEXT NOT NULL,
        university_name TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT NOT NULL,
        duration_ms INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        normalized_json TEXT,
        result_json TEXT NOT NULL,
        logs_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS page_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        page_name TEXT NOT NULL,
        page_type TEXT NOT NULL,
        intent TEXT NOT NULL,
        audience TEXT NOT NULL,
        url TEXT NOT NULL,
        fetch_mode TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT NOT NULL,
        result_json TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES scrape_runs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entity_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        page_name TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        record_index INTEGER NOT NULL,
        status TEXT NOT NULL,
        result_json TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES scrape_runs(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_scrape_runs_university_created ON scrape_runs (university_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_page_results_run_id ON page_results (run_id)",
    "CREATE INDEX IF NOT EXISTS idx_entity_results_run_id ON entity_results (run_id)",
)


class SQLiteDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            connection.commit()
