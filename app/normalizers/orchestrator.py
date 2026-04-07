from __future__ import annotations

from app.normalizers.courses import CourseEntityNormalizer
from app.normalizers.portals import PortalEntityNormalizer
from app.normalizers.university import UniversityEntityNormalizer
from app.runtime.context import UniversityRuntimeContext
from app.schemas.results import NormalizedRunOutput


class EntityRunNormalizer:
    def __init__(self) -> None:
        self.university_normalizer = UniversityEntityNormalizer()
        self.portal_normalizer = PortalEntityNormalizer()
        self.course_normalizer = CourseEntityNormalizer()

    async def normalize(
        self,
        context: UniversityRuntimeContext,
    ) -> NormalizedRunOutput:
        university = await self.university_normalizer.normalize_university(context)
        portals = await self.portal_normalizer.normalize_portals(context)
        courses = await self.course_normalizer.normalize_courses(context)

        return NormalizedRunOutput(
            university=university,
            portals=portals,
            courses=courses,
        )