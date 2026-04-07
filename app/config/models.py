from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


# ============================================================
# ENUMS
# ============================================================


class ConfigSource(str, Enum):
    MANUAL = "manual"
    GENERATED = "generated"
    REPAIRED = "repaired"
    IMPORTED = "imported"


class ConfigStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    REVIEW_REQUIRED = "review_required"
    INVALID = "invalid"
    DISABLED = "disabled"


class PortalFamily(str, Enum):
    UNKNOWN = "unknown"
    GENERIC_CMS = "generic_cms"
    WORDPRESS = "wordpress"
    DRUPAL = "drupal"
    CUSTOM_PHP = "custom_php"
    SPA = "spa"
    TABLE_HEAVY = "table_heavy"
    THIRD_PARTY_PORTAL = "third_party_portal"


class FetchMode(str, Enum):
    HTTP = "http"
    BROWSER = "browser"


class BrowserWaitUntil(str, Enum):
    LOAD = "load"
    DOMCONTENTLOADED = "domcontentloaded"
    NETWORKIDLE = "networkidle"


class PageType(str, Enum):
    LANDING = "landing"
    CONTENT = "content"
    LISTING = "listing"
    TABLE = "table"
    SEARCH = "search"
    FORM = "form"
    LOGIN = "login"
    PORTAL = "portal"
    FAQ = "faq"
    UNKNOWN = "unknown"


class ContentIntent(str, Enum):
    GENERAL = "general"
    ADMISSIONS = "admissions"
    PROGRAMMES = "programmes"
    DEADLINES = "deadlines"
    HOW_TO_APPLY = "how_to_apply"
    ENTRY_REQUIREMENTS = "entry_requirements"
    TUITION_FEES = "tuition_fees"
    SCHOLARSHIPS = "scholarships"
    CUT_OFF = "cut_off"
    PROFILE = "profile"
    CONTACT = "contact"


class AudienceLevel(str, Enum):
    GENERAL = "general"
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    POSTGRADUATE = "postgraduate"
    INTERNATIONAL = "international"


class ExtractStrategy(str, Enum):
    SELECTOR = "selector"
    PATTERN = "pattern"
    KEYWORD = "keyword"
    TABLE = "table"
    LLM = "llm"


class StoreMode(str, Enum):
    REPLACE = "replace"
    APPEND = "append"
    MERGE = "merge"


class MatchMode(str, Enum):
    CONTAINS = "contains"
    EXACT = "exact"
    REGEX = "regex"


class DiscoveryStrategy(str, Enum):
    SEED_ONLY = "seed_only"
    CRAWL = "crawl"
    SITEMAP = "sitemap"
    SEARCH = "search"
    MIXED = "mixed"


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EntityType(str, Enum):
    UNIVERSITY = "university"
    PORTAL = "portal"
    COURSE = "course"


class RecordMatchStrategy(str, Enum):
    POSITION = "position"
    SELECTOR_GROUP = "selector_group"
    TABLE_ROWS = "table_rows"
    LLM_RECORDS = "llm_records"
    SINGLE_RECORD = "single_record"


# ============================================================
# COMMON / METADATA
# ============================================================


class AuditInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: ConfigSource = ConfigSource.MANUAL
    status: ConfigStatus = ConfigStatus.DRAFT
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    version: int = Field(default=1, ge=1)
    created_by: str | None = None
    updated_by: str | None = None
    notes: str | None = None


class TemplateRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    template_version: int | None = Field(default=None, ge=1)


# ============================================================
# UNIVERSITY SEED / PROFILE
# ============================================================


class UniversityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    university_name: str
    country: str
    root_domains: list[str] = Field(min_length=1)
    seed_urls: list[HttpUrl] = Field(min_length=1)
    portal_family_hint: PortalFamily = PortalFamily.UNKNOWN
    tags: list[str] = Field(default_factory=list)


# ============================================================
# DISCOVERY
# ============================================================


class DiscoveryRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    strategy: DiscoveryStrategy = DiscoveryStrategy.MIXED
    enabled: bool = True

    allowed_domains: list[str] = Field(min_length=1)
    include_url_patterns: list[str] = Field(default_factory=list)
    exclude_url_patterns: list[str] = Field(default_factory=list)
    include_anchor_text: list[str] = Field(default_factory=list)
    exclude_anchor_text: list[str] = Field(default_factory=list)

    max_depth: int = Field(default=2, ge=0, le=10)
    max_pages: int = Field(default=50, ge=1, le=1000)


class PageCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    title: str | None = None
    discovered_by: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    page_type_guess: PageType | None = None
    intent_guess: ContentIntent | None = None
    audience_guess: AudienceLevel | None = None


# ============================================================
# FETCH
# ============================================================


class BrowserConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wait_until: BrowserWaitUntil = BrowserWaitUntil.DOMCONTENTLOADED
    wait_for_selector: str | None = None
    extra_wait_ms: int = Field(default=0, ge=0)
    user_agent: str | None = None
    block_resources: list[str] = Field(default_factory=list)


class FetchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: FetchMode
    timeout_ms: int = Field(default=30_000, ge=1)
    headers: dict[str, str] = Field(default_factory=dict)
    browser: BrowserConfig | None = None

    @model_validator(mode="after")
    def validate_browser_config(self) -> "FetchConfig":
        if self.mode == FetchMode.BROWSER and self.browser is None:
            self.browser = BrowserConfig()
        if self.mode == FetchMode.HTTP and self.browser is not None:
            raise ValueError("browser config is only allowed when mode='browser'.")
        return self


# ============================================================
# PAGE ACTIONS
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


class DismissCookieBannerAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["dismiss_cookie_banner"] = "dismiss_cookie_banner"
    selectors: list[str] = Field(default_factory=list)
    texts: list[str] = Field(default_factory=list)


PageAction = Annotated[
    ClickAction
    | TypeAction
    | WaitForAction
    | SelectOptionAction
    | DismissCookieBannerAction,
    Field(discriminator="type"),
]


# ============================================================
# EXTRACTION CONFIGS
# ============================================================


class SelectorExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(min_length=1)
    attribute: str | None = None
    strip: bool = True


class PatternLabelGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    patterns: list[str] = Field(min_length=1)


class PatternExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(min_length=1)
    labels: list[PatternLabelGroup] = Field(min_length=1)
    case_sensitive: bool = False


class KeywordLabelGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    keywords: list[str] = Field(min_length=1)


class KeywordExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(min_length=1)
    labels: list[KeywordLabelGroup] = Field(min_length=1)
    case_sensitive: bool = False
    match_mode: MatchMode = MatchMode.CONTAINS


class TableExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(min_length=1)
    header_row_index: int = Field(default=0, ge=0)
    infer_headers: bool = True


class LLMExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selectors: list[str] = Field(default_factory=list)
    instruction: str
    output_schema_name: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class ExtractionStep(BaseModel):
    """
    One strategy attempt inside a fallback pipeline.
    """
    model_config = ConfigDict(extra="forbid")

    name: str
    strategy: ExtractStrategy
    stop_on_success: bool = True

    selector_config: SelectorExtractConfig | None = None
    pattern_config: PatternExtractConfig | None = None
    keyword_config: KeywordExtractConfig | None = None
    table_config: TableExtractConfig | None = None
    llm_config: LLMExtractConfig | None = None

    @model_validator(mode="after")
    def validate_strategy_config(self) -> "ExtractionStep":
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
            raise ValueError("ExtractionStep must provide exactly one strategy config.")

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
# ENTITY EXTRACTION
# ============================================================


class EntityFieldPlan(BaseModel):
    """
    How to extract one field for one entity type.
    Example: portal.title, portal.status, course.name
    """
    model_config = ConfigDict(extra="forbid")

    field_name: str
    required: bool = False
    store_mode: StoreMode = StoreMode.REPLACE
    steps: list[ExtractionStep] = Field(min_length=1)


class RecordLocator(BaseModel):
    """
    Defines how to split a page into one or more records.
    This is the big missing piece for multi-portal extraction.
    """
    model_config = ConfigDict(extra="forbid")

    strategy: RecordMatchStrategy = RecordMatchStrategy.SINGLE_RECORD

    # For selector_group:
    container_selectors: list[str] = Field(default_factory=list)

    # For table_rows:
    table_selectors: list[str] = Field(default_factory=list)
    header_row_index: int = Field(default=0, ge=0)

    # For LLM record extraction:
    llm_instruction: str | None = None

    @model_validator(mode="after")
    def validate_strategy(self) -> "RecordLocator":
        if self.strategy == RecordMatchStrategy.SELECTOR_GROUP and not self.container_selectors:
            raise ValueError("selector_group strategy requires container_selectors.")
        if self.strategy == RecordMatchStrategy.TABLE_ROWS and not self.table_selectors:
            raise ValueError("table_rows strategy requires table_selectors.")
        if self.strategy == RecordMatchStrategy.LLM_RECORDS and not self.llm_instruction:
            raise ValueError("llm_records strategy requires llm_instruction.")
        return self


