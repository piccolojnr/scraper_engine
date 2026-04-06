from __future__ import annotations

from app.config.models import ExtractRule, ExtractStrategy
from app.extractors.base import BaseExtractor, ExtractionResult
from app.extractors.utils import (
    all_matching_selectors,
    document_text,
    first_matching_pattern_label,
    normalize_whitespace,
    parse_html,
    snippet_around_regex_match,
)
from app.runtime.context import PageRuntimeContext


class PatternExtractor(BaseExtractor):
    """
    Extract a labeled value by matching configured regex/text patterns against
    text resolved from one or more selectors.

    Typical use cases:
      - classify status with more flexible patterns
      - detect application cycle phrases
      - match variable text structures where exact keyword matching is too rigid

    Behavior:
      - tries selector-scoped content first
      - if no selector block matches, falls back to whole-document text
      - returns the configured label as the extracted value
    """

    name = "pattern"
    version = "1"

    def validate_rule(self, rule: ExtractRule) -> None:
        if rule.strategy != ExtractStrategy.PATTERN:
            raise ValueError(
                f"{self.__class__.__name__} only supports strategy='pattern'."
            )

        if rule.pattern_config is None:
            raise ValueError("pattern_config is required for pattern extraction.")

        if not rule.pattern_config.selectors:
            raise ValueError("pattern_config.selectors must not be empty.")

        if not rule.pattern_config.labels:
            raise ValueError("pattern_config.labels must not be empty.")

        if rule.many:
            raise ValueError("pattern extraction does not support many=True.")

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

        pattern_config = rule.pattern_config
        assert pattern_config is not None  # typing

        soup = parse_html(context.html)

        labels = [
            (group.label, group.patterns)
            for group in pattern_config.labels
        ]

        # 1. Prefer selector-scoped blocks first
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
                rule=rule,
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

        # 2. Fall back to whole-document text
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
            rule=rule,
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