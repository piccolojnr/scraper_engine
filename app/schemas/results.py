
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.config.models import ExtractStrategy, FetchMode, PageCategory


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


class ErrorCode(str, Enum):
    FETCH_FAILED = "fetch_failed"
    EMPTY_CONTENT = "empty_content"
    ACTION_FAILED = "action_failed"
    SELECTOR_NOT_FOUND = "selector_not_found"
    KEYWORD_NOT_MATCHED = "keyword_not_matched"
    PATTERN_NOT_MATCHED = "pattern_not_matched"
    TABLE_PARSE_FAILED = "table_parse_failed"
    LLM_EXTRACTION_FAILED = "llm_extraction_failed"
    EXTRACTION_FAILED = "extraction_failed"
    NORMALIZATION_FAILED = "normalization_failed"
    ACCESS_DENIED = "access_denied"
    STRUCTURE_CHANGED = "structure_changed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# ============================================================
# FIELD-LEVEL EXTRACTION RESULTS
# ============================================================


class ExtractedFieldResult(BaseModel):
    """
    Result of one ExtractRule execution.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    output_field: str
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
    page_category: PageCategory
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
# PAGE-LEVEL EXTRACTION RESULT
# ============================================================


class PageExtractionResult(BaseModel):
    """
    Complete result for one configured page in one run.
    """

    model_config = ConfigDict(extra="forbid")

    page_name: str
    page_category: PageCategory
    url: HttpUrl
    fetch_mode: FetchMode
    status: PageRunStatus

    started_at: datetime
    finished_at: datetime

    extracted_fields: list[ExtractedFieldResult] = Field(default_factory=list)

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

    def field_result(self, name: str) -> ExtractedFieldResult:
        for field in self.extracted_fields:
            if field.name == name:
                return field
        raise KeyError(f"Field result '{name}' not found on page '{self.page_name}'.")

    def output_map(self) -> dict[str, Any]:
        """
        Flatten successful extracted values by output_field.

        If multiple rules target the same output_field, the last successful one wins.
        Normalizers can use this as a simple raw input map.
        """
        output: dict[str, Any] = {}

        for field in self.extracted_fields:
            if field.success:
                output[field.output_field] = field.value

        return output


# ============================================================
# NORMALIZED DOMAIN MODELS
# These are the structured entities you ultimately want to store.
# ============================================================


class DeadlineEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    admission_type: str
    opens: str | None = None
    closes: str | None = None
    opens_date: datetime | None = None
    closes_date: datetime | None = None


class TuitionFee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    programme: str
    student_type: str
    amount: str | None = None
    amount_numeric: float | None = None
    currency: str | None = None
    per: str = "semester"
    notes: str | None = None


class CutOffEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    programme: str
    college: str | None = None
    first_choice_cutoff: str | None = None
    fee_paying_cutoff: str | None = None
    second_choice_cutoff: str | None = None
    subject_requirements: str | None = None


class Programme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    degree_types: list[str] = Field(default_factory=list)
    level: str
    overview: str | None = None
    department_url: str | None = None
    duration: str | None = None
    study_modes: list[str] = Field(default_factory=list)
    accredited_by: str | None = None
    tuition_fees: list[TuitionFee] = Field(default_factory=list)


class FeeInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_application_fee: str | None = None
    international_application_fee: str | None = None
    local_tuition_note: str | None = None
    international_tuition_note: str | None = None
    payment_banks: list[str] = Field(default_factory=list)
    payment_account: str | None = None
    payment_swift: str | None = None
    ussd_code: str | None = None
    online_payment_url: str | None = None


class ApplyInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_url: str | None = None
    international_url: str | None = None
    general_url: str | None = None
    required_documents: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    entry_requirements_summary: str | None = None
    min_aggregate: str | None = None


class OngoingAdmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None
    status: str


class Scholarship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provider: str | None = None
    description: str | None = None
    coverage: str | None = None
    eligibility: list[str] = Field(default_factory=list)
    min_gpa: str | None = None
    target_level: str | None = None
    target_college: str | None = None
    deadline: str | None = None
    deadline_date: datetime | None = None
    apply_url: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    renewable: bool | None = None
    is_need_based: bool | None = None
    is_merit_based: bool | None = None


class AccreditationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str
    status: str
    since: str | None = None
    expires: str | None = None
    scope: str = "institutional"
    programme: str | None = None


class UniversityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    type: str | None = None
    founded: int | None = None
    location_city: str | None = None
    location_region: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None
    website: str | None = None
    financialaid_url: str | None = None
    scholarships_apply_url: str | None = None
    total_students: int | None = None
    international_students: int | None = None
    phone: str | None = None
    email: str | None = None
    po_box: str | None = None
    accreditations: list[AccreditationInfo] = Field(default_factory=list)
    rankings: dict[str, str] = Field(default_factory=dict)
    social_media: dict[str, str] = Field(default_factory=dict)


# ============================================================
# FINAL NORMALIZED SNAPSHOT
# This is the structured university-level result produced after
# page extraction + normalization.
# ============================================================


class UniversitySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    university_id: str
    university_name: str

    status: str | None = None
    cycle: str | None = None
    raw_snippet: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    open_date: datetime | None = None
    close_date: datetime | None = None

    ongoing_admissions: list[OngoingAdmission] = Field(default_factory=list)
    deadlines: list[DeadlineEntry] = Field(default_factory=list)

    programmes: list[Programme] = Field(default_factory=list)
    cut_off_points: list[CutOffEntry] = Field(default_factory=list)

    fees: FeeInfo | None = None
    tuition_fees: list[TuitionFee] = Field(default_factory=list)
    scholarships: list[Scholarship] = Field(default_factory=list)

    apply_info: ApplyInfo | None = None
    profile: UniversityProfile | None = None

    source_urls: list[str] = Field(default_factory=list)
    content_hash: str | None = None


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
    snapshot: UniversitySnapshot | None = None
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

    def page_output_map(self) -> dict[str, dict[str, Any]]:
        """
        Return raw extracted outputs grouped by page name.

        Example:
            {
                "main_portal": {"portal_status": "open", "portal_notice_text": "..."},
                "fees_page": {"fees_raw": [...]},
            }
        """
        return {
            page.page_name: page.output_map()
            for page in self.page_results
        }