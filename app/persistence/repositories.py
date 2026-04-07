from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from uuid import uuid4

from app.persistence.db import SQLiteDatabase
from app.persistence.models import PersistedRun
from app.schemas.results import NormalizedRunOutput, PageErrorReport, UniversityRunResult


class RunRepository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def initialize(self) -> None:
        self.database.initialize()

    def save_run(
        self,
        *,
        result: UniversityRunResult,
        logs: list[str] | None = None,
    ) -> PersistedRun:
        run_id = str(uuid4())
        created_at = datetime.utcnow()
        normalized_payload = (
            result.normalized.model_dump(mode="json")
            if result.normalized is not None
            else None
        )
        errors_payload = [error.model_dump(mode="json") for error in result.errors]
        serialized_normalized = (
            json.dumps(normalized_payload, ensure_ascii=False)
            if normalized_payload is not None
            else None
        )
        serialized_errors = json.dumps(errors_payload, ensure_ascii=False)
        serialized_logs = json.dumps(logs or [], ensure_ascii=False)

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO scrape_runs (
                    id,
                    university_id,
                    university_name,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    created_at,
                    normalized_json,
                    errors_json,
                    logs_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    result.university_id,
                    result.university_name,
                    result.status.value,
                    result.started_at.isoformat(),
                    result.finished_at.isoformat(),
                    result.duration_ms,
                    created_at.isoformat(),
                    serialized_normalized,
                    serialized_errors,
                    serialized_logs,
                ),
            )

            connection.commit()

        return PersistedRun(
            run_id=run_id,
            university_id=result.university_id,
            university_name=result.university_name,
            status=result.status.value,
            started_at=result.started_at,
            finished_at=result.finished_at,
            duration_ms=result.duration_ms,
            created_at=created_at,
            normalized=result.normalized,
            errors=list(result.errors),
            logs=list(logs or []),
        )

    def get_run(self, run_id: str) -> PersistedRun | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    university_id,
                    university_name,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    created_at,
                    normalized_json,
                    errors_json,
                    logs_json
                FROM scrape_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_persisted_run(row)

    def get_latest_run(self, university_id: str) -> PersistedRun | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    university_id,
                    university_name,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    created_at,
                    normalized_json,
                    errors_json,
                    logs_json
                FROM scrape_runs
                WHERE university_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (university_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_persisted_run(row)

    def _row_to_persisted_run(self, row: sqlite3.Row) -> PersistedRun:
        normalized_payload = json.loads(row["normalized_json"]) if row["normalized_json"] else None
        errors_payload = json.loads(row["errors_json"]) if row["errors_json"] else []
        logs_payload = json.loads(row["logs_json"])
        return PersistedRun(
            run_id=row["id"],
            university_id=row["university_id"],
            university_name=row["university_name"],
            status=row["status"],
            started_at=datetime.fromisoformat(row["started_at"]),
            finished_at=datetime.fromisoformat(row["finished_at"]),
            duration_ms=row["duration_ms"],
            created_at=datetime.fromisoformat(row["created_at"]),
            normalized=(
                NormalizedRunOutput.model_validate(normalized_payload)
                if normalized_payload is not None
                else None
            ),
            errors=[
                PageErrorReport.model_validate(error_payload)
                for error_payload in errors_payload
            ],
            logs=list(logs_payload),
        )
