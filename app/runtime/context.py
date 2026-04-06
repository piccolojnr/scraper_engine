
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.config.models import PageConfig, UniversityConfig
from app.schemas.results import (
    ErrorCode,
    ExtractedFieldResult,
    PageErrorReport,
    PageExtractionResult,
    PageRunStatus,
)


@dataclass(slots=True)
class RuntimeArtifact:
    """
    A file or debug artifact produced during execution.

    Examples:
      - saved HTML snapshot
      - screenshot
      - downloaded PDF
      - extracted text dump
    """
    kind: str
    path: str
    description: str | None = None


@dataclass(slots=True)
class FieldEvidence:
    """
    Optional evidence captured while extracting a field.
    """
    selector_used: str | None = None
    evidence: str | None = None
    confidence: float | None = None


@dataclass(slots=True)
class PageRuntimeContext:
    """
    Mutable runtime state for one page execution.

    This exists only while a single page is being processed.
    The runner populates it, action handlers mutate it, extractors read/write it,
    and finally it is converted into a PageExtractionResult.
    """

    university: UniversityConfig
    page: PageConfig
    started_at: datetime = field(default_factory=datetime.utcnow)

    # Fetch/runtime outputs
    current_url: str | None = None
    html: str | None = None
    text_content: str | None = None

    # Browser-specific handles.
    # Keep these as Any here so context.py does not hard-depend on Playwright types.
    browser: Any | None = None 
    """Browser instance, if using browser-based fetching."""
    browser_context: Any | None = None
    """Browser context (e.g. incognito), if using browser-based fetching."""
    browser_page: Any | None = None
    """Browser page/tab, if using browser-based fetching."""

    # Extraction/runtime data
    extracted_fields: list[ExtractedFieldResult] = field(default_factory=list)
    raw_outputs: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)

    # Diagnostics
    logs: list[str] = field(default_factory=list)
    artifacts: list[RuntimeArtifact] = field(default_factory=list)
    error: PageErrorReport | None = None

    # Optional short excerpt for debug/result reporting
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

    def set_current_url(self, url: str) -> None:
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

    def add_field_result(
        self,
        *,
        name: str,
        output_field: str,
        strategy: Any,
        success: bool,
        value: Any = None,
        evidence: str | None = None,
        selector_used: str | None = None,
        confidence: float | None = None,
        error_code: ErrorCode | None = None,
        error_message: str | None = None,
    ) -> ExtractedFieldResult:
        """
        Add one extraction result and update raw_outputs on success.
        """
        result = ExtractedFieldResult(
            name=name,
            output_field=output_field,
            strategy=strategy,
            success=success,
            value=value,
            evidence=evidence,
            selector_used=selector_used,
            confidence=confidence,
            error_code=error_code,
            error_message=error_message,
        )
        self.extracted_fields.append(result)

        if success:
            self.raw_outputs[output_field] = value
            self.log(f"Field '{name}' extracted successfully into '{output_field}'.")
        else:
            self.log(
                f"Field '{name}' failed extraction."
                + (f" error_code={error_code}" if error_code else "")
            )

        return result

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
            page_category=self.page.category,
            url=self.page.url,
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
            page_category=self.page.category,
            url=self.page.url,
            fetch_mode=self.page.fetch.mode,
            status=status,
            started_at=self.started_at,
            finished_at=finished_at,
            extracted_fields=self.extracted_fields,
            raw_text_excerpt=self.raw_text_excerpt,
            html_snapshot_path=self.artifact_path("html"),
            screenshot_path=self.artifact_path("screenshot"),
            error=self.error,
        )


@dataclass(slots=True)
class UniversityRuntimeContext:
    """
    Mutable runtime state for one full university scrape run.

    This wraps all page contexts and the final normalized output.
    """

    university: UniversityConfig
    started_at: datetime = field(default_factory=datetime.utcnow)

    page_contexts: list[PageRuntimeContext] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)

    # Raw outputs grouped by page name after successful extraction
    page_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Final normalized snapshot populated by the normalizer layer
    snapshot_data: dict[str, Any] = field(default_factory=dict)

    def log(self, message: str) -> None:
        timestamp = datetime.utcnow().isoformat()
        self.logs.append(f"[{timestamp}] {message}")

    def create_page_context(self, page: PageConfig) -> PageRuntimeContext:
        ctx = PageRuntimeContext(university=self.university, page=page)
        self.page_contexts.append(ctx)
        self.log(f"Created page context for '{page.name}'.")
        return ctx

    def collect_page_output(self, page_ctx: PageRuntimeContext) -> None:
        self.page_outputs[page_ctx.page.name] = dict(page_ctx.raw_outputs)
        self.log(f"Collected raw outputs for page '{page_ctx.page.name}'.")

    def set_snapshot_data(self, data: dict[str, Any]) -> None:
        self.snapshot_data = data
        self.log("Snapshot data updated.")

    def get_page_context(self, page_name: str) -> PageRuntimeContext:
        for ctx in self.page_contexts:
            if ctx.page.name == page_name:
                return ctx
        raise KeyError(f"Page context '{page_name}' not found.")

    def get_page_output(self, page_name: str) -> dict[str, Any]:
        return self.page_outputs.get(page_name, {})