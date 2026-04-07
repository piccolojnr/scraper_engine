from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.config.models import (
    EntityType,
    ExtractStrategy,
    FetchMode,
    PageType,
    ContentIntent,
    AudienceLevel,
)


# ============================================================
# ENUMS
# ============================================================


class RunStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class PageRunStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class EntityRunStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class ErrorCode(str, Enum):
    FETCH_FAILED = "fetch_failed"
    EMPTY_CONTENT = "empty_content"
    ACTION_FAILED = "action_failed"
    SELECTOR_NOT_FOUND = "selector_not_found"
    KEYWORD_NOT_MATCHED = "keyword_not_matched"
    PATTERN_NOT_MATCHED = "pattern_not_matched"
    TABLE_PARSE_FAILED = "table_parse_failed"
    LLM_EXTRACTION_FAILED = "llm_extraction_failed"
    RECORD_LOCATOR_FAILED = "record_locator_failed"
    ENTITY_EXTRACTION_FAILED = "entity_extraction_failed"
    EXTRACTION_FAILED = "extraction_failed"
    NORMALIZATION_FAILED = "normalization_failed"
    VALIDATION_FAILED = "validation_failed"
    ACCESS_DENIED = "access_denied"
    STRUCTURE_CHANGED = "structure_changed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# ============================================================
# FIELD-LEVEL EXTRACTION RESULTS
# ============================================================


class ExtractedFieldResult(BaseModel):
    """
    Result of one extraction step chain for one field.
    Example:
      - portal.title
      - portal.status
      - course.name
      - university.website_url
    """

    model_config = ConfigDict(extra="forbid")

    entity_type: EntityType
    field_name: str
    strategy: ExtractStrategy
    success: bool

    value: Any | None = None
    evidence: str | None = None
    selector_used: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    error_code: ErrorCode | None = None
    error_message: str | None = None


# ============================================================
# PAGE-LEVEL ERROR REPORT
# ============================================================


class PageErrorReport(BaseModel):
    """
    Structured page error for storage, logs, and debugging UI.
    """

    model_config = ConfigDict(extra="forbid")

    page_name: str
    page_type: PageType
    intent: ContentIntent
    audience: AudienceLevel
    url: HttpUrl
    fetch_mode: FetchMode

    error_code: ErrorCode
    message: str
    detail: str | None = None
    suggestion: str | None = None

    html_snapshot_path: str | None = None
    screenshot_path: str | None = None
    happened_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# ENTITY-LEVEL EXTRACTION RESULTS
# ============================================================


class EntityIdentity(BaseModel):
    """
    Minimal identity handle for one extracted record.
    Useful before DB persistence exists.
    """

    model_config = ConfigDict(extra="forbid")

    entity_type: EntityType
    source_page_name: str
    record_index: int = Field(default=0, ge=0)
    source_url: HttpUrl | None = None


class EntityErrorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: EntityType
    source_page_name: str
    record_index: int = Field(default=0, ge=0)

    error_code: ErrorCode
    message: str
    detail: str | None = None
    field_name: str | None = None


class EntityExtractionResult(BaseModel):
    """
    Raw extraction result for one entity record from one page.

    Example:
      - one portal card on an admissions page
      - one course row in a programmes table
      - one university profile block
    """

    model_config = ConfigDict(extra="forbid")

    identity: EntityIdentity
    status: EntityRunStatus

    field_results: list[ExtractedFieldResult] = Field(default_factory=list)

    raw_text_excerpt: str | None = None
    html_fragment: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    error: EntityErrorReport | None = None

    def field_result(self, name: str) -> ExtractedFieldResult:
        for field in self.field_results:
            if field.field_name == name:
                return field
        raise KeyError(
            f"Field result '{name}' not found for "
            f"{self.identity.entity_type}:{self.identity.source_page_name}:{self.identity.record_index}."
        )

    def output_map(self) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for field in self.field_results:
            if field.success:
                output[field.field_name] = field.value
        return output


# ============================================================
# PAGE-LEVEL EXTRACTION RESULT
# ============================================================


