from __future__ import annotations

from app.config.models import EntityType
from app.normalizers.base import BaseEntityNormalizer
from app.runtime.context import UniversityRuntimeContext
from app.schemas.results import PortalRecord


class PortalEntityNormalizer(BaseEntityNormalizer):
    async def normalize_portals(
        self,
        context: UniversityRuntimeContext,
    ) -> list[PortalRecord]:
        entities = self.entity_results(context, EntityType.PORTAL)
        output: list[PortalRecord] = []
        seen: set[tuple[str, str, str]] = set()

        for entity in entities:
            raw = entity.output_map()

            title = self.clean_str(raw.get("title"))
            portal_url = self.clean_str(raw.get("portal_url"))
            degree_level = self.normalize_degree_level(raw.get("degree_level"))
            academic_year = self.clean_str(raw.get("academic_year"))

            if not title:
                continue

            dedupe_key = (
                title.lower(),
                (portal_url or "").lower(),
                (academic_year or "").lower(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            output.append(
                PortalRecord(
                    external_university_id=context.university.profile.id,
                    university_name_hint=context.university.profile.university_name,
                    title=title,
                    slug_candidate=self.clean_str(raw.get("slug_candidate")),
                    description=self.clean_str(raw.get("description")),
                    portal_url=portal_url,
                    degree_level=degree_level,
                    academic_year=academic_year,
                    opens_at=self.parse_datetime(raw.get("opens_at")),
                    closes_at=self.parse_datetime(raw.get("closes_at")),
                    next_opens_at=self.parse_datetime(raw.get("next_opens_at")),
                    status=self.normalize_portal_status(raw.get("status")),
                    fee_amount=self.parse_decimal(raw.get("fee_amount")),
                    fee_currency=self.clean_str(raw.get("fee_currency")) or "GHS",
                    intl_fee_amount=self.parse_decimal(raw.get("intl_fee_amount")),
                    intl_fee_currency=self.clean_str(raw.get("intl_fee_currency")),
                    fee_note=self.clean_str(raw.get("fee_note")),
                    requirements=self.clean_str(raw.get("requirements")),
                    instructions=self.clean_str(raw.get("instructions")),
                    is_featured=None,
                    is_premium=None,
                    source_urls=self.merge_source_urls([entity]),
                    source_page_names=self.merge_source_page_names([entity]),
                    raw_snippets=self.merge_raw_snippets([entity]),
                    confidence=entity.confidence,
                )
            )

        return output