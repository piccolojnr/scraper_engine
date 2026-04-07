from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config.models import UniversityScraperConfig
from app.config.registry import ConfigRegistry
from app.persistence.models import PersistedRun
from app.persistence.repositories import RunRepository
from app.runner.university_runner import UniversityRunner
from app.schemas.results import UniversityRunResult


@dataclass(slots=True)
class ScrapeExecution:
    result: UniversityRunResult
    persisted_run: PersistedRun | None = None


class ScrapeService:
    def __init__(
        self,
        *,
        university_runner: UniversityRunner,
        run_repository: RunRepository | None = None,
    ) -> None:
        self.university_runner = university_runner
        self.run_repository = run_repository

    @staticmethod
    def load_configs(
        *,
        configs_package: str,
        configs_dir: str,
    ) -> list[UniversityScraperConfig]:
        config_registry = ConfigRegistry()
        config_registry.load_package(configs_package, Path(configs_dir))
        return config_registry.all()

    async def run(
        self,
        *,
        config_id: str,
        configs_package: str,
        configs_dir: str,
    ) -> ScrapeExecution:
        config_registry = ConfigRegistry()
        config_registry.load_package(configs_package, Path(configs_dir))
        config = config_registry.get(config_id)

        execution = await self.university_runner.run_with_context(config)
        persisted_run = None

        if self.run_repository is not None:
            persisted_run = self.run_repository.save_run(
                result=execution.result,
                logs=execution.context.logs,
            )

        return ScrapeExecution(
            result=execution.result,
            persisted_run=persisted_run,
        )
