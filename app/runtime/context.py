from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from pydantic import HttpUrl

from app.config.models import PageConfig, UniversityScraperConfig, EntityType
from app.schemas.results import (
    EntityErrorReport,
    EntityExtractionResult,
    EntityIdentity,
    EntityRunStatus,
    ErrorCode,
    ExtractedFieldResult,
    NormalizedRunOutput,
    PageErrorReport,
    PageExtractionResult,
    PageRunStatus,
    UniversityRunResult,
)


@dataclass(slots=True)
class RuntimeArtifact:
    kind: str
    path: str
    description: str | None = None


@dataclass(slots=True)
class FieldEvidence:
    selector_used: str | None = None
    evidence: str | None = None
    confidence: float | None = None


@dataclass(slots=True)
class EntityDraft:
    """
    Mutable in-progress entity being built during page extraction.
    This exists only during extraction, before being frozen into EntityExtractionResult.
    """

    entity_type: EntityType
    source_page_name: str
    record_index: int = 0
    source_url: HttpUrl | None = None

    field_results: list[ExtractedFieldResult] = field(default_factory=list)
    raw_text_excerpt: str | None = None
    html_fragment: str | None = None
    error: EntityErrorReport | None = None

    def add_field_result(
        self,
        *,
        field_name: str,
        strategy: Any,
        success: bool,
        value: Any = None,
        evidence: str | None = None,
        selector_used: str | None = None,
        confidence: float | None = None,
        error_code: ErrorCode | None = None,
        error_message: str | None = None,
    ) -> ExtractedFieldResult:
        result = ExtractedFieldResult(
            entity_type=self.entity_type,
            field_name=field_name,
            strategy=strategy,
            success=success,
            value=value,
            evidence=evidence,
            selector_used=selector_used,
            confidence=confidence,
            error_code=error_code,
            error_message=error_message,
        )
        self.field_results.append(result)
        return result

    def set_error(
        self,
        *,
        error_code: ErrorCode,
        message: str,
        detail: str | None = None,
        field_name: str | None = None,
    ) -> EntityErrorReport:
        self.error = EntityErrorReport(
            entity_type=self.entity_type,
            source_page_name=self.source_page_name,
            record_index=self.record_index,
            error_code=error_code,
            message=message,
            detail=detail,
            field_name=field_name,
        )
        return self.error

    def output_map(self) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for field in self.field_results:
            if field.success:
                output[field.field_name] = field.value
        return output

    def to_result(self, status: EntityRunStatus) -> EntityExtractionResult:
        scores = [f.confidence for f in self.field_results if f.confidence is not None]
        confidence = sum(scores) / len(scores) if scores else None

        return EntityExtractionResult(
            identity=EntityIdentity(
                entity_type=self.entity_type,
                source_page_name=self.source_page_name,
                record_index=self.record_index,
                source_url=self.source_url,
            ),
            status=status,
            field_results=self.field_results,
            raw_text_excerpt=self.raw_text_excerpt,
            html_fragment=self.html_fragment,
            confidence=confidence,
            error=self.error,
        )


