from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Iterable

from app.config.models import UniversityConfig


class ConfigRegistryError(Exception):
    """Base registry error."""


class ConfigNotFoundError(ConfigRegistryError):
    """Raised when a config ID cannot be found."""


class DuplicateConfigError(ConfigRegistryError):
    """Raised when a config with the same ID is registered twice."""


class InvalidConfigModuleError(ConfigRegistryError):
    """Raised when a module does not expose a valid CONFIG object."""


class ConfigRegistry:
    """
    In-memory registry for scraper configs.

    Convention:
      Each config module should expose a module-level variable called CONFIG
      whose value is a UniversityConfig instance.

    Example:
      configs/ug.py -> CONFIG = UniversityConfig(...)
    """

    def __init__(self) -> None:
        self._configs: dict[str, UniversityConfig] = {}

    def register(self, config: UniversityConfig) -> None:
        if config.id in self._configs:
            raise DuplicateConfigError(
                f"Config '{config.id}' is already registered."
            )
        self._configs[config.id] = config

    def register_many(self, configs: Iterable[UniversityConfig]) -> None:
        for config in configs:
            self.register(config)

    def register_module(self, module: ModuleType | str) -> UniversityConfig:
        """
        Register a config from a Python module object or import path.

        The module must expose:
            CONFIG: UniversityConfig
        """
        if isinstance(module, str):
            module = importlib.import_module(module)

        config = getattr(module, "CONFIG", None)

        if config is None:
            raise InvalidConfigModuleError(
                f"Module '{module.__name__}' does not define CONFIG."
            )

        if not isinstance(config, UniversityConfig):
            raise InvalidConfigModuleError(
                f"Module '{module.__name__}' has CONFIG, but it is not a UniversityConfig."
            )

        self.register(config)
        return config

    def register_modules(self, modules: Iterable[ModuleType | str]) -> None:
        for module in modules:
            self.register_module(module)

    def load_package(self, package_name: str, package_dir: str | Path) -> None:
        """
        Import and register every Python file in a package directory except:
          - __init__.py
          - files starting with '_'

        Example:
            registry.load_package("configs", Path("configs"))
        """
        package_path = Path(package_dir)

        for path in sorted(package_path.glob("*.py")):
            if path.name == "__init__.py" or path.name.startswith("_"):
                continue

            module_name = f"{package_name}.{path.stem}"
            self.register_module(module_name)

    def get(self, config_id: str) -> UniversityConfig:
        try:
            return self._configs[config_id]
        except KeyError as exc:
            raise ConfigNotFoundError(
                f"Config '{config_id}' is not registered."
            ) from exc

    def has(self, config_id: str) -> bool:
        return config_id in self._configs

    def all(self) -> list[UniversityConfig]:
        return sorted(self._configs.values(), key=lambda c: c.id)

    def ids(self) -> list[str]:
        return sorted(self._configs.keys())

    def remove(self, config_id: str) -> UniversityConfig:
        try:
            return self._configs.pop(config_id)
        except KeyError as exc:
            raise ConfigNotFoundError(
                f"Config '{config_id}' is not registered."
            ) from exc

    def clear(self) -> None:
        self._configs.clear()


registry = ConfigRegistry()