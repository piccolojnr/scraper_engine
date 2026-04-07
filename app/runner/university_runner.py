from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.config.models import FetchMode, PageType, UniversityScraperConfig, ContentIntent, AudienceLevel
from app.runner.page_runner import PageRunner
from app.runtime.context import UniversityRuntimeContext
from app.schemas.results import (
    ErrorCode,
    NormalizedRunOutput,
    PageErrorReport,
    PageRunStatus,
    RunStatus,
    UniversityRunResult,
)


@runtime_checkable
class RunNormalizer(Protocol):
    """
    Converts raw page entity results into final normalized records.
    """

    async def normalize(
        self,
        context: UniversityRuntimeContext,
    ) -> NormalizedRunOutput:
        ...


@dataclass(slots=True)
class UniversityRunner:
    """
    Executes all enabled pages for one university config, then optionally
    normalizes extracted entities into final normalized output.
    """

    page_runner: PageRunner
    normalizer: RunNormalizer | None = None

    async def run(self, config: UniversityScraperConfig) -> UniversityRunResult:
        context = UniversityRuntimeContext(university=config)
        context.log(f"Starting university run for '{config.profile.id}'.")

        page_results = []
        page_errors: list[PageErrorReport] = []

        for page in config.enabled_pages():
            page_context = context.create_page_context(page)
            page_result = await self.page_runner.run(page_context)
            page_results.append(page_result)

            if page_result.error is not None:
                page_errors.append(page_result.error)

        run_status = self._derive_run_status(page_results)
        normalized: NormalizedRunOutput | None = None

        provisional_result = UniversityRunResult(
            university_id=config.profile.id,
            university_name=config.profile.university_name,
            status=run_status,
            started_at=context.started_at,
            finished_at=datetime.utcnow(),
            page_results=page_results,
            normalized=None,
            errors=page_errors,
        )
        context.set_run_result(provisional_result)

        if self.normalizer is not None:
            try:
                normalized = await self.normalizer.normalize(context)
                context.set_normalized(normalized)
            except Exception as exc:
                context.log(f"Normalization failed: {exc}")

                page_errors.append(
                    PageErrorReport(
                        page_name="__normalization__",
                        page_type=PageType.UNKNOWN,
                        intent=ContentIntent.GENERAL,
                        audience=AudienceLevel.GENERAL,
                        url="https://invalid.local/normalization",  # type: ignore[arg-type]
                        fetch_mode=FetchMode.HTTP,
                        error_code=ErrorCode.NORMALIZATION_FAILED,
                        message="Run normalization failed.",
                        detail=str(exc),
                        suggestion="Inspect entity results and normalizer logic.",
                    )
                )

                if run_status == RunStatus.SUCCESS:
                    run_status = RunStatus.PARTIAL_SUCCESS

        finished_at = datetime.utcnow()
        context.log(
            f"Finished university run for '{config.profile.id}' with status={run_status.value}."
        )

        final_result = UniversityRunResult(
            university_id=config.profile.id,
            university_name=config.profile.university_name,
            status=run_status,
            started_at=context.started_at,
            finished_at=finished_at,
            page_results=page_results,
            normalized=normalized,
            errors=page_errors,
        )
        context.set_run_result(final_result)
        return final_result

    def _derive_run_status(self, page_results: list) -> RunStatus:
        if not page_results:
            return RunStatus.FAILED

        total = len(page_results)
        failed = sum(1 for result in page_results if result.status == PageRunStatus.FAILED)
        succeeded = sum(1 for result in page_results if result.status == PageRunStatus.SUCCESS)

        if failed == 0 and succeeded == total:
            return RunStatus.SUCCESS

        if succeeded > 0:
            return RunStatus.PARTIAL_SUCCESS

        return RunStatus.FAILED