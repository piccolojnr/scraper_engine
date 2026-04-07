from __future__ import annotations

from app.config.models import ExtractStrategy
from app.extractors.base import StepExtractor
from app.extractors.keyword import KeywordExtractor
from app.extractors.llm import LLMClient, LLMExtractor
from app.extractors.pattern import PatternExtractor
from app.extractors.selector import SelectorExtractor
from app.extractors.table import TableExtractor


class ExtractorFactoryError(Exception):
    pass


class UnsupportedExtractorStrategyError(ExtractorFactoryError):
    pass


class MissingExtractorDependencyError(ExtractorFactoryError):
    pass


class ExtractorFactory:
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
        self._llm = LLMExtractor(llm_client) if llm_client is not None else None

    def get(self, strategy: ExtractStrategy) -> StepExtractor:
        if strategy == ExtractStrategy.SELECTOR:
            return self._selector
        if strategy == ExtractStrategy.KEYWORD:
            return self._keyword
        if strategy == ExtractStrategy.PATTERN:
            return self._pattern
        if strategy == ExtractStrategy.TABLE:
            return self._table
        if strategy == ExtractStrategy.LLM:
            if self._llm is None:
                raise MissingExtractorDependencyError(
                    "LLM extractor requested, but no llm_client was provided."
                )
            return self._llm

        raise UnsupportedExtractorStrategyError(
            f"No extractor registered for strategy '{strategy.value}'."
        )

    def has(self, strategy: ExtractStrategy) -> bool:
        if strategy == ExtractStrategy.LLM:
            return self._llm is not None

        return strategy in {
            ExtractStrategy.SELECTOR,
            ExtractStrategy.KEYWORD,
            ExtractStrategy.PATTERN,
            ExtractStrategy.TABLE,
        }