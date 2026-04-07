from __future__ import annotations

from app.config.models import ExtractStrategy
from app.extractors.base import BaseStepExtractor, ExtractionResult, StepExtractionRequest
from app.extractors.utils import (
    all_matching_selectors,
    document_text,
    first_matching_keyword_label,
    normalize_whitespace,
    parse_html,
    snippet_around_match,
)
from app.runtime.context import PageRuntimeContext


class KeywordExtractor(BaseStepExtractor):
    """
    Extract a labeled value by matching configured keywords against text
    resolved from one or more selectors.

    Typical use case:
      - classify portal status as open / closed / upcoming
      - infer degree level from local record content
    """

    name = "keyword"
    version = "2"

    async def extract_entity_field(
        self,
        *,
        context: PageRuntimeContext,
        request: StepExtractionRequest,
    ) -> ExtractionResult:
        step = request.step
        if step.strategy != ExtractStrategy.KEYWORD:
            return self.make_failure_result(
                error_message="KeywordExtractor only supports keyword steps."
            )

        if step.keyword_config is None:
            return self.make_failure_result(
                error_message="keyword_config is required for keyword extraction."
            )

        scoped_context = self.scoped_context(
            context=context,
            record_scope=request.record_scope,
        )

        if not scoped_context.html:
            return self.make_failure_result(
                error_message="No HTML content available in page context."
            )

        keyword_config = step.keyword_config
        soup = parse_html(scoped_context.html)

        labels = [
            (group.label, group.keywords)
            for group in keyword_config.labels
        ]

        selected_blocks = all_matching_selectors(soup, keyword_config.selectors)

        for block in selected_blocks:
            label, matched_keyword = first_matching_keyword_label(
                block.text,
                labels,
                case_sensitive=keyword_config.case_sensitive,
                match_mode=keyword_config.match_mode.value,
            )

            if label is None or matched_keyword is None:
                continue

            extraction_input = self.build_input(
                content=block.text,
                selector_used=block.selector,
            )
            metadata = self.build_metadata(
                field_name=request.field_name,
                step=step,
                extraction_input=extraction_input,
            )

            evidence = snippet_around_match(
                block.text,
                matched_keyword,
                case_sensitive=keyword_config.case_sensitive,
            )

            return self.make_success_result(
                value=label,
                evidence=evidence or normalize_whitespace(block.text)[:300],
                selector_used=block.selector,
                confidence=1.0,
                metadata=metadata,
            )

        full_text = document_text(soup)
        label, matched_keyword = first_matching_keyword_label(
            full_text,
            labels,
            case_sensitive=keyword_config.case_sensitive,
            match_mode=keyword_config.match_mode.value,
        )

        extraction_input = self.build_input(
            content=full_text,
            selector_used=None,
        )
        metadata = self.build_metadata(
            field_name=request.field_name,
            step=step,
            extraction_input=extraction_input,
        )

        if label is None or matched_keyword is None:
            return self.make_failure_result(
                error_message="No configured keyword label matched the page content.",
                metadata=metadata,
            )

        evidence = snippet_around_match(
            full_text,
            matched_keyword,
            case_sensitive=keyword_config.case_sensitive,
        )

        return self.make_success_result(
            value=label,
            evidence=evidence or full_text[:300],
            selector_used=None,
            confidence=0.9,
            metadata=metadata,
        )