from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.config.models import (
    ClickAction,
    ExtractRule,
    FetchMode,
    PageAction,
    PageConfig,
    SelectOptionAction,
    TypeAction,
    WaitForAction,
)
from app.extractors.factory import (
    ExtractorFactory,
    MissingExtractorDependencyError,
    UnsupportedExtractorStrategyError,
)
from app.runtime.context import PageRuntimeContext
from app.schemas.results import ErrorCode, PageExtractionResult, PageRunStatus


# ============================================================
# FETCH / BROWSER PROTOCOLS
# ============================================================


@dataclass(slots=True, frozen=True)
class FetchResponse:
    url: str
    html: str
    text_content: str | None = None


@runtime_checkable
class HttpClient(Protocol):
    async def fetch(
        self,
        *,
        url: str,
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
    def url(self) -> str: ...


@runtime_checkable
class BrowserClient(Protocol):
    async def fetch(
        self,
        *,
        url: str,
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
      - run extractors for each rule
      - record success/failure into the page context
      - return final PageExtractionResult

    Non-responsibilities:
      - university-level orchestration
      - normalization across pages
      - persistence
      - cache orchestration
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

            await self._run_extract_rules(context, page.extract)

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

        context.log(f"Fetching page over HTTP: {page.url}")

        try:
            response = await self.http_client.fetch(
                url=str(page.url),
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

        context.log(f"Fetching page in browser: {page.url}")

        try:
            response, browser_page = await self.browser_client.fetch(
                url=str(page.url),
                timeout_ms=page.fetch.timeout_ms,
                headers=page.fetch.headers,
                wait_for_selector=page.fetch.wait_for_selector,
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
        assert browser_page is not None  # guarded earlier

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
        """
        Refresh HTML/text after browser actions mutate the DOM.
        """
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
    # EXTRACTION
    # ========================================================

    async def _run_extract_rules(
        self,
        context: PageRuntimeContext,
        rules: list[ExtractRule],
    ) -> None:
        if not rules:
            context.log("No extract rules configured for page.")
            return

        context.log(f"Running {len(rules)} extract rule(s).")

        for rule in rules:
            await self._run_single_extract_rule(context, rule)

    async def _run_single_extract_rule(
        self,
        context: PageRuntimeContext,
        rule: ExtractRule,
    ) -> None:
        context.log(
            f"Running extract rule '{rule.name}' "
            f"(strategy={rule.strategy.value}, output_field={rule.output_field})."
        )

        try:
            extractor = self.extractor_factory.get(rule.strategy)
        except MissingExtractorDependencyError as exc:
            context.add_field_result(
                name=rule.name,
                output_field=rule.output_field,
                strategy=rule.strategy,
                success=False,
                error_code=ErrorCode.EXTRACTION_FAILED,
                error_message=str(exc),
            )

            if rule.required and context.error is None:
                context.set_error(
                    error_code=ErrorCode.EXTRACTION_FAILED,
                    message=f"Required extractor dependency missing for rule '{rule.name}'.",
                    detail=str(exc),
                )
            return

        except UnsupportedExtractorStrategyError as exc:
            context.add_field_result(
                name=rule.name,
                output_field=rule.output_field,
                strategy=rule.strategy,
                success=False,
                error_code=ErrorCode.EXTRACTION_FAILED,
                error_message=str(exc),
            )

            if rule.required and context.error is None:
                context.set_error(
                    error_code=ErrorCode.EXTRACTION_FAILED,
                    message=f"Unsupported extractor strategy for rule '{rule.name}'.",
                    detail=str(exc),
                )
            return

        try:
            extractor.validate_rule(rule)
            result = await extractor.extract(context, rule)

        except Exception as exc:
            context.add_field_result(
                name=rule.name,
                output_field=rule.output_field,
                strategy=rule.strategy,
                success=False,
                error_code=self._error_code_for_strategy(rule.strategy),
                error_message=str(exc),
            )

            if rule.required and context.error is None:
                context.set_error(
                    error_code=ErrorCode.EXTRACTION_FAILED,
                    message=f"Required rule '{rule.name}' failed during extraction.",
                    detail=str(exc),
                    suggestion="Inspect the page structure and update the extract rule.",
                )
            return

        if result.success:
            context.add_field_result(
                name=rule.name,
                output_field=rule.output_field,
                strategy=rule.strategy,
                success=True,
                value=result.value,
                evidence=result.evidence,
                selector_used=result.selector_used,
                confidence=result.confidence,
            )
            return

        context.add_field_result(
            name=rule.name,
            output_field=rule.output_field,
            strategy=rule.strategy,
            success=False,
            evidence=result.evidence,
            selector_used=result.selector_used,
            error_code=self._error_code_for_strategy(rule.strategy),
            error_message=result.error_message,
        )

        if rule.required and context.error is None:
            context.set_error(
                error_code=ErrorCode.EXTRACTION_FAILED,
                message=f"Required rule '{rule.name}' did not produce a value.",
                detail=result.error_message,
                suggestion="Check selectors, page content, or extraction strategy.",
            )

    def _error_code_for_strategy(self, strategy) -> ErrorCode:
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
        """
        Determine final page status.

        Rules:
          - if a page-level error exists -> FAILED
          - if any required extraction rule failed -> FAILED
          - otherwise -> SUCCESS
        """
        if context.error is not None:
            return PageRunStatus.FAILED

        required_rule_names = {
            rule.name
            for rule in context.page.extract
            if rule.required
        }

        if not required_rule_names:
            return PageRunStatus.SUCCESS

        successful_required = {
            result.name
            for result in context.extracted_fields
            if result.success and result.name in required_rule_names
        }

        missing_required = required_rule_names - successful_required
        if missing_required:
            context.log(
                "Required extraction rule(s) missing: "
                + ", ".join(sorted(missing_required))
            )
            return PageRunStatus.FAILED

        return PageRunStatus.SUCCESS

    # ========================================================
    # CLEANUP
    # ========================================================

    async def _cleanup_browser_resources(self, context: PageRuntimeContext) -> None:
        """
        Best-effort cleanup for browser-backed page runs.

        Cleanup failures should not overwrite the real extraction/fetch result.
        """
        if context.browser_page is None:
            return

        try:
            context.log("Cleaning up browser page resources.")
            await context.browser_page.close()
        except Exception as exc:
            context.log(f"Browser resource cleanup failed: {exc}")
        finally:
            context.browser_page = None