class EntityExtractionPlan(BaseModel):
    """
    Extracts one entity type from a page.
    A page can have multiple entity extraction plans:
    - university metadata
    - many portals
    - many courses
    """
    model_config = ConfigDict(extra="forbid")

    name: str
    entity_type: EntityType
    many: bool = False
    enabled: bool = True

    record_locator: RecordLocator = Field(default_factory=RecordLocator)
    fields: list[EntityFieldPlan] = Field(min_length=1)

    normalizers: list[str] = Field(default_factory=list)
    required_identity_fields: list[str] = Field(default_factory=list)


# ============================================================
# NORMALIZATION
# ============================================================


class NormalizerRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    params: dict[str, Any] = Field(default_factory=dict)


# ============================================================
# VALIDATION EXPECTATIONS
# ============================================================


class RequiredFieldExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    min_items: int | None = Field(default=None, ge=0)
    allow_empty_string: bool = False


class EntityValidationExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: EntityType
    min_records: int | None = Field(default=None, ge=0)
    required_fields: list[RequiredFieldExpectation] = Field(default_factory=list)


class PageValidationExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_fetch: bool = True
    min_text_length: int | None = Field(default=None, ge=0)
    entities: list[EntityValidationExpectation] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: ValidationSeverity
    code: str
    message: str
    field: str | None = None
    entity_type: EntityType | None = None


# ============================================================
# PAGE CONFIG
# ============================================================


class PageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: PageType = PageType.UNKNOWN
    intent: ContentIntent = ContentIntent.GENERAL
    audience: AudienceLevel = AudienceLevel.GENERAL

    url: HttpUrl | None = None
    url_candidates: list[HttpUrl] = Field(default_factory=list)
    canonical: bool = False

    priority: int = Field(default=1, ge=1)
    enabled: bool = True

    template: TemplateRef | None = None
    audit: AuditInfo = Field(default_factory=AuditInfo)

    notes: str | None = None
    fetch: FetchConfig
    actions: list[PageAction] = Field(default_factory=list)

    entity_extractors: list[EntityExtractionPlan] = Field(default_factory=list)
    normalizers: list[NormalizerRef] = Field(default_factory=list)
    validation: PageValidationExpectation | None = None

    @model_validator(mode="after")
    def validate_url_presence(self) -> "PageConfig":
        if self.url is None and not self.url_candidates:
            raise ValueError("PageConfig requires either url or at least one url_candidate.")
        return self

    @property
    def is_browser_page(self) -> bool:
        return self.fetch.mode == FetchMode.BROWSER


# ============================================================
# CONFIG-LEVEL VALIDATION / HEALTH
# ============================================================


class ConfigValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    issues: list[ValidationIssue] = Field(default_factory=list)


# ============================================================
# TOP-LEVEL EXECUTABLE UNIVERSITY CONFIG
# ============================================================


class UniversityScraperConfig(BaseModel):
    """
    Executable scraper config for one university.
    Runtime consumes this config.
    """
    model_config = ConfigDict(extra="forbid")

    profile: UniversityProfile
    audit: AuditInfo = Field(default_factory=AuditInfo)

    discovery: list[DiscoveryRule] = Field(default_factory=list)
    pages: list[PageConfig] = Field(min_length=1)

    last_validation: ConfigValidationReport | None = None

    @model_validator(mode="after")
    def validate_unique_page_names(self) -> "UniversityScraperConfig":
        seen: set[str] = set()
        for page in self.pages:
            if page.name in seen:
                raise ValueError(
                    f"Duplicate page name '{page.name}' in config '{self.profile.id}'."
                )
            seen.add(page.name)
        return self

    def enabled_pages(self) -> list[PageConfig]:
        return sorted(
            (page for page in self.pages if page.enabled),
            key=lambda p: p.priority,
        )

    def canonical_pages(self) -> list[PageConfig]:
        return sorted(
            (page for page in self.pages if page.enabled and page.canonical),
            key=lambda p: p.priority,
        )

    def pages_by_intent(self, intent: ContentIntent) -> list[PageConfig]:
        return sorted(
            (page for page in self.pages if page.intent == intent and page.enabled),
            key=lambda p: p.priority,
        )

    def page_by_name(self, name: str) -> PageConfig:
        for page in self.pages:
            if page.name == name:
                return page
        raise KeyError(f"Page '{name}' not found in config '{self.profile.id}'.")