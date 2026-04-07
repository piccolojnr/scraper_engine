from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config.models import (
    AudienceLevel,
    ContentIntent,
    EntityType,
    ExtractStrategy,
    FetchMode,
    PageType,
)
from app.persistence.db import SQLiteDatabase
from app.persistence.repositories import RunRepository
from app.schemas.results import (
    EntityExtractionResult,
    EntityIdentity,
    EntityRunStatus,
    ExtractedFieldResult,
    NormalizedRunOutput,
    PageExtractionResult,
    PageRunStatus,
    RunStatus,
    UniversityRecord,
    UniversityRunResult,
)


def build_result(*, finished_at: datetime) -> UniversityRunResult:
    started_at = finished_at - timedelta(seconds=5)
    entity = EntityExtractionResult(
        identity=EntityIdentity(
            entity_type=EntityType.UNIVERSITY,
            source_page_name="profile",
            record_index=0,
            source_url="https://example.edu/profile",
        ),
        status=EntityRunStatus.SUCCESS,
        field_results=[
            ExtractedFieldResult(
                entity_type=EntityType.UNIVERSITY,
                field_name="name",
                strategy=ExtractStrategy.SELECTOR,
                success=True,
                value="Example University",
                confidence=0.9,
            )
        ],
        confidence=0.9,
    )
    page = PageExtractionResult(
        page_name="profile",
        page_type=PageType.CONTENT,
        intent=ContentIntent.PROFILE,
        audience=AudienceLevel.GENERAL,
        url="https://example.edu/profile",
        fetch_mode=FetchMode.HTTP,
        status=PageRunStatus.SUCCESS,
        started_at=started_at,
        finished_at=finished_at,
        entities=[entity],
    )
    return UniversityRunResult(
        university_id="example",
        university_name="Example University",
        status=RunStatus.SUCCESS,
        started_at=started_at,
        finished_at=finished_at,
        page_results=[page],
        normalized=NormalizedRunOutput(
            university=UniversityRecord(
                name="Example University",
                country="Nigeria",
            )
        ),
    )


def test_save_and_get_run(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "runs.sqlite3")
    repository = RunRepository(database)
    repository.initialize()

    result = build_result(finished_at=datetime(2026, 4, 7, 16, 0, tzinfo=UTC))
    saved = repository.save_run(result=result, logs=["started", "finished"])

    fetched = repository.get_run(saved.run_id)

    assert fetched is not None
    assert fetched.run_id == saved.run_id
    assert fetched.university_id == "example"
    assert fetched.normalized is not None
    assert fetched.normalized.university is not None
    assert fetched.normalized.university.name == "Example University"
    assert fetched.logs == ["started", "finished"]


def test_get_latest_run_returns_most_recent(tmp_path) -> None:
    database = SQLiteDatabase(tmp_path / "runs.sqlite3")
    repository = RunRepository(database)
    repository.initialize()

    repository.save_run(
        result=build_result(finished_at=datetime(2026, 4, 7, 16, 0, tzinfo=UTC))
    )
    latest_result = build_result(finished_at=datetime(2026, 4, 7, 17, 0, tzinfo=UTC))
    latest_saved = repository.save_run(result=latest_result)

    fetched = repository.get_latest_run("example")

    assert fetched is not None
    assert fetched.run_id == latest_saved.run_id
    assert fetched.finished_at == latest_result.finished_at
