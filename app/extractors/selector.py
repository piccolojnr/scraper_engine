from __future__ import annotations

from app.config.models import ExtractStrategy
from app.extractors.base import BaseStepExtractor, ExtractionResult, StepExtractionRequest
from app.extractors.utils import (
    parse_html,
    single_value_from_selector,
    text_list_from_selector,
    attribute_list_from_selector,
    snippet_around_match,
)
from app.runtime.context import PageRuntimeContext


class SelectorExtractor(BaseStepExtractor):
    name = "selector"
    version = "2"

    async def extract_entity_field(
        self,
        *,
        context: PageRuntimeContext,
        request: StepExtractionRequest,
    ) -> ExtractionResult:
        step = request.step
        if step.strategy != ExtractStrategy.SELECTOR:
            return self.make_failure_result(
                error_message="SelectorExtractor only supports selector steps."
            )

        if step.selector_config is None:
            return self.make_failure_result(
                error_message="selector_config is required for selector extraction."
            )

        scoped_context = self.scoped_context(
            context=context,
            record_scope=request.record_scope,
        )

        if not scoped_context.html:
            return self.make_failure_result(
                error_message="No HTML content available in page context."
            )

        soup = parse_html(scoped_context.html)
        config = step.selector_config
        selectors = config.selectors
        attribute = config.attribute

        # selector extraction can infer many/single from caller intent later if needed;
        # for now keep it simple: if multiple matches exist, return list only when attribute/text list helpers are appropriate.
        if attribute:
            values, selector_used = attribute_list_from_selector(
                soup,
                selectors=selectors,
                attribute=attribute,
            )
            if values:
                extraction_input = self.build_input(
                    content="\n".join(values),
                    selector_used=selector_used,
                )
                metadata = self.build_metadata(
                    field_name=request.field_name,
                    step=step,
                    extraction_input=extraction_input,
                )
                if len(values) == 1:
                    value = values[0]
                    evidence = snippet_around_match(
                        scoped_context.text_content or scoped_context.html or "",
                        value,
                    )
                    return self.make_success_result(
                        value=value,
                        evidence=evidence or value[:300],
                        selector_used=selector_used,
                        confidence=1.0,
                        metadata=metadata,
                    )

                return self.make_success_result(
                    value=values,
                    evidence=" | ".join(values[:5])[:500],
                    selector_used=selector_used,
                    confidence=1.0,
                    metadata=metadata,
                )

        value, selector_used = single_value_from_selector(
            soup,
            selectors=selectors,
            attribute=None,
        )

        if value is None:
            values, selector_used = text_list_from_selector(
                soup,
                selectors=selectors,
            )
            if values:
                extraction_input = self.build_input(
                    content="\n".join(values),
                    selector_used=selector_used,
                )
                metadata = self.build_metadata(
                    field_name=request.field_name,
                    step=step,
                    extraction_input=extraction_input,
                )
                if len(values) == 1:
                    value = values[0]
                    evidence = snippet_around_match(
                        scoped_context.text_content or scoped_context.html or "",
                        value,
                    )
                    return self.make_success_result(
                        value=value,
                        evidence=evidence or value[:300],
                        selector_used=selector_used,
                        confidence=1.0,
                        metadata=metadata,
                    )

                return self.make_success_result(
                    value=values,
                    evidence=" | ".join(values[:5])[:500],
                    selector_used=selector_used,
                    confidence=1.0,
                    metadata=metadata,
                )

            return self.make_failure_result(
                error_message=f"No value matched selectors {selectors}."
            )

        extraction_input = self.build_input(
            content=value,
            selector_used=selector_used,
        )
        metadata = self.build_metadata(
            field_name=request.field_name,
            step=step,
            extraction_input=extraction_input,
        )

        evidence = snippet_around_match(
            scoped_context.text_content or scoped_context.html or "",
            value,
        )

        return self.make_success_result(
            value=value,
            evidence=evidence or value[:300],
            selector_used=selector_used,
            confidence=1.0,
            metadata=metadata,
        )