from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.schemas.results import UniversityRunResult


@dataclass(slots=True, frozen=True)
class PersistedRun:
    run_id: str
    university_id: str
    university_name: str
    status: str
    created_at: datetime
    result: UniversityRunResult
    logs: list[str]
