from __future__ import annotations

from app.config.models import ExtractRule, ExtractStrategy
from app.extractors.base import BaseExtractor, ExtractionResult
from app.extractors.utils import (
    parse_html,
    single_value_from_selector,
    text_list_from_selector,
    attribute_list_from_selector,
    snippet_around_match,
)
from app.runtime.context import PageRuntimeContext


class SelectorExtractor(BaseExtractor):
    """
    Extract values from HTML using CSS selectors.

    Supported behaviors:
      - single text value
      - single attribute value
      - list of text values
      - list of attribute values
    """

    name = "selector"
    version = "1"

    def validate_rule(self, rule: ExtractRule) -> None:
        if rule.strategy != ExtractStrategy.SELECTOR:
            raise ValueError(
                f"{self.__class__.__name__} only supports strategy='selector'."
            )

        if rule.selector_config is None:
            raise ValueError("selector_config is required for selector extraction.")

        if not rule.selector_config.selectors:
            raise ValueError("selector_config.selectors must not be empty.")

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

        soup = parse_html(context.html)
        selector_config = rule.selector_config
        assert selector_config is not None  # for typing

        selectors = selector_config.selectors
        attribute = selector_config.attribute

        if rule.many:
            return self._extract_many(
                context=context,
                rule=rule,
                soup=soup,
                selectors=selectors,
                attribute=attribute,
            )

        return self._extract_single(
            context=context,
            rule=rule,
            soup=soup,
            selectors=selectors,
            attribute=attribute,
        )

    def _extract_single(
        self,
        *,
        context: PageRuntimeContext,
        rule: ExtractRule,
        soup,
        selectors: list[str],
        attribute: str | None,
    ) -> ExtractionResult:
        value, selector_used = single_value_from_selector(
            soup,
            selectors=selectors,
            attribute=attribute,
        )

        if value is None:
            return self.make_failure_result(
                error_message=(
                    f"No value matched selectors {selectors}"
                    + (f" for attribute '{attribute}'." if attribute else ".")
                )
            )

        extraction_input = self.build_input(
            content=value,
            selector_used=selector_used,
        )
        metadata = self.build_metadata(
            rule=rule,
            extraction_input=extraction_input,
        )

        evidence = snippet_around_match(
            context.text_content or context.html or "",
            value,
        )

        return self.make_success_result(
            value=value,
            evidence=evidence or value[:300],
            selector_used=selector_used,
            confidence=1.0,
            metadata=metadata,
        )

    def _extract_many(
        self,
        *,
        context: PageRuntimeContext,
        rule: ExtractRule,
        soup,
        selectors: list[str],
        attribute: str | None,
    ) -> ExtractionResult:
        if attribute:
            values, selector_used = attribute_list_from_selector(
                soup,
                selectors=selectors,
                attribute=attribute,
            )
        else:
            values, selector_used = text_list_from_selector(
                soup,
                selectors=selectors,
            )

        if not values:
            return self.make_failure_result(
                error_message=(
                    f"No values matched selectors {selectors}"
                    + (f" for attribute '{attribute}'." if attribute else ".")
                )
            )

        combined_content = "\n".join(values)
        extraction_input = self.build_input(
            content=combined_content,
            selector_used=selector_used,
        )
        metadata = self.build_metadata(
            rule=rule,
            extraction_input=extraction_input,
        )

        preview = values[:5]
        evidence = " | ".join(preview)

        return self.make_success_result(
            value=values,
            evidence=evidence[:500],
            selector_used=selector_used,
            confidence=1.0,
            metadata=metadata,
        )