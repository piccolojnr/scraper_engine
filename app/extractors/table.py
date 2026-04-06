from __future__ import annotations

from typing import Any

from app.config.models import ExtractRule, ExtractStrategy
from app.extractors.base import BaseExtractor, ExtractionResult
from app.extractors.utils import (
    extract_tables,
    parse_html,
    table_to_rows,
)
from app.runtime.context import PageRuntimeContext


class TableExtractor(BaseExtractor):
    """
    Extract raw tabular data from HTML tables.

    This extractor is intentionally generic. It returns table payloads in a
    simple structured form and leaves domain interpretation to normalizers.

    Returned value shape:
        - if rule.many is False:
            {
                "selector_used": str | None,
                "header_row_index": int,
                "rows": list[list[str]],
            }

        - if rule.many is True:
            [
                {
                    "selector_used": str | None,
                    "header_row_index": int,
                    "rows": list[list[str]],
                },
                ...
            ]
    """

    name = "table"
    version = "1"

    def validate_rule(self, rule: ExtractRule) -> None:
        if rule.strategy != ExtractStrategy.TABLE:
            raise ValueError(
                f"{self.__class__.__name__} only supports strategy='table'."
            )

        if rule.table_config is None:
            raise ValueError("table_config is required for table extraction.")

        if not rule.table_config.selectors:
            raise ValueError("table_config.selectors must not be empty.")

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

        table_config = rule.table_config
        assert table_config is not None  # typing

        soup = parse_html(context.html)

        tables, selector_used = extract_tables(
            soup,
            selectors=table_config.selectors,
        )

        if not tables:
            extraction_input = self.build_input(
                content=context.text_content or context.html,
                selector_used=None,
            )
            metadata = self.build_metadata(
                rule=rule,
                extraction_input=extraction_input,
            )

            return self.make_failure_result(
                error_message=(
                    f"No tables matched selectors {table_config.selectors}."
                ),
                metadata=metadata,
            )

        payloads: list[dict[str, Any]] = []

        for table in tables:
            rows = table_to_rows(
                table,
                header_row_index=table_config.header_row_index,
            )

            if not rows:
                continue

            payloads.append(
                {
                    "selector_used": selector_used,
                    "header_row_index": table_config.header_row_index,
                    "rows": rows,
                }
            )

        if not payloads:
            combined_html = "\n".join(str(table) for table in tables)
            extraction_input = self.build_input(
                content=combined_html,
                selector_used=selector_used,
            )
            metadata = self.build_metadata(
                rule=rule,
                extraction_input=extraction_input,
            )

            return self.make_failure_result(
                error_message="Matched table elements but could not extract any rows.",
                selector_used=selector_used,
                metadata=metadata,
            )

        if rule.many:
            combined_content = "\n\n".join(
                "\n".join(" | ".join(row) for row in payload["rows"])
                for payload in payloads
            )
            extraction_input = self.build_input(
                content=combined_content,
                selector_used=selector_used,
            )
            metadata = self.build_metadata(
                rule=rule,
                extraction_input=extraction_input,
            )

            evidence = self._build_many_evidence(payloads)

            return self.make_success_result(
                value=payloads,
                evidence=evidence,
                selector_used=selector_used,
                confidence=1.0,
                metadata=metadata,
            )

        first_payload = payloads[0]
        content = "\n".join(" | ".join(row) for row in first_payload["rows"])
        extraction_input = self.build_input(
            content=content,
            selector_used=selector_used,
        )
        metadata = self.build_metadata(
            rule=rule,
            extraction_input=extraction_input,
        )

        evidence = self._build_single_evidence(first_payload)

        return self.make_success_result(
            value=first_payload,
            evidence=evidence,
            selector_used=selector_used,
            confidence=1.0,
            metadata=metadata,
        )

    def _build_single_evidence(self, payload: dict[str, Any]) -> str:
        rows: list[list[str]] = payload["rows"]
        preview_rows = rows[:3]
        return " || ".join(" | ".join(row) for row in preview_rows)[:500]

    def _build_many_evidence(self, payloads: list[dict[str, Any]]) -> str:
        parts: list[str] = []

        for payload in payloads[:2]:
            rows: list[list[str]] = payload["rows"]
            preview_rows = rows[:2]
            parts.append(" || ".join(" | ".join(row) for row in preview_rows))

        return " ### ".join(parts)[:500]