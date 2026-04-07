from __future__ import annotations

from app.config.models import EntityType
from app.normalizers.base import BaseEntityNormalizer
from app.runtime.context import UniversityRuntimeContext
from app.schemas.results import CourseRecord


class CourseEntityNormalizer(BaseEntityNormalizer):
    async def normalize_courses(
        self,
        context: UniversityRuntimeContext,
    ) -> list[CourseRecord]:
        entities = self.entity_results(context, EntityType.COURSE)
        output: list[CourseRecord] = []
        seen: set[tuple[str, str, str]] = set()

        for entity in entities:
            raw = entity.output_map()

            name = self.clean_str(raw.get("name"))
            faculty = self.clean_str(raw.get("faculty"))
            department = self.clean_str(raw.get("department"))
            degree_level = self.normalize_degree_level(raw.get("degree_level"))

            if not name:
                continue

            dedupe_key = (
                name.lower(),
                (degree_level or "").lower(),
                (department or "").lower(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            output.append(
                CourseRecord(
                    external_university_id=context.university.profile.id,
                    university_name_hint=context.university.profile.university_name,
                    name=name,
                    slug_candidate=self.clean_str(raw.get("slug_candidate")),
                    faculty=faculty,
                    department=department,
                    degree_level=degree_level,
                    mode=self.normalize_course_mode(raw.get("mode")),
                    duration_years=self.parse_int(raw.get("duration_years")),
                    tuition_fee=self.parse_decimal(raw.get("tuition_fee")),
                    fee_currency=self.clean_str(raw.get("fee_currency")) or "GHS",
                    fee_note=self.clean_str(raw.get("fee_note")),
                    description=self.clean_str(raw.get("description")),
                    requirements=self.clean_str(raw.get("requirements")),
                    cut_off_point=self.clean_str(raw.get("cut_off_point")),
                    is_active=True,
                    source_urls=self.merge_source_urls([entity]),
                    source_page_names=self.merge_source_page_names([entity]),
                    raw_snippets=self.merge_raw_snippets([entity]),
                    confidence=entity.confidence,
                )
            )

        return output