class PageExtractionResult(BaseModel):
    """
    Complete result for one configured page in one run.
    """

    model_config = ConfigDict(extra="forbid")

    page_name: str
    page_type: PageType
    intent: ContentIntent
    audience: AudienceLevel
    url: HttpUrl
    fetch_mode: FetchMode
    status: PageRunStatus

    started_at: datetime
    finished_at: datetime

    entities: list[EntityExtractionResult] = Field(default_factory=list)

    raw_text_excerpt: str | None = None
    html_snapshot_path: str | None = None
    screenshot_path: str | None = None

    error: PageErrorReport | None = None

    @property
    def success(self) -> bool:
        return self.status == PageRunStatus.SUCCESS

    @property
    def duration_ms(self) -> int:
        delta = self.finished_at - self.started_at
        return int(delta.total_seconds() * 1000)

    def entities_by_type(self, entity_type: EntityType) -> list[EntityExtractionResult]:
        return [entity for entity in self.entities if entity.identity.entity_type == entity_type]


# ============================================================
# NORMALIZED ENTITY RECORDS
# These are the structured entities you persist or upsert later.
# ============================================================


class BaseNormalizedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_urls: list[str] = Field(default_factory=list)
    source_page_names: list[str] = Field(default_factory=list)
    raw_snippets: list[str] = Field(default_factory=list)

    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    content_hash: str | None = None


class UniversityRecord(BaseNormalizedRecord):
    model_config = ConfigDict(extra="forbid")

    external_university_id: str | None = None

    name: str
    slug_candidate: str | None = None
    country: str

    state_province: str | None = None
    city: str | None = None
    type: str | None = None

    website_url: str | None = None
    logo_url: str | None = None
    description: str | None = None
    course_catalog_url: str | None = None
    fee_schedule_url: str | None = None

    is_active: bool = True


class PortalRecord(BaseNormalizedRecord):
    model_config = ConfigDict(extra="forbid")

    external_university_id: str | None = None
    university_name_hint: str | None = None

    title: str
    slug_candidate: str | None = None
    description: str | None = None
    portal_url: str | None = None

    degree_level: str | None = None
    academic_year: str | None = None

    opens_at: datetime | None = None
    closes_at: datetime | None = None
    next_opens_at: datetime | None = None

    status: str | None = None

    fee_amount: Decimal | None = None
    fee_currency: str | None = None
    intl_fee_amount: Decimal | None = None
    intl_fee_currency: str | None = None
    fee_note: str | None = None

    requirements: str | None = None
    instructions: str | None = None

    is_featured: bool | None = None
    is_premium: bool | None = None


class CourseRecord(BaseNormalizedRecord):
    model_config = ConfigDict(extra="forbid")

    external_university_id: str | None = None
    university_name_hint: str | None = None

    name: str
    slug_candidate: str | None = None

    faculty: str | None = None
    department: str | None = None

    degree_level: str | None = None
    mode: str | None = None

    duration_years: int | None = None

    tuition_fee: Decimal | None = None
    fee_currency: str | None = None
    fee_note: str | None = None

    description: str | None = None
    requirements: str | None = None
    cut_off_point: str | None = None

    is_active: bool = True


# ============================================================
# NORMALIZED RUN OUTPUT
# This replaces the old UniversitySnapshot.
# ============================================================


class NormalizedRunOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    university: UniversityRecord | None = None
    portals: list[PortalRecord] = Field(default_factory=list)
    courses: list[CourseRecord] = Field(default_factory=list)


# ============================================================
# UNIVERSITY-LEVEL RUN RESULT
# Top-level result returned by the runner for one config execution.
# ============================================================


class UniversityRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    university_id: str
    university_name: str
    status: RunStatus

    started_at: datetime
    finished_at: datetime

    page_results: list[PageExtractionResult] = Field(default_factory=list)
    normalized: NormalizedRunOutput | None = None
    errors: list[PageErrorReport] = Field(default_factory=list)

    @property
    def duration_ms(self) -> int:
        delta = self.finished_at - self.started_at
        return int(delta.total_seconds() * 1000)

    @property
    def successful_pages(self) -> list[PageExtractionResult]:
        return [page for page in self.page_results if page.status == PageRunStatus.SUCCESS]

    @property
    def failed_pages(self) -> list[PageExtractionResult]:
        return [page for page in self.page_results if page.status == PageRunStatus.FAILED]

    def page_result(self, name: str) -> PageExtractionResult:
        for page in self.page_results:
            if page.page_name == name:
                return page
        raise KeyError(f"Page result '{name}' not found for university '{self.university_id}'.")

    def entity_results(self, entity_type: EntityType) -> list[EntityExtractionResult]:
        output: list[EntityExtractionResult] = []
        for page in self.page_results:
            output.extend(page.entities_by_type(entity_type))
        return output