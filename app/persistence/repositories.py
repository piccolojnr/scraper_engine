from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.persistence.db import SQLiteDatabase
from app.persistence.models import PersistedRun
from app.schemas.results import UniversityRunResult


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
        result_payload = result.model_dump(mode="json")
        normalized_payload = result_payload.get("normalized")
        serialized_result = json.dumps(result_payload, ensure_ascii=False)
        serialized_normalized = (
            json.dumps(normalized_payload, ensure_ascii=False)
            if normalized_payload is not None
            else None
        )
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
                    result_json,
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
                    serialized_result,
                    serialized_logs,
                ),
            )

            for page_result in result.page_results:
                connection.execute(
                    """
                    INSERT INTO page_results (
                        run_id,
                        page_name,
                        page_type,
                        intent,
                        audience,
                        url,
                        fetch_mode,
                        status,
                        started_at,
                        finished_at,
                        result_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        page_result.page_name,
                        page_result.page_type.value,
                        page_result.intent.value,
                        page_result.audience.value,
                        str(page_result.url),
                        page_result.fetch_mode.value,
                        page_result.status.value,
                        page_result.started_at.isoformat(),
                        page_result.finished_at.isoformat(),
                        json.dumps(page_result.model_dump(mode="json"), ensure_ascii=False),
                    ),
                )

                for entity_result in page_result.entities:
                    connection.execute(
                        """
                        INSERT INTO entity_results (
                            run_id,
                            page_name,
                            entity_type,
                            record_index,
                            status,
                            result_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            page_result.page_name,
                            entity_result.identity.entity_type.value,
                            entity_result.identity.record_index,
                            entity_result.status.value,
                            json.dumps(entity_result.model_dump(mode="json"), ensure_ascii=False),
                        ),
                    )

            connection.commit()

        return PersistedRun(
            run_id=run_id,
            university_id=result.university_id,
            university_name=result.university_name,
            status=result.status.value,
            created_at=created_at,
            result=result,
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
                    created_at,
                    result_json,
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
                    created_at,
                    result_json,
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

    def _row_to_persisted_run(self, row: Any) -> PersistedRun:
        result_payload = json.loads(row["result_json"])
        logs_payload = json.loads(row["logs_json"])
        return PersistedRun(
            run_id=row["id"],
            university_id=row["university_id"],
            university_name=row["university_name"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            result=UniversityRunResult.model_validate(result_payload),
            logs=list(logs_payload),
        )
