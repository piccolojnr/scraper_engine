from __future__ import annotations

from app.config.models import ExtractStrategy
from app.extractors.base import Extractor
from app.extractors.keyword import KeywordExtractor
from app.extractors.llm import LLMClient, LLMExtractor
from app.extractors.pattern import PatternExtractor
from app.extractors.selector import SelectorExtractor
from app.extractors.table import TableExtractor


class ExtractorFactoryError(Exception):
    """Base extractor factory error."""


class UnsupportedExtractorStrategyError(ExtractorFactoryError):
    """Raised when no extractor exists for a configured strategy."""


class MissingExtractorDependencyError(ExtractorFactoryError):
    """Raised when an extractor requires a dependency that was not provided."""


class ExtractorFactory:
    """
    Factory for constructing extractor instances.

    Notes:
      - stateless extractors are created once and reused
      - dependency-backed extractors like LLM are created only if the required
        dependency is provided
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._llm_client = llm_client

        self._selector = SelectorExtractor()
        self._keyword = KeywordExtractor()
        self._pattern = PatternExtractor()
        self._table = TableExtractor()

    def get(self, strategy: ExtractStrategy) -> Extractor:
        if strategy == ExtractStrategy.SELECTOR:
            return self._selector

        if strategy == ExtractStrategy.KEYWORD:
            return self._keyword

        if strategy == ExtractStrategy.PATTERN:
            return self._pattern

        if strategy == ExtractStrategy.TABLE:
            return self._table

        if strategy == ExtractStrategy.LLM:
            if self._llm_client is None:
                raise MissingExtractorDependencyError(
                    "LLM extractor requested, but no llm_client was provided to ExtractorFactory."
                )
            return LLMExtractor(self._llm_client)

        raise UnsupportedExtractorStrategyError(
            f"No extractor registered for strategy '{strategy.value}'."
        )

    def has(self, strategy: ExtractStrategy) -> bool:
        if strategy == ExtractStrategy.LLM:
            return self._llm_client is not None

        return strategy in {
            ExtractStrategy.SELECTOR,
            ExtractStrategy.KEYWORD,
            ExtractStrategy.PATTERN,
            ExtractStrategy.TABLE,
        }
