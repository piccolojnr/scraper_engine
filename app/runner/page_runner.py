from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from pydantic import HttpUrl

from app.config.models import (
    ClickAction,
    DismissCookieBannerAction,
    EntityExtractionPlan,
    EntityFieldPlan,
    ExtractionStep,
    FetchMode,
    PageAction,
    PageConfig,
    RecordMatchStrategy,
    SelectOptionAction,
    TypeAction,
    WaitForAction,
)
from app.extractors.base import RecordScope, StepExtractionRequest
from app.extractors.factory import (
    ExtractorFactory,
    MissingExtractorDependencyError,
    UnsupportedExtractorStrategyError,
)
from app.runtime.context import EntityDraft, PageRuntimeContext
from app.schemas.results import (
    EntityRunStatus,
    ErrorCode,
    PageExtractionResult,
    PageRunStatus,
)


# ============================================================
# FETCH / BROWSER PROTOCOLS
# ============================================================


@dataclass(slots=True, frozen=True)
class FetchResponse:
    url: HttpUrl
    html: str
    text_content: str | None = None


@runtime_checkable
class HttpClient(Protocol):
    async def fetch(
        self,
        *,
        url: HttpUrl | str,
        timeout_ms: int,
        headers: dict[str, str],
    ) -> FetchResponse:
        ...


@runtime_checkable
class BrowserPageHandle(Protocol):
    async def click(self, selector: str) -> None: ...
    async def fill(self, selector: str, value: str) -> None: ...
    async def select_option(self, selector: str, value: str) -> None: ...
    async def wait_for_selector(self, selector: str, timeout_ms: int) -> None: ...
    async def wait_for_text(self, text: str, timeout_ms: int) -> None: ...
    async def content(self) -> str: ...
    async def text_content(self) -> str | None: ...
    async def close(self) -> None: ...
    @property
    def url(self) -> HttpUrl: ...


@runtime_checkable
class BrowserClient(Protocol):
    async def fetch(
        self,
        *,
        url: HttpUrl | str,
        timeout_ms: int,
        headers: dict[str, str],
        wait_for_selector: str | None = None,
    ) -> tuple[FetchResponse, BrowserPageHandle]:
        ...







# ============================================================
# PAGE RUNNER
# ============================================================


