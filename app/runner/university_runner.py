from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.config.models import FetchMode, PageCategory, UniversityConfig
from app.runner.page_runner import PageRunner
from app.runtime.context import UniversityRuntimeContext
from app.schemas.results import (
    ErrorCode,
    PageErrorReport,
    PageRunStatus,
    RunStatus,
    UniversityRunResult,
    UniversitySnapshot,
)


@runtime_checkable
class UniversityNormalizer(Protocol):
    """
    Converts raw page outputs + page results into a final normalized snapshot.
    """

    async def normalize(
        self,
        context: UniversityRuntimeContext,
    ) -> UniversitySnapshot:
        ...


@dataclass(slots=True)
class UniversityRunner:
    """
    Executes all enabled pages for one university config, then optionally
    normalizes the combined outputs into a final UniversitySnapshot.
    """

    page_runner: PageRunner
    normalizer: UniversityNormalizer | None = None

    async def run(self, config: UniversityConfig) -> UniversityRunResult:
        context = UniversityRuntimeContext(university=config)
        context.log(f"Starting university run for '{config.id}'.")

        page_results = []
        page_errors: list[PageErrorReport] = []

        for page in config.enabled_pages():
            page_context = context.create_page_context(page)
            page_result = await self.page_runner.run(page_context)
            page_results.append(page_result)

            context.collect_page_output(page_context)

            if page_result.error is not None:
                page_errors.append(page_result.error)

        run_status = self._derive_run_status(page_results)
        snapshot: UniversitySnapshot | None = None

        if self.normalizer is not None:
            try:
                snapshot = await self.normalizer.normalize(context)
                context.set_snapshot_data(snapshot.model_dump())
            except Exception as exc:
                context.log(f"Normalization failed: {exc}")

                page_errors.append(
                    PageErrorReport(
                        page_name="__normalization__",
                        page_category=PageCategory.GENERAL,
                        url="https://invalid.local/normalization",  # type: ignore
                        fetch_mode=FetchMode.HTTP,
                        error_code=ErrorCode.NORMALIZATION_FAILED,
                        message="University normalization failed.",
                        detail=str(exc),
                        suggestion="Inspect page outputs and normalizer logic.",
                    )
                )

                run_status = RunStatus.FAILED if run_status == RunStatus.SUCCESS else run_status

        finished_at = datetime.utcnow()
        context.log(f"Finished university run for '{config.id}' with status={run_status.value}.")

        return UniversityRunResult(
            university_id=config.id,
            university_name=config.university_name,
            status=run_status,
            started_at=context.started_at,
            finished_at=finished_at,
            page_results=page_results,
            snapshot=snapshot,
            errors=page_errors,
        )

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