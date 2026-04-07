from __future__ import annotations

from abc import ABC
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.config.models import EntityType
from app.runtime.context import UniversityRuntimeContext
from app.schemas.results import EntityExtractionResult


class BaseEntityNormalizer(ABC):
    """
    Shared helper base for entity-oriented normalizers.

    Responsibilities:
      - read raw extracted entity results from the run context
      - provide safe parsing / normalization helpers
      - provide source/evidence aggregation helpers

    Non-responsibilities:
      - fetching
      - extraction
      - persistence
    """

    def entity_results(
        self,
        context: UniversityRuntimeContext,
        entity_type: EntityType,
    ) -> list[EntityExtractionResult]:
        results: list[EntityExtractionResult] = []

        run_result = getattr(context, "run_result", None)
        if run_result is None:
            return results

        for page in run_result.page_results:
            for entity in page.entities:
                if entity.identity.entity_type == entity_type:
                    results.append(entity)

        return results

    def entity_maps(
        self,
        context: UniversityRuntimeContext,
        entity_type: EntityType,
    ) -> list[dict[str, Any]]:
        return [entity.output_map() for entity in self.entity_results(context, entity_type)]

    def first_entity_value(
        self,
        context: UniversityRuntimeContext,
        entity_type: EntityType,
        field_name: str,
        default: Any = None,
    ) -> Any:
        for item in self.entity_maps(context, entity_type):
            value = item.get(field_name)
            if self.is_present(value):
                return value
        return default

    def collect_entity_values(
        self,
        context: UniversityRuntimeContext,
        entity_type: EntityType,
        field_name: str,
    ) -> list[Any]:
        values: list[Any] = []
        for item in self.entity_maps(context, entity_type):
            value = item.get(field_name)
            if self.is_present(value):
                values.append(value)
        return values

    def merge_source_urls(self, entities: list[EntityExtractionResult]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []

        for entity in entities:
            url = entity.identity.source_url
            if not url:
                continue
            value = str(url).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            output.append(value)

        return output

    def merge_source_page_names(self, entities: list[EntityExtractionResult]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []

        for entity in entities:
            name = entity.identity.source_page_name.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            output.append(name)

        return output

    def merge_raw_snippets(self, entities: list[EntityExtractionResult]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []

        for entity in entities:
            snippet = (entity.raw_text_excerpt or "").strip()
            if not snippet or snippet in seen:
                continue
            seen.add(snippet)
            output.append(snippet)

        return output

    def average_confidence(self, entities: list[EntityExtractionResult]) -> float | None:
        scores = [e.confidence for e in entities if e.confidence is not None]
        if not scores:
            return None
        return sum(scores) / len(scores)

    def is_present(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) > 0
        return True

    def as_list(self, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def clean_str(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def parse_decimal(self, value: Any) -> Decimal | None:
        if value is None:
            return None
        text = str(value).strip().replace(",", "")
        if not text:
            return None
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None

    def parse_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except Exception:
            return None

    def parse_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value

        text = str(value).strip()
        if not text:
            return None

        # Keep this conservative for now.
        # You can replace this later with dateutil/parser.
        for fmt in (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        return None

    def normalize_degree_level(self, value: Any) -> str | None:
        text = (self.clean_str(value) or "").lower()
        if not text:
            return None

        if any(k in text for k in ["undergraduate", "bachelor", "bsc", "ba", "b.eng"]):
            return "undergraduate"
        if any(k in text for k in ["masters", "master", "msc", "ma", "mba", "mphil"]):
            return "masters"
        if any(k in text for k in ["phd", "doctorate", "doctoral"]):
            return "phd"
        if "diploma" in text and "postgraduate" in text:
            return "postgraduate_diploma"
        if "diploma" in text:
            return "diploma"
        if "certificate" in text:
            return "certificate"
        if "short course" in text or "short-course" in text:
            return "short_course"
        if "professional" in text:
            return "professional"
        if "all" in text:
            return "all"

        return None

    def normalize_portal_status(self, value: Any) -> str | None:
        text = (self.clean_str(value) or "").lower()
        if not text:
            return None

        if any(k in text for k in ["closing soon", "deadline approaching", "last chance"]):
            return "closing_soon"
        if any(k in text for k in ["open", "applications open", "apply now", "now open"]):
            return "open"
        if any(k in text for k in ["closed", "applications closed"]):
            return "closed"
        if any(k in text for k in ["upcoming", "coming soon", "opens soon"]):
            return "upcoming"
        if "unknown" in text:
            return "unknown"

        return None

    def normalize_course_mode(self, value: Any) -> str | None:
        text = (self.clean_str(value) or "").lower()
        if not text:
            return None

        if "part" in text and "time" in text:
            return "part_time"
        if "distance" in text or "online" in text:
            return "distance"
        if "sandwich" in text:
            return "sandwich"
        if "evening" in text:
            return "evening"
        if "weekend" in text:
            return "weekend"
        if "full" in text and "time" in text:
            return "full_time"

        return None