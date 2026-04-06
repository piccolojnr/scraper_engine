
from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


# ============================================================
# ENUMS
# ============================================================


class FetchMode(str, Enum):
    HTTP = "http"
    BROWSER = "browser"


class PageCategory(str, Enum):
    MAIN = "main"
    ADMISSIONS = "admissions"
    PROFILE = "profile"
    DEADLINES = "deadlines"
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    HOW_TO_APPLY = "how_to_apply"
    ENTRY_REQUIREMENTS = "entry_requirements"
    PROGRAMMES = "programmes"
    CUT_OFF = "cut_off"
    SCHOLARSHIPS = "scholarships"
    TUITION_FEES = "tuition_fees"
    GENERAL = "general"


class ExtractStrategy(str, Enum):
    SELECTOR = "selector"
    PATTERN = "pattern"
    KEYWORD = "keyword"
    TABLE = "table"
    LLM = "llm"


class StoreMode(str, Enum):
    REPLACE = "replace"
    APPEND = "append"


# ============================================================
# FETCH
# ============================================================


class FetchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: FetchMode
    timeout_ms: int = Field(default=30_000, ge=1)
    headers: dict[str, str] = Field(default_factory=dict)
    wait_for_selector: str | None = None


# ============================================================
# PAGE ACTIONS
# Optional helpers for interactive pages
# ============================================================


class ClickAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["click"] = "click"
    selector: str | None = None
    text: str | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "ClickAction":
        if not self.selector and not self.text:
            raise ValueError("ClickAction requires either 'selector' or 'text'.")
        return self


class TypeAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["type"] = "type"
    selector: str
    value: str


class WaitForAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["wait_for"] = "wait_for"
    selector: str | None = None
    text: str | None = None
    timeout_ms: int = Field(default=10_000, ge=1)

    @model_validator(mode="after")
    def validate_target(self) -> "WaitForAction":
        if not self.selector and not self.text:
            raise ValueError("WaitForAction requires either 'selector' or 'text'.")
        return self


class SelectOptionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["select_option"] = "select_option"
    selector: str
    value: str


PageAction = Annotated[
    ClickAction | TypeAction | WaitForAction | SelectOptionAction,
    Field(discriminator="type"),
]


# ============================================================
# EXTRACTION CONFIGS
# ============================================================


class SelectorExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(default_factory=list, min_length=1)
    attribute: str | None = None


class PatternLabelGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    patterns: list[str] = Field(min_length=1)


class PatternExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(default_factory=list, min_length=1)
    labels: list[PatternLabelGroup] = Field(default_factory=list, min_length=1)
    case_sensitive: bool = False


class KeywordLabelGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    keywords: list[str] = Field(min_length=1)


class KeywordExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(default_factory=list, min_length=1)
    labels: list[KeywordLabelGroup] = Field(default_factory=list, min_length=1)
    case_sensitive: bool = False
    match_mode: Literal["contains", "exact"] = "contains"


class TableExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(default_factory=list, min_length=1)
    header_row_index: int = Field(default=0, ge=0)


class LLMExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(default_factory=list, min_length=1)
    instruction: str
    output_schema_name: str | None = None


class ExtractRule(BaseModel):
    """
    One extraction rule for one page.

    Exactly one strategy-specific config must be provided, and it must match
    the selected strategy.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    strategy: ExtractStrategy
    output_field: str
    many: bool = False
    required: bool = False
    store_mode: StoreMode = StoreMode.REPLACE

    selector_config: SelectorExtractConfig | None = None
    pattern_config: PatternExtractConfig | None = None
    keyword_config: KeywordExtractConfig | None = None
    table_config: TableExtractConfig | None = None
    llm_config: LLMExtractConfig | None = None

    @model_validator(mode="after")
    def validate_strategy_config(self) -> "ExtractRule":
        config_count = sum(
            cfg is not None
            for cfg in (
                self.selector_config,
                self.pattern_config,
                self.keyword_config,
                self.table_config,
                self.llm_config,
            )
        )

        if config_count != 1:
            raise ValueError(
                "ExtractRule must provide exactly one strategy config."
            )

        if self.strategy == ExtractStrategy.SELECTOR and self.selector_config is None:
            raise ValueError("strategy='selector' requires selector_config.")

        if self.strategy == ExtractStrategy.PATTERN and self.pattern_config is None:
            raise ValueError("strategy='pattern' requires pattern_config.")

        if self.strategy == ExtractStrategy.KEYWORD and self.keyword_config is None:
            raise ValueError("strategy='keyword' requires keyword_config.")

        if self.strategy == ExtractStrategy.TABLE and self.table_config is None:
            raise ValueError("strategy='table' requires table_config.")

        if self.strategy == ExtractStrategy.LLM and self.llm_config is None:
            raise ValueError("strategy='llm' requires llm_config.")

        return self


# ============================================================
# PAGE + UNIVERSITY CONFIG
# ============================================================


class PageConfig(BaseModel):
    """Configuration for one page to scrape, including how to fetch and extract data."""
    model_config = ConfigDict(extra="forbid")

    name: str
    category: PageCategory
    url: HttpUrl
    priority: int = Field(default=1, ge=1)
    notes: str | None = None
    fetch: FetchConfig
    actions: list[PageAction] = Field(default_factory=list)
    extract: list[ExtractRule] = Field(default_factory=list)
    normalizer: str | None = None
    enabled: bool = True

    @property
    def is_browser_page(self) -> bool:
        return self.fetch.mode == FetchMode.BROWSER


class UniversityConfig(BaseModel):
    """Configuration for one university, including all pages to scrape and how."""
    model_config = ConfigDict(extra="forbid")

    id: str
    university_name: str
    country: str
    pages: list[PageConfig] = Field(min_length=1)

    # Optional seeded/manual values
    seeded_fee_info: dict | None = None
    seeded_apply_info: dict | None = None
    seeded_profile: dict | None = None

    @model_validator(mode="after")
    def validate_unique_page_names(self) -> "UniversityConfig":
        seen: set[str] = set()

        for page in self.pages:
            if page.name in seen:
                raise ValueError(f"Duplicate page name '{page.name}' in config '{self.id}'.")
            seen.add(page.name)

        return self

    def enabled_pages(self) -> list[PageConfig]:
        return sorted(
            (page for page in self.pages if page.enabled),
            key=lambda p: p.priority,
        )

    def page_by_name(self, name: str) -> PageConfig:
        for page in self.pages:
            if page.name == name:
                return page
        raise KeyError(f"Page '{name}' not found in config '{self.id}'.")

    def pages_by_category(self, category: PageCategory) -> list[PageConfig]:
        return sorted(
            (page for page in self.pages if page.category == category and page.enabled),
            key=lambda p: p.priority,
        )