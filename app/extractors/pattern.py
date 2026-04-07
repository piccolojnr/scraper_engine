from __future__ import annotations

from app.config.models import ExtractStrategy
from app.extractors.base import BaseStepExtractor, ExtractionResult, StepExtractionRequest
from app.extractors.utils import (
    all_matching_selectors,
    document_text,
    first_matching_pattern_label,
    normalize_whitespace,
    parse_html,
    snippet_around_regex_match,
)
from app.runtime.context import PageRuntimeContext


class PatternExtractor(BaseStepExtractor):
    """
    Extract a labeled value by matching configured regex/text patterns against
    text resolved from one or more selectors.
    """

    name = "pattern"
    version = "2"

    async def extract_entity_field(
        self,
        *,
        context: PageRuntimeContext,
        request: StepExtractionRequest,
    ) -> ExtractionResult:
        step = request.step
        if step.strategy != ExtractStrategy.PATTERN:
            return self.make_failure_result(
                error_message="PatternExtractor only supports pattern steps."
            )

        if step.pattern_config is None:
            return self.make_failure_result(
                error_message="pattern_config is required for pattern extraction."
            )

        scoped_context = self.scoped_context(
            context=context,
            record_scope=request.record_scope,
        )

        if not scoped_context.html:
            return self.make_failure_result(
                error_message="No HTML content available in page context."
            )

        pattern_config = step.pattern_config
        soup = parse_html(scoped_context.html)

        labels = [
            (group.label, group.patterns)
            for group in pattern_config.labels
        ]

        selected_blocks = all_matching_selectors(soup, pattern_config.selectors)

        for block in selected_blocks:
            label, matched_pattern = first_matching_pattern_label(
                block.text,
                labels,
                case_sensitive=pattern_config.case_sensitive,
            )

            if label is None or matched_pattern is None:
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

            evidence = snippet_around_regex_match(
                block.text,
                matched_pattern,
                case_sensitive=pattern_config.case_sensitive,
            )

            return self.make_success_result(
                value=label,
                evidence=evidence or normalize_whitespace(block.text)[:300],
                selector_used=block.selector,
                confidence=1.0,
                metadata=metadata,
            )

        full_text = document_text(soup)
        label, matched_pattern = first_matching_pattern_label(
            full_text,
            labels,
            case_sensitive=pattern_config.case_sensitive,
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

        if label is None or matched_pattern is None:
            return self.make_failure_result(
                error_message="No configured pattern label matched the page content.",
                metadata=metadata,
            )

        evidence = snippet_around_regex_match(
            full_text,
            matched_pattern,
            case_sensitive=pattern_config.case_sensitive,
        )

        return self.make_success_result(
            value=label,
            evidence=evidence or full_text[:300],
            selector_used=None,
            confidence=0.9,
            metadata=metadata,
        )