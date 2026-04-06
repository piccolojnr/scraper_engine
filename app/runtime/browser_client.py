from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from playwright.async_api import (
    Browser,
    Page,
    Playwright,
    async_playwright,
)

from app.extractors.utils import document_text, parse_html
from app.runner.page_runner import BrowserPageHandle, FetchResponse


@dataclass(slots=True)
class PlaywrightPageHandle(BrowserPageHandle):
    """
    Thin adapter over a Playwright Page so the runner depends on our
    protocol shape instead of Playwright directly.
    """

    page: Page

    async def click(self, selector: str) -> None:
        await self.page.click(selector)

    async def fill(self, selector: str, value: str) -> None:
        await self.page.fill(selector, value)

    async def select_option(self, selector: str, value: str) -> None:
        await self.page.select_option(selector, value)

    async def wait_for_selector(self, selector: str, timeout_ms: int) -> None:
        await self.page.wait_for_selector(selector, timeout=timeout_ms)

    async def wait_for_text(self, text: str, timeout_ms: int) -> None:
        await self.page.get_by_text(text).first.wait_for(timeout=timeout_ms)

    async def content(self) -> str:
        return await self.page.content()

    async def text_content(self) -> str | None:
        html = await self.page.content()
        if not html.strip():
            return None

        soup = parse_html(html)
        text = document_text(soup)
        return text or None

    async def close(self) -> None:
        """
        Close the owning browser context to fully clean up this page run.
        """
        await self.page.context.close()

    @property
    def url(self) -> str:
        return self.page.url


@dataclass(slots=True)
class PlaywrightBrowserClient:
    """
    Basic browser client for JS-rendered or interactive pages.

    Notes:
      - Uses a single shared browser instance
      - Creates a fresh context + page for each fetch
      - Returns a page handle so the runner can execute actions
      - Does not implement caching yet
    """

    headless: bool = True
    browser_type: str = "chromium"
    default_navigation_wait_until: Optional[
            Literal["commit", "domcontentloaded", "load", "networkidle", None]
        
    ] = "domcontentloaded"
    default_headers: dict[str, str] = field(default_factory=dict)

    _playwright: Playwright | None = field(default=None, init=False, repr=False)
    _browser: Browser | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> "PlaywrightBrowserClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        if self._playwright is not None and self._browser is not None:
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._launch_browser(self._playwright)

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def fetch(
        self,
        *,
        url: str,
        timeout_ms: int,
        headers: dict[str, str],
        wait_for_selector: str | None = None,
    ) -> tuple[FetchResponse, BrowserPageHandle]:
        """
        Open a browser page, navigate, optionally wait for a selector, and
        return the current HTML/text plus a page handle for further actions.

        The caller is responsible for using the returned handle during the page
        run. The page handle owns the browser context lifecycle via close().
        """
        browser = await self._get_browser()

        merged_headers = dict(self.default_headers)
        merged_headers.update(headers)

        browser_context = await browser.new_context(
            extra_http_headers=merged_headers or None,
        )

        page = await browser_context.new_page()
        page.set_default_timeout(timeout_ms)

        await page.goto(
            url,
            wait_until=self.default_navigation_wait_until,
            timeout=timeout_ms,
        )

        if wait_for_selector:
            await page.wait_for_selector(wait_for_selector, timeout=timeout_ms)

        html = await page.content()
        text_content = self._extract_text_content(html)

        handle = PlaywrightPageHandle(page=page)

        return (
            FetchResponse(
                url=page.url,
                html=html,
                text_content=text_content,
            ),
            handle,
        )

    async def _get_browser(self) -> Browser:
        if self._browser is None:
            await self.start()

        assert self._browser is not None
        return self._browser

    async def _launch_browser(self, playwright: Playwright) -> Browser:
        browser_type = self.browser_type.lower()

        if browser_type == "chromium":
            return await playwright.chromium.launch(headless=self.headless)

        if browser_type == "firefox":
            return await playwright.firefox.launch(headless=self.headless)

        if browser_type == "webkit":
            return await playwright.webkit.launch(headless=self.headless)

        raise ValueError(
            f"Unsupported browser_type '{self.browser_type}'. "
            "Expected one of: chromium, firefox, webkit."
        )

    def _extract_text_content(self, html: str) -> str | None:
        if not html.strip():
            return None

        soup = parse_html(html)
        text = document_text(soup)
        return text or None