from __future__ import annotations

from app.config.models import ExtractRule, ExtractStrategy
from app.extractors.base import BaseExtractor, ExtractionResult
from app.extractors.utils import (
    all_matching_selectors,
    document_text,
    first_matching_keyword_label,
    normalize_whitespace,
    parse_html,
    snippet_around_match,
)
from app.runtime.context import PageRuntimeContext


class KeywordExtractor(BaseExtractor):
    """
    Extract a labeled value by matching configured keywords against text
    resolved from one or more selectors.

    Typical use case:
      - classify portal status as open / closed / upcoming

    Behavior:
      - tries selectors in order
      - checks each matched selector block for a label match
      - if no selector block matches, falls back to whole-document text
      - returns the matched label as the extracted value
    """

    name = "keyword"
    version = "1"

    def validate_rule(self, rule: ExtractRule) -> None:
        if rule.strategy != ExtractStrategy.KEYWORD:
            raise ValueError(
                f"{self.__class__.__name__} only supports strategy='keyword'."
            )

        if rule.keyword_config is None:
            raise ValueError("keyword_config is required for keyword extraction.")

        if not rule.keyword_config.selectors:
            raise ValueError("keyword_config.selectors must not be empty.")

        if not rule.keyword_config.labels:
            raise ValueError("keyword_config.labels must not be empty.")

        if rule.many:
            raise ValueError("keyword extraction does not support many=True.")

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

        keyword_config = rule.keyword_config
        assert keyword_config is not None  # typing

        soup = parse_html(context.html)

        labels = [
            (group.label, group.keywords)
            for group in keyword_config.labels
        ]

        # 1. Try selector-scoped content first
        selected_blocks = all_matching_selectors(soup, keyword_config.selectors)

        for block in selected_blocks:
            label, matched_keyword = first_matching_keyword_label(
                block.text,
                labels,
                case_sensitive=keyword_config.case_sensitive,
                match_mode=keyword_config.match_mode,
            )

            if label is None or matched_keyword is None:
                continue

            extraction_input = self.build_input(
                content=block.text,
                selector_used=block.selector,
            )
            metadata = self.build_metadata(
                rule=rule,
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

        # 2. Fall back to full document text
        full_text = document_text(soup)
        label, matched_keyword = first_matching_keyword_label(
            full_text,
            labels,
            case_sensitive=keyword_config.case_sensitive,
            match_mode=keyword_config.match_mode,
        )

        if label is None or matched_keyword is None:
            extraction_input = self.build_input(
                content=full_text,
                selector_used=None,
            )
            metadata = self.build_metadata(
                rule=rule,
                extraction_input=extraction_input,
            )

            return self.make_failure_result(
                error_message="No configured keyword label matched the page content.",
                metadata=metadata,
            )

        extraction_input = self.build_input(
            content=full_text,
            selector_used=None,
        )
        metadata = self.build_metadata(
            rule=rule,
            extraction_input=extraction_input,
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