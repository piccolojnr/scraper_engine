from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.schemas.results import NormalizedRunOutput, PageErrorReport


@dataclass(slots=True, frozen=True)
class PersistedRun:
    run_id: str
    university_id: str
    university_name: str
    status: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    created_at: datetime
    normalized: NormalizedRunOutput | None
    errors: list[PageErrorReport]
    logs: list[str]
