from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Any, Protocol

from app.config.models import ExtractionStep
from app.runtime.context import PageRuntimeContext


@dataclass(slots=True, frozen=True)
class ExtractionInput:
    content: str
    selector_used: str | None = None

    def fingerprint(self) -> str:
        return sha256(self.content.encode("utf-8", errors="ignore")).hexdigest()


@dataclass(slots=True, frozen=True)
class ExtractionMetadata:
    extractor_name: str
    extractor_version: str
    field_name: str
    step_name: str
    strategy_name: str
    input_fingerprint: str

    def cache_key(self) -> str:
        return ":".join(
            [
                self.extractor_name,
                self.extractor_version,
                self.field_name,
                self.step_name,
                self.strategy_name,
                self.input_fingerprint,
            ]
        )


@dataclass(slots=True)
class ExtractionResult:
    success: bool
    value: Any = None
    evidence: str | None = None
    selector_used: str | None = None
    confidence: float | None = None
    error_message: str | None = None
    metadata: ExtractionMetadata | None = None


@dataclass(slots=True, frozen=True)
class RecordScope:
    record_index: int
    html_fragment: str | None = None
    text_fragment: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class StepExtractionRequest:
    field_name: str
    step: ExtractionStep
    record_scope: RecordScope | None = None


class StepExtractor(Protocol):
    name: str
    version: str

    async def extract_entity_field(
        self,
        *,
        context: PageRuntimeContext,
        request: StepExtractionRequest,
    ) -> ExtractionResult:
        ...


class BaseStepExtractor(ABC):
    name: str = "base"
    version: str = "1"

    @abstractmethod
    async def extract_entity_field(
        self,
        *,
        context: PageRuntimeContext,
        request: StepExtractionRequest,
    ) -> ExtractionResult:
        raise NotImplementedError

    def build_metadata(
        self,
        *,
        field_name: str,
        step: ExtractionStep,
        extraction_input: ExtractionInput,
    ) -> ExtractionMetadata:
        return ExtractionMetadata(
            extractor_name=self.name,
            extractor_version=self.version,
            field_name=field_name,
            step_name=step.name,
            strategy_name=step.strategy.value,
            input_fingerprint=extraction_input.fingerprint(),
        )

    def make_success_result(
        self,
        *,
        value: Any,
        evidence: str | None = None,
        selector_used: str | None = None,
        confidence: float | None = None,
        metadata: ExtractionMetadata | None = None,
    ) -> ExtractionResult:
        return ExtractionResult(
            success=True,
            value=value,
            evidence=evidence,
            selector_used=selector_used,
            confidence=confidence,
            error_message=None,
            metadata=metadata,
        )

    def make_failure_result(
        self,
        *,
        error_message: str,
        evidence: str | None = None,
        selector_used: str | None = None,
        metadata: ExtractionMetadata | None = None,
    ) -> ExtractionResult:
        return ExtractionResult(
            success=False,
            value=None,
            evidence=evidence,
            selector_used=selector_used,
            confidence=None,
            error_message=error_message,
            metadata=metadata,
        )

    def scoped_context(
        self,
        *,
        context: PageRuntimeContext,
        record_scope: RecordScope | None,
    ) -> PageRuntimeContext:
        if record_scope is None:
            return context

        scoped_html = record_scope.html_fragment or context.html
        scoped_text = record_scope.text_fragment or context.text_content

        return replace(
            context,
            html=scoped_html,
            text_content=scoped_text,
            raw_text_excerpt=(scoped_text[:1000] if scoped_text else context.raw_text_excerpt),
        )

    def page_text(self, context: PageRuntimeContext) -> str:
        if context.text_content:
            return context.text_content
        if context.html:
            return context.html
        return ""

    def build_input(
        self,
        *,
        content: str,
        selector_used: str | None = None,
    ) -> ExtractionInput:
        return ExtractionInput(
            content=content,
            selector_used=selector_used,
        )