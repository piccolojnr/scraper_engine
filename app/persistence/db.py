from __future__ import annotations

import sqlite3
from pathlib import Path


CURRENT_SCHEMA_VERSION = 2

RUN_TABLE_SCHEMA = """
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
        errors_json TEXT NOT NULL DEFAULT '[]',
        logs_json TEXT NOT NULL DEFAULT '[]'
    )
"""

RUN_TABLE_COLUMNS = {
    "id": "TEXT",
    "university_id": "TEXT NOT NULL",
    "university_name": "TEXT NOT NULL",
    "status": "TEXT NOT NULL",
    "started_at": "TEXT NOT NULL",
    "finished_at": "TEXT NOT NULL",
    "duration_ms": "INTEGER NOT NULL",
    "created_at": "TEXT NOT NULL",
    "normalized_json": "TEXT",
    "errors_json": "TEXT NOT NULL DEFAULT '[]'",
    "logs_json": "TEXT NOT NULL DEFAULT '[]'",
}

SCHEMA_STATEMENTS = (
    RUN_TABLE_SCHEMA,
    "CREATE INDEX IF NOT EXISTS idx_scrape_runs_university_created ON scrape_runs (university_id, created_at DESC)",
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
            self._migrate(connection)
            connection.commit()

    def _migrate(self, connection: sqlite3.Connection) -> None:
        current_version = self._schema_version(connection)

        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)

        if current_version < 2:
            self._ensure_run_columns(connection)

        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

    def _schema_version(self, connection: sqlite3.Connection) -> int:
        row = connection.execute("PRAGMA user_version").fetchone()
        if row is None:
            return 0
        return int(row[0])

    def _ensure_run_columns(self, connection: sqlite3.Connection) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(scrape_runs)")
        }
        for column_name, column_type in RUN_TABLE_COLUMNS.items():
            if column_name in existing_columns:
                continue
            connection.execute(
                f"ALTER TABLE scrape_runs ADD COLUMN {column_name} {column_type}"
            )
