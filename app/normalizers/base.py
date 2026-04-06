from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from app.runtime.context import UniversityRuntimeContext
from app.schemas.results import UniversitySnapshot


class Normalizer(Protocol):
    """
    Protocol implemented by all university-level normalizers.
    """

    async def normalize(
        self,
        context: UniversityRuntimeContext,
    ) -> UniversitySnapshot:
        """
        Convert collected page outputs into a final normalized snapshot.
        """
        ...


class BaseNormalizer(ABC):
    """
    Shared base class for concrete normalizers.

    Responsibilities:
      - provide helper methods for accessing page outputs
      - provide helper methods for seeded/manual fallback values
      - define the normalize contract

    Non-responsibilities:
      - fetching
      - extraction
      - persistence
      - page execution
    """

    @abstractmethod
    async def normalize(
        self,
        context: UniversityRuntimeContext,
    ) -> UniversitySnapshot:
        raise NotImplementedError

    # ========================================================
    # PAGE OUTPUT HELPERS
    # ========================================================

    def page_output(
        self,
        context: UniversityRuntimeContext,
        page_name: str,
    ) -> dict[str, Any]:
        """
        Return the raw extracted output map for a page.

        Example:
            {
                "portal_status": "open",
                "portal_notice_text": "...",
            }
        """
        return context.get_page_output(page_name)

    def page_value(
        self,
        context: UniversityRuntimeContext,
        page_name: str,
        output_field: str,
        default: Any = None,
    ) -> Any:
        """
        Return one raw extracted value from a page output map.
        """
        return context.get_page_output(page_name).get(output_field, default)

    def first_value(
        self,
        context: UniversityRuntimeContext,
        page_names: list[str],
        output_field: str,
        default: Any = None,
    ) -> Any:
        """
        Return the first non-empty value found across multiple pages.

        Useful when multiple pages might expose overlapping information.
        """
        for page_name in page_names:
            value = context.get_page_output(page_name).get(output_field)
            if self.is_present(value):
                return value
        return default

    def collect_values(
        self,
        context: UniversityRuntimeContext,
        page_names: list[str],
        output_field: str,
    ) -> list[Any]:
        """
        Collect all non-empty values for one output field across multiple pages.
        """
        values: list[Any] = []

        for page_name in page_names:
            value = context.get_page_output(page_name).get(output_field)
            if self.is_present(value):
                values.append(value)

        return values

    # ========================================================
    # CONFIG / SEEDED FALLBACK HELPERS
    # ========================================================

    def seeded_fee_info(self, context: UniversityRuntimeContext) -> dict[str, Any] | None:
        return context.university.seeded_fee_info

    def seeded_apply_info(self, context: UniversityRuntimeContext) -> dict[str, Any] | None:
        return context.university.seeded_apply_info

    def seeded_profile(self, context: UniversityRuntimeContext) -> dict[str, Any] | None:
        return context.university.seeded_profile

    # ========================================================
    # COMMON UTILITIES
    # ========================================================

    def source_urls(self, context: UniversityRuntimeContext) -> list[str]:
        """
        Return page URLs for all enabled pages in config order.
        """
        return [str(page.url) for page in context.university.enabled_pages()]

    def successful_page_names(self, context: UniversityRuntimeContext) -> list[str]:
        """
        Return names of pages that produced collected outputs.
        """
        return list(context.page_outputs.keys())

    def merge_unique_strings(self, *values: str | None) -> list[str]:
        """
        Deduplicate string values while preserving order.
        """
        seen: set[str] = set()
        result: list[str] = []

        for value in values:
            if not value:
                continue

            cleaned = value.strip()
            if not cleaned or cleaned in seen:
                continue

            seen.add(cleaned)
            result.append(cleaned)

        return result

    def flatten_unique_strings(self, groups: list[list[str]]) -> list[str]:
        """
        Flatten nested string lists into a unique ordered list.
        """
        seen: set[str] = set()
        result: list[str] = []

        for group in groups:
            for item in group:
                cleaned = item.strip()
                if not cleaned or cleaned in seen:
                    continue

                seen.add(cleaned)
                result.append(cleaned)

        return result

    def is_present(self, value: Any) -> bool:
        """
        Decide whether a value should count as present during normalization.
        """
        if value is None:
            return False

        if isinstance(value, str):
            return bool(value.strip())

        if isinstance(value, (list, tuple, set, dict)):
            return len(value) > 0

        return True

    def as_list(self, value: Any) -> list[Any]:
        """
        Normalize one-or-many values into a list.
        """
        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]