class PageRunner:
    """
    Executes one PageConfig against a PageRuntimeContext.

    Responsibilities:
      - fetch page content
      - run optional page actions
      - run entity extractors
      - record success/failure into the page context
      - return final PageExtractionResult
    """

    def __init__(
        self,
        *,
        extractor_factory: ExtractorFactory,
        http_client: HttpClient | None = None,
        browser_client: BrowserClient | None = None,
    ) -> None:
        self.extractor_factory = extractor_factory
        self.http_client = http_client
        self.browser_client = browser_client

    async def run(self, context: PageRuntimeContext) -> PageExtractionResult:
        page = context.page
        context.log(f"Starting page run for '{page.name}' with mode={page.fetch.mode.value}.")

        try:
            await self._fetch_page(context, page)

            if page.actions:
                await self._run_actions(context, page.actions)
                await self._refresh_browser_content(context)

            await self._run_entity_extractors(context, page.entity_extractors)

            status = self._derive_page_status(context)
            context.log(f"Finished page run for '{page.name}' with status={status.value}.")
            return context.to_page_result(status)

        except Exception as exc:
            if context.error is None:
                context.set_error(
                    error_code=ErrorCode.UNKNOWN,
                    message="Unhandled page runner error.",
                    detail=str(exc),
                )

            context.log(f"Unhandled exception during page run: {exc}")
            return context.to_page_result(PageRunStatus.FAILED)

        finally:
            await self._cleanup_browser_resources(context)

    # ========================================================
    # FETCHING
    # ========================================================

    async def _fetch_page(self, context: PageRuntimeContext, page: PageConfig) -> None:
        if page.fetch.mode == FetchMode.HTTP:
            await self._fetch_http(context, page)
            return

        if page.fetch.mode == FetchMode.BROWSER:
            await self._fetch_browser(context, page)
            return

        raise ValueError(f"Unsupported fetch mode: {page.fetch.mode}")

    async def _fetch_http(self, context: PageRuntimeContext, page: PageConfig) -> None:
        if self.http_client is None:
            raise RuntimeError("HTTP fetch requested, but no http_client is configured.")

        target_url = page.url or page.url_candidates[0]
        context.log(f"Fetching page over HTTP: {target_url}")

        try:
            response = await self.http_client.fetch(
                url=target_url,
                timeout_ms=page.fetch.timeout_ms,
                headers=page.fetch.headers,
            )
        except Exception as exc:
            context.set_error(
                error_code=ErrorCode.FETCH_FAILED,
                message="HTTP fetch failed.",
                detail=str(exc),
                suggestion="Check network access, timeout settings, or page URL.",
            )
            raise

        self._apply_fetch_response(context, response)

    async def _fetch_browser(self, context: PageRuntimeContext, page: PageConfig) -> None:
        if self.browser_client is None:
            raise RuntimeError("Browser fetch requested, but no browser_client is configured.")

        target_url = str(page.url or page.url_candidates[0])
        wait_for_selector = page.fetch.browser.wait_for_selector if page.fetch.browser else None

        context.log(f"Fetching page in browser: {target_url}")

        try:
            response, browser_page = await self.browser_client.fetch(
                url=target_url,
                timeout_ms=page.fetch.timeout_ms,
                headers=page.fetch.headers,
                wait_for_selector=wait_for_selector,
            )
        except Exception as exc:
            context.set_error(
                error_code=ErrorCode.FETCH_FAILED,
                message="Browser fetch failed.",
                detail=str(exc),
                suggestion="Check browser runtime, timeout settings, or page selectors.",
            )
            raise

        context.browser_page = browser_page
        self._apply_fetch_response(context, response)

    def _apply_fetch_response(self, context: PageRuntimeContext, response: FetchResponse) -> None:
        context.set_current_url(response.url)
        context.set_html(response.html)
        context.set_text_content(response.text_content)

        if not response.html.strip():
            context.set_error(
                error_code=ErrorCode.EMPTY_CONTENT,
                message="Fetched page returned empty HTML content.",
                suggestion="Check whether the page is blocked, empty, or requires browser rendering.",
            )
            raise ValueError("Fetched page returned empty HTML content.")

    # ========================================================
    # ACTIONS
    # ========================================================

    async def _run_actions(
        self,
        context: PageRuntimeContext,
        actions: list[PageAction],
    ) -> None:
        if context.browser_page is None:
            context.set_error(
                error_code=ErrorCode.ACTION_FAILED,
                message="Page actions require a browser page, but none is available.",
                suggestion="Change fetch mode to 'browser' for this page.",
            )
            raise RuntimeError("Cannot execute page actions without browser_page.")

        context.log(f"Running {len(actions)} page action(s).")

        for action in actions:
            try:
                await self._run_action(context, action)
            except Exception as exc:
                context.set_error(
                    error_code=ErrorCode.ACTION_FAILED,
                    message=f"Action '{action.type}' failed.",
                    detail=str(exc),
                    suggestion="Review page action selectors or browser wait conditions.",
                )
                raise

    async def _run_action(
        self,
        context: PageRuntimeContext,
        action: PageAction,
    ) -> None:
        browser_page = context.browser_page
        assert browser_page is not None

        if isinstance(action, DismissCookieBannerAction):
            for selector in action.selectors:
                try:
                    context.log(f"Attempting cookie dismissal via selector: {selector}")
                    await browser_page.click(selector)
                    return
                except Exception:
                    continue
            # text-based dismissal can be added later
            return

        if isinstance(action, ClickAction):
            if action.selector:
                context.log(f"Clicking selector: {action.selector}")
                await browser_page.click(action.selector)
                return

            if action.text:
                context.log(f"Waiting for text before click attempt: {action.text}")
                await browser_page.wait_for_text(action.text, timeout_ms=10_000)
                raise NotImplementedError(
                    "Text-based click is not implemented yet. Use selector-based click for now."
                )

        elif isinstance(action, TypeAction):
            context.log(f"Typing into selector: {action.selector}")
            await browser_page.fill(action.selector, action.value)
            return

        elif isinstance(action, SelectOptionAction):
            context.log(f"Selecting option on selector: {action.selector}")
            await browser_page.select_option(action.selector, action.value)
            return

        elif isinstance(action, WaitForAction):
            if action.selector:
                context.log(f"Waiting for selector: {action.selector}")
                await browser_page.wait_for_selector(
                    action.selector,
                    timeout_ms=action.timeout_ms,
                )
                return

            if action.text:
                context.log(f"Waiting for text: {action.text}")
                await browser_page.wait_for_text(
                    action.text,
                    timeout_ms=action.timeout_ms,
                )
                return

        raise ValueError(f"Unsupported action type: {action.type}")

    async def _refresh_browser_content(self, context: PageRuntimeContext) -> None:
        if context.browser_page is None:
            return

        context.log("Refreshing browser-rendered content after actions.")
        html = await context.browser_page.content()
        text_content = await context.browser_page.text_content()
        current_url = context.browser_page.url

        context.set_current_url(current_url)
        context.set_html(html)
        context.set_text_content(text_content)

    # ========================================================
    # ENTITY EXTRACTION
    # ========================================================

    async def _run_entity_extractors(
        self,
        context: PageRuntimeContext,
        entity_extractors: list[EntityExtractionPlan],
    ) -> None:
        if not entity_extractors:
            context.log("No entity extractors configured for page.")
            return

        context.log(f"Running {len(entity_extractors)} entity extractor(s).")

        for extractor_plan in entity_extractors:
            if not extractor_plan.enabled:
                context.log(f"Skipping disabled entity extractor '{extractor_plan.name}'.")
                continue

            await self._run_entity_extractor(context, extractor_plan)

    async def _run_entity_extractor(
        self,
        context: PageRuntimeContext,
        plan: EntityExtractionPlan,
    ) -> None:
        context.log(
            f"Running entity extractor '{plan.name}' for entity_type={plan.entity_type.value}."
        )

        record_scopes = await self._locate_records(context, plan)

        if not record_scopes:
            context.log(f"No records located for entity extractor '{plan.name}'.")
            return

        for scope in record_scopes:
            draft = context.create_entity_draft(
                entity_type=plan.entity_type,
                record_index=scope.record_index,
                source_url=context.current_url,
            )
            draft.raw_text_excerpt = scope.text_fragment
            draft.html_fragment = scope.html_fragment

            await self._run_entity_fields(context, draft, plan.fields, scope)

            status = self._derive_entity_status(draft, plan.required_identity_fields)
            context.add_entity_result(draft.to_result(status))

    async def _locate_records(
        self,
        context: PageRuntimeContext,
        plan: EntityExtractionPlan,
    ) -> list[RecordScope]:
        locator = plan.record_locator

        if locator.strategy == RecordMatchStrategy.SINGLE_RECORD:
            return [
                RecordScope(
                    record_index=0,
                    html_fragment=context.html,
                    text_fragment=context.raw_text_excerpt,
                )
            ]

        if locator.strategy == RecordMatchStrategy.SELECTOR_GROUP:
            # Placeholder for now.
            # In production, parse context.html and extract one fragment per matched container.
            # The important thing is the contract shape.
            context.log(
                f"Record locator selector_group using selectors={locator.container_selectors}"
            )
            return [
                RecordScope(
                    record_index=0,
                    html_fragment=context.html,
                    text_fragment=context.raw_text_excerpt,
                    metadata={"container_selectors": locator.container_selectors},
                )
            ]

        if locator.strategy == RecordMatchStrategy.TABLE_ROWS:
            context.log(
                f"Record locator table_rows using selectors={locator.table_selectors}"
            )
            return [
                RecordScope(
                    record_index=0,
                    html_fragment=context.html,
                    text_fragment=context.raw_text_excerpt,
                    metadata={"table_selectors": locator.table_selectors},
                )
            ]

        if locator.strategy == RecordMatchStrategy.LLM_RECORDS:
            context.log("Record locator llm_records selected.")
            return [
                RecordScope(
                    record_index=0,
                    html_fragment=context.html,
                    text_fragment=context.raw_text_excerpt,
                )
            ]

        if locator.strategy == RecordMatchStrategy.POSITION:
            return [
                RecordScope(
                    record_index=0,
                    html_fragment=context.html,
                    text_fragment=context.raw_text_excerpt,
                )
            ]

        context.log(f"Unsupported record locator strategy: {locator.strategy}")
        return []

    async def _run_entity_fields(
        self,
        context: PageRuntimeContext,
        draft: EntityDraft,
        fields: list[EntityFieldPlan],
        scope: RecordScope,
    ) -> None:
        for field_plan in fields:
            await self._run_single_field_plan(context, draft, field_plan, scope)

    async def _run_single_field_plan(
        self,
        context: PageRuntimeContext,
        draft: EntityDraft,
        field_plan: EntityFieldPlan,
        scope: RecordScope,
    ) -> None:
        context.log(
            f"Running field plan '{field_plan.field_name}' "
            f"for entity_type={draft.entity_type.value} record_index={draft.record_index}."
        )

        last_error: str | None = None

        for step in field_plan.steps:
            try:
                success = await self._run_extraction_step(context, draft, field_plan, step, scope)
            except Exception as exc:
                last_error = str(exc)
                draft.add_field_result(
                    field_name=field_plan.field_name,
                    strategy=step.strategy,
                    success=False,
                    error_code=self._error_code_for_strategy(step.strategy),
                    error_message=last_error,
                )
                continue

            if success and step.stop_on_success:
                return

        if field_plan.required and field_plan.field_name not in draft.output_map():
            draft.set_error(
                error_code=ErrorCode.ENTITY_EXTRACTION_FAILED,
                message=f"Required field '{field_plan.field_name}' missing.",
                detail=last_error,
                field_name=field_plan.field_name,
            )

    async def _run_extraction_step(
        self,
        context: PageRuntimeContext,
        draft: EntityDraft,
        field_plan: EntityFieldPlan,
        step: ExtractionStep,
        scope: RecordScope,
    ) -> bool:
        try:
            extractor = self.extractor_factory.get(step.strategy)
        except (MissingExtractorDependencyError, UnsupportedExtractorStrategyError) as exc:
            draft.add_field_result(
                field_name=field_plan.field_name,
                strategy=step.strategy,
                success=False,
                error_code=ErrorCode.EXTRACTION_FAILED,
                error_message=str(exc),
            )
            return False

        # Extractor contract note:
        # This assumes the extractor can work from:
        #   - page context
        #   - extraction step
        #   - optional record scope
        # You will likely need a small adapter in the extractor layer.
        result = await extractor.extract_entity_field(
    context=context,
    request=StepExtractionRequest(
        field_name=field_plan.field_name,
        step=step,
        record_scope=scope,
    ),
)

        if result.success:
            draft.add_field_result(
                field_name=field_plan.field_name,
                strategy=step.strategy,
                success=True,
                value=result.value,
                evidence=result.evidence,
                selector_used=result.selector_used,
                confidence=result.confidence,
            )
            return True

        draft.add_field_result(
            field_name=field_plan.field_name,
            strategy=step.strategy,
            success=False,
            evidence=result.evidence,
            selector_used=result.selector_used,
            error_code=self._error_code_for_strategy(step.strategy),
            error_message=result.error_message,
        )
        return False

    def _derive_entity_status(
        self,
        draft: EntityDraft,
        required_identity_fields: list[str],
    ) -> EntityRunStatus:
        output = draft.output_map()

        if draft.error is not None and not output:
            return EntityRunStatus.FAILED

        missing_required = [field for field in required_identity_fields if not output.get(field)]
        if missing_required and not output:
            return EntityRunStatus.FAILED

        if missing_required:
            return EntityRunStatus.PARTIAL_SUCCESS

        return EntityRunStatus.SUCCESS

    def _error_code_for_strategy(self, strategy: Any) -> ErrorCode:
        strategy_name = getattr(strategy, "value", str(strategy))

        if strategy_name == "selector":
            return ErrorCode.SELECTOR_NOT_FOUND
        if strategy_name == "keyword":
            return ErrorCode.KEYWORD_NOT_MATCHED
        if strategy_name == "pattern":
            return ErrorCode.PATTERN_NOT_MATCHED
        if strategy_name == "table":
            return ErrorCode.TABLE_PARSE_FAILED
        if strategy_name == "llm":
            return ErrorCode.LLM_EXTRACTION_FAILED

        return ErrorCode.EXTRACTION_FAILED

    # ========================================================
    # STATUS DERIVATION
    # ========================================================

    def _derive_page_status(self, context: PageRuntimeContext) -> PageRunStatus:
        if context.error is not None:
            return PageRunStatus.FAILED

        if not context.page.entity_extractors:
            return PageRunStatus.SUCCESS

        if not context.entities:
            return PageRunStatus.FAILED

        if any(entity.status in {EntityRunStatus.SUCCESS, EntityRunStatus.PARTIAL_SUCCESS} for entity in context.entities):
            return PageRunStatus.SUCCESS

        return PageRunStatus.FAILED

    # ========================================================
    # CLEANUP
    # ========================================================

    async def _cleanup_browser_resources(self, context: PageRuntimeContext) -> None:
        if context.browser_page is None:
            return

        try:
            context.log("Cleaning up browser page resources.")
            await context.browser_page.close()
        except Exception as exc:
            context.log(f"Browser resource cleanup failed: {exc}")
        finally:
            context.browser_page = None
