from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.config.models import ExtractRule, ExtractStrategy
from app.extractors.base import BaseExtractor, ExtractionResult
from app.extractors.utils import (
    all_matching_selectors,
    document_text,
    normalize_whitespace,
    parse_html,
)
from app.runtime.context import PageRuntimeContext


@dataclass(slots=True, frozen=True)
class LLMGenerationRequest:
    """
    Narrow, structured request sent to the LLM layer.

    The extractor prepares this request, but does not know how the LLM call
    is actually executed.
    """

    instruction: str
    content: str
    output_schema_name: str | None = None


@dataclass(slots=True)
class LLMGenerationResponse:
    """
    Structured response returned by the LLM layer.

    `value` should already be parsed into a Python object if possible.
    """

    success: bool
    value: Any = None
    raw_text: str | None = None
    confidence: float | None = None
    error_message: str | None = None


class LLMClient(Protocol):
    """
    Minimal protocol for the LLM dependency used by the extractor.

    You can later implement this with OpenAI, Anthropic, local models, etc.
    """

    async def generate_structured(
        self,
        request: LLMGenerationRequest,
    ) -> LLMGenerationResponse:
        ...


class LLMExtractor(BaseExtractor):
    """
    Extract structured or classified data from selected page content using an LLM.

    Behavior:
      - narrow input to selector-scoped content first
      - if selectors yield nothing useful, fall back to whole-document text
      - send a bounded instruction + content payload to the LLM client
      - return the structured value from the LLM response

    Notes:
      - This extractor does not know anything about specific providers.
      - This extractor does not do caching.
      - This extractor does not mutate runtime context directly.
    """

    name = "llm"
    version = "1"

    def __init__(self, client: LLMClient, *, max_input_chars: int = 12_000) -> None:
        self.client = client
        self.max_input_chars = max_input_chars

    def validate_rule(self, rule: ExtractRule) -> None:
        if rule.strategy != ExtractStrategy.LLM:
            raise ValueError(
                f"{self.__class__.__name__} only supports strategy='llm'."
            )

        if rule.llm_config is None:
            raise ValueError("llm_config is required for LLM extraction.")

        if not rule.llm_config.selectors:
            raise ValueError("llm_config.selectors must not be empty.")

        if not rule.llm_config.instruction.strip():
            raise ValueError("llm_config.instruction must not be empty.")

    async def extract(
        self,
        context: PageRuntimeContext,
        rule: ExtractRule,
    ) -> ExtractionResult:
        self.validate_rule(rule)

        if not context.html:
            return self.make_failure_result(
                error_message="No HTML content available in page context."
            )

        llm_config = rule.llm_config
        assert llm_config is not None  # typing

        soup = parse_html(context.html)

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
            rule=rule,
            extraction_input=extraction_input,
        )

        request = LLMGenerationRequest(
            instruction=llm_config.instruction,
            content=bounded_content,
            output_schema_name=llm_config.output_schema_name,
        )

        response = await self.client.generate_structured(request)

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
        """
        Resolve the best input content for the LLM.

        Prefer selector-scoped content because it is narrower and cheaper.
        Fall back to full-page text only if needed.
        """
        blocks = all_matching_selectors(soup, selectors)

        if blocks:
            combined = "\n\n".join(
                block.text for block in blocks if block.text.strip()
            ).strip()

            if combined:
                # Use the first matched selector as the primary evidence marker.
                return normalize_whitespace(combined), blocks[0].selector

        full_text = document_text(soup)
        return normalize_whitespace(full_text), None

    def _truncate_content(self, content: str) -> str:
        """
        Bound content size so the extractor stays predictable and cheap.
        """
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
        """
        Build a compact evidence string for result/debug storage.

        Prefer model raw text when available; otherwise use the start of the
        selected content block.
        """
        if raw_text:
            raw = normalize_whitespace(raw_text)
            if raw:
                return raw[:500]

        return content[:500]