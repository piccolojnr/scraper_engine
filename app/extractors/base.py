from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol

from app.config.models import ExtractRule
from app.runtime.context import PageRuntimeContext


@dataclass(slots=True, frozen=True)
class ExtractionInput:
    """
    The resolved input a concrete extractor actually works on.

    This is usually not the whole page. It may be:
      - text from a matched selector
      - table HTML/text
      - a narrowed content block
      - full page text as fallback

    This object exists mainly to make extractor execution explicit and to
    support future caching without coupling caching to the extractor itself.
    """

    content: str
    selector_used: str | None = None

    def fingerprint(self) -> str:
        """
        Stable hash of the input content.

        Later, an external extraction executor/cache layer can use this as part
        of a cache key.
        """
        return sha256(self.content.encode("utf-8", errors="ignore")).hexdigest()


@dataclass(slots=True, frozen=True)
class ExtractionMetadata:
    """
    Metadata about one extraction attempt.

    This is not a cache record. It is just enough structured information for an
    outer orchestration layer to decide whether and how to cache.
    """

    extractor_name: str
    extractor_version: str
    rule_name: str
    strategy_name: str
    input_fingerprint: str

    def cache_key(self) -> str:
        """
        Suggested stable key for an external cache service.

        The extractor does not use this directly. It only exposes it.
        """
        return ":".join(
            [
                self.extractor_name,
                self.extractor_version,
                self.rule_name,
                self.strategy_name,
                self.input_fingerprint,
            ]
        )


@dataclass(slots=True)
class ExtractionResult:
    """
    Internal return type from an extractor.

    The page runner or extraction executor will later translate this into
    ExtractedFieldResult on the runtime context.
    """

    success: bool
    value: Any = None
    evidence: str | None = None
    selector_used: str | None = None
    confidence: float | None = None
    error_message: str | None = None
    metadata: ExtractionMetadata | None = None


class Extractor(Protocol):
    """
    Protocol implemented by all concrete extractors.
    """

    name: str
    version: str

    def validate_rule(self, rule: ExtractRule) -> None:
        """
        Raise ValueError if the rule is not compatible with this extractor.
        """
        ...

    async def extract(
        self,
        context: PageRuntimeContext,
        rule: ExtractRule,
    ) -> ExtractionResult:
        """
        Execute extraction for one rule against one page context.
        """
        ...


class BaseExtractor(ABC):
    """
    Shared base class for concrete extractors.

    Responsibilities:
      - validate strategy/rule compatibility
      - provide shared helper methods
      - expose stable extraction metadata for outer layers

    Non-responsibilities:
      - cache reads/writes
      - TTL/invalidation policy
      - persistence
      - runtime context mutation
    """

    name: str = "base"
    version: str = "1"

    @abstractmethod
    def validate_rule(self, rule: ExtractRule) -> None:
        raise NotImplementedError

    @abstractmethod
    async def extract(
        self,
        context: PageRuntimeContext,
        rule: ExtractRule,
    ) -> ExtractionResult:
        raise NotImplementedError

    def build_metadata(
        self,
        *,
        rule: ExtractRule,
        extraction_input: ExtractionInput,
    ) -> ExtractionMetadata:
        """
        Build stable metadata for this extraction attempt.

        A future extraction executor can use this to generate cache keys without
        making cache policy part of the extractor itself.
        """
        return ExtractionMetadata(
            extractor_name=self.name,
            extractor_version=self.version,
            rule_name=rule.name,
            strategy_name=rule.strategy.value,
            input_fingerprint=extraction_input.fingerprint(),
        )

    def make_success_result(
        self,
        *,
        value: Any,
        evidence: str | None = None,
        selector_used: str | None = None,
        confidence: float | None = None,
        metadata: ExtractionMetadata | None = None,
    ) -> ExtractionResult:
        return ExtractionResult(
            success=True,
            value=value,
            evidence=evidence,
            selector_used=selector_used,
            confidence=confidence,
            error_message=None,
            metadata=metadata,
        )

    def make_failure_result(
        self,
        *,
        error_message: str,
        evidence: str | None = None,
        selector_used: str | None = None,
        metadata: ExtractionMetadata | None = None,
    ) -> ExtractionResult:
        return ExtractionResult(
            success=False,
            value=None,
            evidence=evidence,
            selector_used=selector_used,
            confidence=None,
            error_message=error_message,
            metadata=metadata,
        )

    def page_text(self, context: PageRuntimeContext) -> str:
        """
        Return the best available text source from the page context.
        """
        if context.text_content:
            return context.text_content
        if context.html:
            return context.html
        return ""

    def build_input(
        self,
        *,
        content: str,
        selector_used: str | None = None,
    ) -> ExtractionInput:
        return ExtractionInput(
            content=content,
            selector_used=selector_used,
        )