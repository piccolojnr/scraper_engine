from __future__ import annotations

from typing import Any

from app.normalizers.base import BaseNormalizer
from app.runtime.context import UniversityRuntimeContext
from app.schemas.results import (
    AccreditationInfo,
    ApplyInfo,
    CutOffEntry,
    DeadlineEntry,
    FeeInfo,
    OngoingAdmission,
    Programme,
    Scholarship,
    TuitionFee,
    UniversityProfile,
    UniversitySnapshot,
)


class DefaultUniversityNormalizer(BaseNormalizer):
    """
    Default university-level normalizer.

    Philosophy:
      - be conservative
      - prefer extracted values first
      - use seeded/manual fallbacks where appropriate
      - avoid over-parsing ambiguous raw data too early

    This normalizer assumes page extractors mostly produce already-useful raw
    values such as:
      - portal_status
      - portal_notice_text
      - programmes_raw
      - deadlines_raw
      - fees_raw
      - cutoffs_raw
      - apply_notes_raw
      - scholarships_raw
    """

    async def normalize(
        self,
        context: UniversityRuntimeContext,
    ) -> UniversitySnapshot:
        status = self._normalize_status(context)
        raw_snippet = self._normalize_raw_snippet(context)
        deadlines = self._normalize_deadlines(context)
        programmes = self._normalize_programmes(context)
        cut_off_points = self._normalize_cutoffs(context)
        fees = self._normalize_fee_info(context)
        tuition_fees = self._normalize_tuition_fees(context)
        apply_info = self._normalize_apply_info(context)
        scholarships = self._normalize_scholarships(context)
        profile = self._normalize_profile(context)
        ongoing_admissions = self._normalize_ongoing_admissions(context)

        snapshot = UniversitySnapshot(
            university_id=context.university.id,
            university_name=context.university.university_name,
            status=status,
            raw_snippet=raw_snippet,
            deadlines=deadlines,
            programmes=programmes,
            cut_off_points=cut_off_points,
            fees=fees,
            tuition_fees=tuition_fees,
            apply_info=apply_info,
            scholarships=scholarships,
            profile=profile,
            ongoing_admissions=ongoing_admissions,
            source_urls=self.source_urls(context),
        )

        return snapshot

    # ========================================================
    # CORE FIELDS
    # ========================================================

    def _normalize_status(self, context: UniversityRuntimeContext) -> str | None:
        page_names = self.successful_page_names(context)

        return self.first_value(
            context,
            page_names=page_names,
            output_field="portal_status",
            default=None,
        )

    def _normalize_raw_snippet(self, context: UniversityRuntimeContext) -> str | None:
        page_names = self.successful_page_names(context)

        return self.first_value(
            context,
            page_names=page_names,
            output_field="portal_notice_text",
            default=None,
        )

    def _normalize_ongoing_admissions(
        self,
        context: UniversityRuntimeContext,
    ) -> list[OngoingAdmission]:
        page_names = self.successful_page_names(context)
        raw_groups = self.collect_values(context, page_names, "ongoing_admissions_raw")

        items: list[OngoingAdmission] = []

        for raw_value in raw_groups:
            for entry in self.as_list(raw_value):
                model = self._parse_model(entry, OngoingAdmission)
                if model is not None:
                    items.append(model)

        return items

    # ========================================================
    # DEADLINES
    # ========================================================

    def _normalize_deadlines(
        self,
        context: UniversityRuntimeContext,
    ) -> list[DeadlineEntry]:
        page_names = self.successful_page_names(context)
        raw_groups = self.collect_values(context, page_names, "deadlines_raw")

        items: list[DeadlineEntry] = []

        for raw_value in raw_groups:
            for entry in self._flatten_table_payloads(raw_value):
                deadline = self._deadline_from_row(entry)
                if deadline is not None:
                    items.append(deadline)

        return items

    def _deadline_from_row(self, row: Any) -> DeadlineEntry | None:
        """
        Accept either:
          - dict-like deadline entry
          - table row list[str]
        """
        if isinstance(row, dict):
            model = self._parse_model(row, DeadlineEntry)
            if model is not None:
                return model

        if isinstance(row, list) and row:
            admission_type = self._safe_str(row, 0)
            opens = self._safe_str(row, 1)
            closes = self._safe_str(row, 2)

            if not self.is_present(admission_type):
                return None

            return DeadlineEntry(
                admission_type=admission_type or "Unknown",
                opens=opens,
                closes=closes,
            )

        return None

    # ========================================================
    # PROGRAMMES
    # ========================================================

    def _normalize_programmes(
        self,
        context: UniversityRuntimeContext,
    ) -> list[Programme]:
        page_names = self.successful_page_names(context)
        raw_groups = self.collect_values(context, page_names, "programmes_raw")

        items: list[Programme] = []
        seen: set[str] = set()

        for raw_value in raw_groups:
            for entry in self.as_list(raw_value):
                programme = self._programme_from_entry(entry)
                if programme is None:
                    continue

                key = programme.name.strip().lower()
                if not key or key in seen:
                    continue

                seen.add(key)
                items.append(programme)

        return items

    def _programme_from_entry(self, entry: Any) -> Programme | None:
        if isinstance(entry, dict):
            model = self._parse_model(entry, Programme)
            if model is not None:
                return model

        if isinstance(entry, str) and entry.strip():
            return Programme(
                name=entry.strip(),
                degree_types=[],
                level="unknown",
            )

        return None

    # ========================================================
    # CUT-OFFS
    # ========================================================

    def _normalize_cutoffs(
        self,
        context: UniversityRuntimeContext,
    ) -> list[CutOffEntry]:
        page_names = self.successful_page_names(context)
        raw_groups = self.collect_values(context, page_names, "cutoffs_raw")

        items: list[CutOffEntry] = []

        for raw_value in raw_groups:
            for entry in self._flatten_table_payloads(raw_value):
                cutoff = self._cutoff_from_row(entry)
                if cutoff is not None:
                    items.append(cutoff)

        return items

    def _cutoff_from_row(self, row: Any) -> CutOffEntry | None:
        if isinstance(row, dict):
            model = self._parse_model(row, CutOffEntry)
            if model is not None:
                return model

        if isinstance(row, list) and row:
            programme = self._safe_str(row, 0)
            if not self.is_present(programme):
                return None

            return CutOffEntry(
                programme=programme or "Unknown",
                college=self._safe_str(row, 1),
                first_choice_cutoff=self._safe_str(row, 2),
                fee_paying_cutoff=self._safe_str(row, 3),
                second_choice_cutoff=self._safe_str(row, 4),
                subject_requirements=self._safe_str(row, 5),
            )

        return None

    # ========================================================
    # FEES
    # ========================================================

    def _normalize_fee_info(
        self,
        context: UniversityRuntimeContext,
    ) -> FeeInfo | None:
        page_names = self.successful_page_names(context)

        # Prefer direct extracted structured fee info if it exists
        raw_fee_info = self.first_value(
            context,
            page_names=page_names,
            output_field="fee_info_raw",
            default=None,
        )
        if raw_fee_info is not None:
            model = self._parse_model(raw_fee_info, FeeInfo)
            if model is not None:
                return model

        seeded = self.seeded_fee_info(context)
        if seeded is not None:
            model = self._parse_model(seeded, FeeInfo)
            if model is not None:
                return model

        return None

    def _normalize_tuition_fees(
        self,
        context: UniversityRuntimeContext,
    ) -> list[TuitionFee]:
        page_names = self.successful_page_names(context)
        raw_groups = self.collect_values(context, page_names, "fees_raw")

        items: list[TuitionFee] = []

        for raw_value in raw_groups:
            for entry in self._flatten_table_payloads(raw_value):
                fee = self._tuition_fee_from_row(entry)
                if fee is not None:
                    items.append(fee)

        return items

    def _tuition_fee_from_row(self, row: Any) -> TuitionFee | None:
        if isinstance(row, dict):
            model = self._parse_model(row, TuitionFee)
            if model is not None:
                return model

        if isinstance(row, list) and row:
            programme = self._safe_str(row, 0)
            if not self.is_present(programme):
                return None

            return TuitionFee(
                programme=programme or "Unknown",
                student_type=self._safe_str(row, 1) or "all",
                amount=self._safe_str(row, 2),
                currency=self._safe_str(row, 3),
                per=self._safe_str(row, 4) or "semester",
                notes=self._safe_str(row, 5),
            )

        return None

    # ========================================================
    # APPLY INFO
    # ========================================================

    def _normalize_apply_info(
        self,
        context: UniversityRuntimeContext,
    ) -> ApplyInfo | None:
        page_names = self.successful_page_names(context)

        raw_apply_info = self.first_value(
            context,
            page_names=page_names,
            output_field="apply_info_raw",
            default=None,
        )
        if raw_apply_info is not None:
            model = self._parse_model(raw_apply_info, ApplyInfo)
            if model is not None:
                return model

        apply_notes_groups = self.collect_values(context, page_names, "apply_notes_raw")
        required_docs_groups = self.collect_values(context, page_names, "required_documents_raw")

        notes = self._normalize_string_values(apply_notes_groups)
        required_documents = self._normalize_string_values(required_docs_groups)

        seeded = self.seeded_apply_info(context)
        seeded_model = self._parse_model(seeded, ApplyInfo) if seeded else None

        if not notes and not required_documents and seeded_model is None:
            return None

        return ApplyInfo(
            local_url=seeded_model.local_url if seeded_model else None,
            international_url=seeded_model.international_url if seeded_model else None,
            general_url=seeded_model.general_url if seeded_model else None,
            required_documents=required_documents or (seeded_model.required_documents if seeded_model else []),
            notes=notes or (seeded_model.notes if seeded_model else []),
            entry_requirements_summary=seeded_model.entry_requirements_summary if seeded_model else None,
            min_aggregate=seeded_model.min_aggregate if seeded_model else None,
        )

    # ========================================================
    # SCHOLARSHIPS
    # ========================================================

    def _normalize_scholarships(
        self,
        context: UniversityRuntimeContext,
    ) -> list[Scholarship]:
        page_names = self.successful_page_names(context)
        raw_groups = self.collect_values(context, page_names, "scholarships_raw")

        items: list[Scholarship] = []

        for raw_value in raw_groups:
            for entry in self.as_list(raw_value):
                model = self._parse_model(entry, Scholarship)
                if model is not None:
                    items.append(model)

        return items

    # ========================================================
    # PROFILE
    # ========================================================

    def _normalize_profile(
        self,
        context: UniversityRuntimeContext,
    ) -> UniversityProfile | None:
        page_names = self.successful_page_names(context)

        raw_profile = self.first_value(
            context,
            page_names=page_names,
            output_field="profile_raw",
            default=None,
        )
        if raw_profile is not None:
            model = self._parse_model(raw_profile, UniversityProfile)
            if model is not None:
                return model

        seeded = self.seeded_profile(context)
        if seeded is not None:
            model = self._parse_model(seeded, UniversityProfile)
            if model is not None:
                return model

        return None

    # ========================================================
    # HELPERS
    # ========================================================

    def _parse_model(self, raw: Any, model_cls):
        if raw is None:
            return None

        if isinstance(raw, model_cls):
            return raw

        if isinstance(raw, dict):
            try:
                return model_cls.model_validate(raw)
            except Exception:
                return None

        return None

    def _safe_str(self, row: list[Any], index: int) -> str | None:
        if index >= len(row):
            return None

        value = row[index]
        if value is None:
            return None

        text = str(value).strip()
        return text or None

    def _flatten_table_payloads(self, raw_value: Any) -> list[Any]:
        """
        Normalizes various table-style payloads into row-like entries.

        Supports:
          - single table payload:
              {"rows": [...]}
          - multiple table payloads:
              [{"rows": [...]}, {"rows": [...]}]
          - already-flat row entries
        """
        rows: list[Any] = []

        if raw_value is None:
            return rows

        if isinstance(raw_value, dict):
            table_rows = raw_value.get("rows")
            if isinstance(table_rows, list):
                return table_rows
            return rows

        if isinstance(raw_value, list):
            # list of payload dicts
            if raw_value and all(isinstance(item, dict) and "rows" in item for item in raw_value):
                for payload in raw_value:
                    table_rows = payload.get("rows", [])
                    if isinstance(table_rows, list):
                        rows.extend(table_rows)
                return rows

            # already list of rows or list of dict entries
            return raw_value

        return rows

    def _normalize_string_values(self, raw_groups: list[Any]) -> list[str]:
        values: list[str] = []

        for raw_value in raw_groups:
            for entry in self.as_list(raw_value):
                if isinstance(entry, str) and entry.strip():
                    values.append(entry.strip())

        return self.flatten_unique_strings([values])