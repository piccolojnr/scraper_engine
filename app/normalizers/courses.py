from __future__ import annotations

import re
from collections.abc import Iterable

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

            department = self.clean_str(raw.get("department"))
            degree_level = self.normalize_degree_level(raw.get("degree_level"))
            description = self.clean_str(raw.get("description"))
            course_pairs = self._expand_courses_with_faculty(
                raw.get("name"),
                raw.get("faculty"),
            )

            for name, faculty in course_pairs:
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
                        description=description,
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

    def _expand_course_names(self, value: object) -> list[str]:
        return [name for name, _faculty in self._expand_courses_with_faculty(value, None)]

    def _expand_courses_with_faculty(
        self,
        names_value: object,
        faculty_value: object,
    ) -> list[tuple[str, str | None]]:
        name_items = self._as_clean_list(names_value)
        faculty_items = self._as_clean_list(faculty_value)

        if name_items and faculty_items and name_items == faculty_items:
            return self._extract_courses_and_faculties_from_list(name_items)

        candidates: list[tuple[str, str | None]] = []
        if isinstance(names_value, str):
            for item in self._split_course_blob(names_value):
                candidates.append((item, None))
        elif isinstance(names_value, Iterable) and not isinstance(names_value, (str, bytes, dict)):
            for text in self._as_clean_list(names_value):
                if self._looks_like_course_blob(text):
                    for item in self._split_course_blob(text):
                        candidates.append((item, None))
                else:
                    candidates.append((text, None))
        else:
            text = self.clean_str(names_value)
            if text:
                candidates.append((text, None))

        cleaned: list[tuple[str, str | None]] = []
        seen: set[tuple[str, str | None]] = set()
        for item, faculty in candidates:
            normalized = self._clean_course_name(item)
            clean_faculty = self._clean_faculty_name(faculty)
            if not normalized:
                continue
            key = (normalized.lower(), clean_faculty.lower() if clean_faculty else None)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append((normalized, clean_faculty))
        return cleaned

    def _as_clean_list(self, value: object) -> list[str]:
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
            return [item for item in (self.clean_str(v) for v in value) if item]
        text = self.clean_str(value)
        return [text] if text else []

    def _looks_like_course_blob(self, text: str) -> bool:
        upper = text.upper()
        return (
            len(text) > 200
            or "FACULTY OF" in upper
            or "COLLEGE OF" in upper
            or upper.count(" FACULTY OF ") >= 1
        )

    def _looks_like_course_list(self, items: list[str]) -> bool:
        if len(items) < 5:
            return False
        heading_count = sum(1 for item in items if self._is_heading(item))
        return heading_count >= 1

    def _extract_courses_from_list(self, items: list[str]) -> list[str]:
        return [name for name, _faculty in self._extract_courses_and_faculties_from_list(items)]

    def _extract_courses_and_faculties_from_list(self, items: list[str]) -> list[tuple[str, str | None]]:
        courses: list[tuple[str, str | None]] = []
        current_faculty: str | None = None

        for item in items:
            cleaned = self._clean_course_name(item)
            if not cleaned:
                continue
            if self._is_heading(cleaned):
                current_faculty = self._clean_faculty_name(cleaned)
                continue
            courses.append((cleaned, current_faculty))

        return courses

    def _split_course_blob(self, text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return []

        normalized = re.sub(
            r"^APPROVED UNDERGRADUATE DEGREE PROGRAMMES/COURSES.*?LIST OF APPROVED PROGRAMMES/COURSES\s*",
            "",
            normalized,
            flags=re.IGNORECASE,
        )

        normalized = re.sub(r"\bCOLLEGE OF [A-Z &]+", "|", normalized)
        normalized = re.sub(r"\bFACULTY OF [A-Z &]+", "|", normalized)
        normalized = re.sub(r"\bSCHOOL OF [A-Z &]+", "|", normalized)
        normalized = re.sub(r"\bINSTITUTE OF [A-Z &]+", "|", normalized)

        pieces = [part.strip(" .|,-") for part in normalized.split("|")]

        expanded: list[str] = []
        for piece in pieces:
            if not piece:
                continue
            expanded.extend(self._extract_uppercase_course_names(piece))

        if expanded:
            return expanded

        return [normalized]

    def _extract_uppercase_course_names(self, text: str) -> list[str]:
        tokens = text.split()
        phrases: list[str] = []
        current: list[str] = []

        for token in tokens:
            cleaned = token.strip(" ,;:.\t\r\n")
            if not cleaned:
                continue

            if self._is_course_token(cleaned):
                current.append(cleaned)
            else:
                if current:
                    phrases.append(" ".join(current))
                    current = []

        if current:
            phrases.append(" ".join(current))

        return phrases

    def _is_course_token(self, token: str) -> bool:
        upper = token.upper()
        if upper in {"&", "AND", "OF", "IN", "TO", "THE", "LANGUAGE", "STUDIES", "SCIENCE", "SCIENCES", "ARTS", "LAW", "MEDICINE", "PHARMACY", "ENGINEERING", "TECHNOLOGY", "EDUCATION", "ECONOMICS", "SOCIOLOGY", "PSYCHOLOGY", "STATISTICS", "HISTORY", "MUSIC", "BOTANY", "CHEMISTRY", "GEOLOGY", "PHYSICS", "MATHEMATICS", "MICROBIOLOGY", "ZOOLOGY", "PHYSIOLOGY", "PHYSIOTHERAPY", "DENTISTRY", "BIOCHEMISTRY", "COMPUTER", "ARCHAEOLOGY", "ANTHROPOLOGY", "ARABIC", "CLASSICS", "ENGLISH", "FRENCH", "GERMAN", "RUSSIAN", "PHILOSOPHY", "RELIGIOUS", "THEATRE", "ADULT", "GUIDIANCE&", "COUNSELLING", "HEALTH", "HUMAN", "KINETICS", "LIBRARY&INFORMATION", "SPECIAL", "TEACHER", "PRE-PRIMARY", "SOCIAL", "POLITICAL", "AGRICULTURAL", "ENVIRONMENTAL", "MECHANICAL", "ELECTRICAL/ELECTRONICS", "CIVIL", "PETROLEUM", "INDUSTRIAL", "PRODUCTION", "FOOD", "WOOD", "VETERINARY", "WILDLIFE", "ECOTOURISM", "AGRONOMY", "ANIMAL", "AQUACULTURE", "FISHERIES", "MANAGEMENT", "DEVELOPMENT", "PROTECTION", "ENVIROMENTAL", "BIOLOGY", "NURSING", "LABORATRY", "NUTRITION", "DIETETICS", "MULTIDISCIPLINARY", "RENEWABLE", "NATURAL", "RESOURCES", "COMMUNICATION"}:
            return True
        if re.fullmatch(r"[A-Z][A-Z/&().:-]*", upper):
            return True
        if re.fullmatch(r"\(.*\)", token):
            return True
        return False

    def _clean_course_name(self, value: str) -> str | None:
        text = re.sub(r"\s+", " ", value).strip(" ,;:.\t\r\n")
        if not text:
            return None

        upper = text.upper()
        if upper.startswith("APPROVED UNDERGRADUATE"):
            return None
        if upper.startswith("LIST OF APPROVED"):
            return None
        if upper == ".":
            return None
        if len(text) < 3:
            return None
        if self._is_fragment(text):
            return None
        return text

    def _is_fragment(self, text: str) -> bool:
        lower = text.lower()
        return lower in {
            "french",
            "german",
            "russian",
            "arts",
            "pre-primary",
            "science",
            "social science",
        }

    def _is_heading(self, text: str) -> bool:
        upper = text.upper()
        return (
            upper.startswith("FACULTY OF ")
            or upper.startswith("COLLEGE OF ")
            or upper.startswith("SCHOOL OF ")
            or upper.startswith("INSTITUTE OF ")
            or upper.endswith(":")
        )

    def _clean_faculty_name(self, value: str | None) -> str | None:
        text = self.clean_str(value)
        if not text:
            return None
        if not self._is_heading(text):
            return None
        return text.title()
