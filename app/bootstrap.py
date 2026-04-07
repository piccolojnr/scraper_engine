from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from app.extractors.factory import ExtractorFactory
from app.normalizers.orchestrator import EntityRunNormalizer
from app.persistence.db import SQLiteDatabase
from app.persistence.repositories import RunRepository
from app.runner.page_runner import PageRunner
from app.runner.university_runner import UniversityRunner
from app.runtime.browser_client import PlaywrightBrowserClient
from app.runtime.http_client import SimpleHttpClient
from app.runtime.openai_llm_client import OpenAILLMClient
from app.services.scrape_service import ScrapeService
from app.settings import AppSettings, get_settings


USER_AGENT = "UniScraper/2.0"


def build_run_repository(settings: AppSettings | None = None) -> RunRepository | None:
    resolved_settings = settings or get_settings()

    if not resolved_settings.persistence.enabled:
        return None

    repository = RunRepository(
        SQLiteDatabase(Path(resolved_settings.persistence.sqlite_path))
    )
    repository.initialize()
    return repository


@asynccontextmanager
async def build_scrape_service(
    *,
    headed: bool = False,
    browser: str = "chromium",
    settings: AppSettings | None = None,
) -> AsyncIterator[ScrapeService]:
    resolved_settings = settings or get_settings()
    llm_client = OpenAILLMClient.from_env()

    async with SimpleHttpClient(
        default_headers={"User-Agent": USER_AGENT},
        verify_ssl=resolved_settings.http_client.verify_ssl,
    ) as http_client, PlaywrightBrowserClient(
        headless=not headed,
        browser_type=browser,
        default_headers={"User-Agent": USER_AGENT},
    ) as browser_client:
        extractor_factory = ExtractorFactory(llm_client=llm_client)
        page_runner = PageRunner(
            extractor_factory=extractor_factory,
            http_client=http_client,
            browser_client=browser_client,
        )
        university_runner = UniversityRunner(
            page_runner=page_runner,
            normalizer=EntityRunNormalizer(),
        )

        yield ScrapeService(
            university_runner=university_runner,
            run_repository=build_run_repository(resolved_settings),
        )
