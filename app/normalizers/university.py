from __future__ import annotations

from app.config.models import EntityType
from app.normalizers.base import BaseEntityNormalizer
from app.runtime.context import UniversityRuntimeContext
from app.schemas.results import UniversityRecord


class UniversityEntityNormalizer(BaseEntityNormalizer):
    async def normalize_university(
        self,
        context: UniversityRuntimeContext,
    ) -> UniversityRecord | None:
        entities = self.entity_results(context, EntityType.UNIVERSITY)
        if not entities:
            return None

        first = entities[0].output_map()

        name = self.clean_str(first.get("name")) or context.university.profile.university_name
        country = self.clean_str(first.get("country")) or context.university.profile.country

        return UniversityRecord(
            external_university_id=context.university.profile.id,
            name=name,
            slug_candidate=self.clean_str(first.get("slug_candidate")),
            country=country,
            state_province=self.clean_str(first.get("state_province")),
            city=self.clean_str(first.get("city")),
            type=self.clean_str(first.get("type")),
            website_url=self.clean_str(first.get("website_url")),
            logo_url=self.clean_str(first.get("logo_url")),
            description=self.clean_str(first.get("description")),
            course_catalog_url=self.clean_str(first.get("course_catalog_url")),
            fee_schedule_url=self.clean_str(first.get("fee_schedule_url")),
            is_active=True,
            source_urls=self.merge_source_urls(entities),
            source_page_names=self.merge_source_page_names(entities),
            raw_snippets=self.merge_raw_snippets(entities),
            confidence=self.average_confidence(entities),
        )