from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENAI_", extra="ignore")

    api_key: str | None = None
    base_url: str | None = None
    model: str = "gpt-4.1-mini"
    timeout_seconds: float = 60.0
    reasoning_effort: str | None = None


class HttpClientSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HTTP_CLIENT_", extra="ignore")

    verify_ssl: bool = True


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    openai: OpenAISettings = OpenAISettings()
    http_client: HttpClientSettings = HttpClientSettings()


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
