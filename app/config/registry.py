from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Iterable

from app.config.models import ConfigStatus, UniversityScraperConfig


class ConfigRegistryError(Exception):
    """Base registry error."""


class ConfigNotFoundError(ConfigRegistryError):
    """Raised when a config ID cannot be found."""


class DuplicateConfigError(ConfigRegistryError):
    """Raised when a config with the same ID is registered twice."""


class InvalidConfigModuleError(ConfigRegistryError):
    """Raised when a module does not expose a valid CONFIG object."""


class ConfigRegistry:
    def __init__(self) -> None:
        self._configs: dict[str, UniversityScraperConfig] = {}

    def _config_id(self, config: UniversityScraperConfig) -> str:
        return config.profile.id

    def register(self, config: UniversityScraperConfig) -> None:
        config_id = self._config_id(config)

        if config_id in self._configs:
            raise DuplicateConfigError(
                f"Config '{config_id}' is already registered."
            )

        self._configs[config_id] = config

    def register_many(self, configs: Iterable[UniversityScraperConfig]) -> None:
        for config in configs:
            self.register(config)

    def register_module(self, module: ModuleType | str) -> UniversityScraperConfig:
        if isinstance(module, str):
            module = importlib.import_module(module)

        config = getattr(module, "CONFIG", None)

        if config is None:
            raise InvalidConfigModuleError(
                f"Module '{module.__name__}' does not define CONFIG."
            )

        if not isinstance(config, UniversityScraperConfig):
            raise InvalidConfigModuleError(
                f"Module '{module.__name__}' has CONFIG, but it is not a UniversityScraperConfig."
            )

        self.register(config)
        return config

    def register_modules(self, modules: Iterable[ModuleType | str]) -> None:
        for module in modules:
            self.register_module(module)

    def load_package(self, package_name: str, package_dir: str | Path) -> None:
        package_path = Path(package_dir)

        for path in sorted(package_path.glob("*.py")):
            if path.name == "__init__.py" or path.name.startswith("_"):
                continue

            module_name = f"{package_name}.{path.stem}"
            self.register_module(module_name)

    def get(self, config_id: str) -> UniversityScraperConfig:
        try:
            return self._configs[config_id]
        except KeyError as exc:
            raise ConfigNotFoundError(
                f"Config '{config_id}' is not registered."
            ) from exc

    def has(self, config_id: str) -> bool:
        return config_id in self._configs

    def all(self) -> list[UniversityScraperConfig]:
        return sorted(self._configs.values(), key=lambda c: c.profile.id)

    def ids(self) -> list[str]:
        return sorted(self._configs.keys())

    def by_status(self, status: ConfigStatus) -> list[UniversityScraperConfig]:
        return sorted(
            (config for config in self._configs.values() if config.audit.status == status),
            key=lambda c: c.profile.id,
        )

    def active(self) -> list[UniversityScraperConfig]:
        return self.by_status(ConfigStatus.ACTIVE)

    def remove(self, config_id: str) -> UniversityScraperConfig:
        try:
            return self._configs.pop(config_id)
        except KeyError as exc:
            raise ConfigNotFoundError(
                f"Config '{config_id}' is not registered."
            ) from exc

    def clear(self) -> None:
        self._configs.clear()


registry = ConfigRegistry()