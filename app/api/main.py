from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.api.schemas import ConfigSummary, PersistedRunResponse, RunRequest, RunResponse
from app.bootstrap import build_run_repository, build_scrape_service
from app.config.registry import ConfigNotFoundError
from app.services.scrape_service import ScrapeService


def create_app() -> FastAPI:
    api = FastAPI(
        title="UniScraper API",
        version="0.1.0",
        description="API wrapper around the scraper engine runtime.",
    )

    @api.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @api.get("/configs", response_model=list[ConfigSummary])
    async def list_configs(
        configs_package: str = "configs",
        configs_dir: str = "configs",
    ) -> list[ConfigSummary]:
        configs = ScrapeService.load_configs(
            configs_package=configs_package,
            configs_dir=configs_dir,
        )
        return [
            ConfigSummary(
                id=config.profile.id,
                university_name=config.profile.university_name,
                status=config.audit.status.value,
            )
            for config in configs
        ]

    @api.post("/runs", response_model=RunResponse, status_code=201)
    async def create_run(payload: RunRequest) -> RunResponse:
        try:
            async with build_scrape_service(
                headed=payload.headed,
                browser=payload.browser,
            ) as service:
                execution = await service.run(
                    config_id=payload.config_id,
                    configs_package=payload.configs_package,
                    configs_dir=payload.configs_dir,
                )
        except ConfigNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Run failed: {exc}") from exc

        return RunResponse.from_execution(execution)

    @api.get("/runs/{run_id}", response_model=PersistedRunResponse)
    async def get_run(run_id: str) -> PersistedRunResponse:
        repository = build_run_repository()
        if repository is None:
            raise HTTPException(status_code=503, detail="Persistence is disabled.")

        persisted_run = repository.get_run(run_id)
        if persisted_run is None:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' was not found.")

        return PersistedRunResponse.from_persisted_run(persisted_run)

    @api.get("/universities/{config_id}/latest", response_model=PersistedRunResponse)
    async def get_latest_run(config_id: str) -> PersistedRunResponse:
        repository = build_run_repository()
        if repository is None:
            raise HTTPException(status_code=503, detail="Persistence is disabled.")

        persisted_run = repository.get_latest_run(config_id)
        if persisted_run is None:
            raise HTTPException(
                status_code=404,
                detail=f"No persisted runs found for university '{config_id}'.",
            )

        return PersistedRunResponse.from_persisted_run(persisted_run)

    return api


app = create_app()
