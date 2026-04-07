from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.persistence.models import PersistedRun
from app.schemas.results import NormalizedRunOutput, PageErrorReport, UniversityRunResult
from app.services.scrape_service import ScrapeExecution


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_id: str
    configs_package: str = "configs"
    configs_dir: str = "configs"
    headed: bool = False
    browser: Literal["chromium", "firefox", "webkit"] = "chromium"


class ConfigSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    university_name: str
    status: str


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    university_id: str
    university_name: str
    status: str
    result: UniversityRunResult

    @classmethod
    def from_execution(cls, execution: ScrapeExecution) -> "RunResponse":
        return cls(
            run_id=execution.persisted_run.run_id if execution.persisted_run else None,
            university_id=execution.result.university_id,
            university_name=execution.result.university_name,
            status=execution.result.status.value,
            result=execution.result,
        )


class PersistedRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    university_id: str
    university_name: str
    status: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    created_at: datetime
    logs: list[str] = Field(default_factory=list)
    normalized: NormalizedRunOutput | None = None
    errors: list[PageErrorReport] = Field(default_factory=list)

    @classmethod
    def from_persisted_run(cls, persisted_run: PersistedRun) -> "PersistedRunResponse":
        return cls(
            run_id=persisted_run.run_id,
            university_id=persisted_run.university_id,
            university_name=persisted_run.university_name,
            status=persisted_run.status,
            started_at=persisted_run.started_at,
            finished_at=persisted_run.finished_at,
            duration_ms=persisted_run.duration_ms,
            created_at=persisted_run.created_at,
            logs=persisted_run.logs,
            normalized=persisted_run.normalized,
            errors=persisted_run.errors,
        )
