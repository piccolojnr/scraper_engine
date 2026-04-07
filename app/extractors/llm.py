from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.config.models import ExtractStrategy
from app.extractors.base import BaseStepExtractor, ExtractionResult, StepExtractionRequest
from app.extractors.utils import (
    all_matching_selectors,
    document_text,
    normalize_whitespace,
    parse_html,
)
from app.runtime.context import PageRuntimeContext


@dataclass(slots=True, frozen=True)
class LLMGenerationRequest:
    instruction: str
    content: str
    output_schema_name: str | None = None


@dataclass(slots=True)
class LLMGenerationResponse:
    success: bool
    value: Any = None
    raw_text: str | None = None
    confidence: float | None = None
    error_message: str | None = None


class LLMClient(Protocol):
    async def generate_structured(
        self,
        request: LLMGenerationRequest,
    ) -> LLMGenerationResponse:
        ...


class LLMExtractor(BaseStepExtractor):
    """
    Extract structured or classified data from selected page content using an LLM.
    """

    name = "llm"
    version = "2"

    def __init__(self, client: LLMClient, *, max_input_chars: int = 12_000) -> None:
        self.client = client
        self.max_input_chars = max_input_chars

    async def extract_entity_field(
        self,
        *,
        context: PageRuntimeContext,
        request: StepExtractionRequest,
    ) -> ExtractionResult:
        step = request.step
        if step.strategy != ExtractStrategy.LLM:
            return self.make_failure_result(
                error_message="LLMExtractor only supports llm steps."
            )

        if step.llm_config is None:
            return self.make_failure_result(
                error_message="llm_config is required for LLM extraction."
            )

        if not step.llm_config.instruction.strip():
            return self.make_failure_result(
                error_message="llm_config.instruction must not be empty."
            )

        scoped_context = self.scoped_context(
            context=context,
            record_scope=request.record_scope,
        )

        if not scoped_context.html:
            return self.make_failure_result(
                error_message="No HTML content available in page context."
            )

        llm_config = step.llm_config
        soup = parse_html(scoped_context.html)

        content, selector_used = self._resolve_content(
            soup=soup,
            selectors=llm_config.selectors,
        )

        if not content:
            return self.make_failure_result(
                error_message="No content available for LLM extraction."
            )

        bounded_content = self._truncate_content(content)
        extraction_input = self.build_input(
            content=bounded_content,
            selector_used=selector_used,
        )
        metadata = self.build_metadata(
            field_name=request.field_name,
            step=step,
            extraction_input=extraction_input,
        )

        response = await self.client.generate_structured(
            LLMGenerationRequest(
                instruction=llm_config.instruction,
                content=bounded_content,
                output_schema_name=llm_config.output_schema_name,
            )
        )

        if not response.success:
            return self.make_failure_result(
                error_message=response.error_message or "LLM extraction failed.",
                evidence=(response.raw_text[:500] if response.raw_text else None),
                selector_used=selector_used,
                metadata=metadata,
            )

        evidence = self._build_evidence(
            content=bounded_content,
            raw_text=response.raw_text,
        )

        return self.make_success_result(
            value=response.value,
            evidence=evidence,
            selector_used=selector_used,
            confidence=response.confidence,
            metadata=metadata,
        )

    def _resolve_content(
        self,
        *,
        soup,
        selectors: list[str],
    ) -> tuple[str, str | None]:
        blocks = all_matching_selectors(soup, selectors)

        if blocks:
            combined = "\n\n".join(
                block.text for block in blocks if block.text.strip()
            ).strip()

            if combined:
                return normalize_whitespace(combined), blocks[0].selector

        full_text = document_text(soup)
        return normalize_whitespace(full_text), None

    def _truncate_content(self, content: str) -> str:
        content = normalize_whitespace(content)
        if len(content) <= self.max_input_chars:
            return content
        return content[: self.max_input_chars].rstrip()

    def _build_evidence(
        self,
        *,
        content: str,
        raw_text: str | None,
    ) -> str:
        if raw_text:
            raw = normalize_whitespace(raw_text)
            if raw:
                return raw[:500]

        return content[:500]