@dataclass(slots=True)
class PageRuntimeContext:
    """
    Mutable runtime state for one page execution.
    """

    university: UniversityScraperConfig
    page: PageConfig
    started_at: datetime = field(default_factory=datetime.utcnow)

    current_url: HttpUrl | None = None
    html: str | None = None
    text_content: str | None = None

    browser: Any | None = None
    browser_context: Any | None = None
    browser_page: Any | None = None

    entities: list[EntityExtractionResult] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)

    logs: list[str] = field(default_factory=list)
    artifacts: list[RuntimeArtifact] = field(default_factory=list)
    error: PageErrorReport | None = None

    raw_text_excerpt: str | None = None

    def log(self, message: str) -> None:
        timestamp = datetime.utcnow().isoformat()
        self.logs.append(f"[{timestamp}] {message}")

    def set_html(self, html: str | None) -> None:
        self.html = html
        if html is not None:
            self.log(f"HTML captured for page '{self.page.name}'.")

    def set_text_content(self, text: str | None) -> None:
        self.text_content = text
        if text:
            cleaned = text.strip()
            self.raw_text_excerpt = cleaned[:1000] if cleaned else None
            self.log(f"Text content captured for page '{self.page.name}'.")

    def set_current_url(self, url: HttpUrl) -> None:
        self.current_url = url
        self.log(f"Current URL set to {url}")

    def set_variable(self, key: str, value: Any) -> None:
        self.variables[key] = value
        self.log(f"Variable '{key}' updated.")

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def add_artifact(self, kind: str, path: str, description: str | None = None) -> None:
        self.artifacts.append(RuntimeArtifact(kind=kind, path=path, description=description))
        self.log(f"Artifact added: kind={kind}, path={path}")

    def artifact_path(self, kind: str) -> str | None:
        for artifact in self.artifacts:
            if artifact.kind == kind:
                return artifact.path
        return None

    def create_entity_draft(
        self,
        *,
        entity_type: EntityType,
        record_index: int = 0,
        source_url: HttpUrl | None = None,
    ) -> EntityDraft:
        self.log(
            f"Created entity draft type={entity_type} "
            f"record_index={record_index} page={self.page.name}"
        )
        return EntityDraft(
            entity_type=entity_type,
            source_page_name=self.page.name,
            record_index=record_index,
            source_url=source_url or self.current_url,
        )

    def add_entity_result(self, entity: EntityExtractionResult) -> None:
        self.entities.append(entity)
        self.log(
            f"Entity result added type={entity.identity.entity_type} "
            f"record_index={entity.identity.record_index}"
        )

    def set_error(
        self,
        *,
        error_code: ErrorCode,
        message: str,
        detail: str | None = None,
        suggestion: str | None = None,
    ) -> PageErrorReport:
        report = PageErrorReport(
            page_name=self.page.name,
            page_type=self.page.type,
            intent=self.page.intent,
            audience=self.page.audience,
            url=self.page.url or (self.current_url or cast(HttpUrl, "http://invalid.local")),
            fetch_mode=self.page.fetch.mode,
            error_code=error_code,
            message=message,
            detail=detail,
            suggestion=suggestion,
            html_snapshot_path=self.artifact_path("html"),
            screenshot_path=self.artifact_path("screenshot"),
        )
        self.error = report
        self.log(f"Page error set: {error_code} - {message}")
        return report

    def to_page_result(self, status: PageRunStatus) -> PageExtractionResult:
        finished_at = datetime.utcnow()

        return PageExtractionResult(
            page_name=self.page.name,
            page_type=self.page.type,
            intent=self.page.intent,
            audience=self.page.audience,
            url=self.page.url or (self.current_url or cast(HttpUrl, "http://invalid.local")),
            fetch_mode=self.page.fetch.mode,
            status=status,
            started_at=self.started_at,
            finished_at=finished_at,
            entities=self.entities,
            raw_text_excerpt=self.raw_text_excerpt,
            html_snapshot_path=self.artifact_path("html"),
            screenshot_path=self.artifact_path("screenshot"),
            error=self.error,
        )


@dataclass(slots=True)
class UniversityRuntimeContext:
    """
    Mutable runtime state for one full university scrape run.
    """

    university: UniversityScraperConfig
    started_at: datetime = field(default_factory=datetime.utcnow)

    page_contexts: list[PageRuntimeContext] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)

    normalized: NormalizedRunOutput | None = None
    run_result: UniversityRunResult | None = None

    def log(self, message: str) -> None:
        timestamp = datetime.utcnow().isoformat()
        self.logs.append(f"[{timestamp}] {message}")

    def create_page_context(self, page: PageConfig) -> PageRuntimeContext:
        ctx = PageRuntimeContext(university=self.university, page=page)
        self.page_contexts.append(ctx)
        self.log(f"Created page context for '{page.name}'.")
        return ctx

    def set_normalized(self, normalized: NormalizedRunOutput) -> None:
        self.normalized = normalized
        self.log("Normalized run output updated.")

    def set_run_result(self, result: UniversityRunResult) -> None:
        self.run_result = result
        self.log("Run result updated.")

    def get_page_context(self, page_name: str) -> PageRuntimeContext:
        for ctx in self.page_contexts:
            if ctx.page.name == page_name:
                return ctx
        raise KeyError(f"Page context '{page_name}' not found.")