from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.extractors.utils import document_text, parse_html
from app.runner.page_runner import FetchResponse


@dataclass(slots=True)
class SimpleHttpClient:
    """
    Basic async HTTP client for fetching static pages.

    Notes:
      - Intended for pages configured with fetch.mode == HTTP
      - Returns raw HTML plus a normalized text extraction
      - Does not perform browser rendering
      - Does not implement caching yet
    """

    default_headers: dict[str, str] = field(default_factory=dict)
    follow_redirects: bool = True
    verify_ssl: bool = True

    _client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    async def __aenter__(self) -> "SimpleHttpClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        """
        Initialize the underlying httpx client if needed.
        """
        if self._client is not None:
            return

        self._client = httpx.AsyncClient(
            follow_redirects=self.follow_redirects,
            verify=self.verify_ssl,
            headers=self.default_headers,
        )

    async def close(self) -> None:
        """
        Close the underlying httpx client.
        """
        if self._client is None:
            return

        await self._client.aclose()
        self._client = None

    async def fetch(
        self,
        *,
        url: str,
        timeout_ms: int,
        headers: dict[str, str],
    ) -> FetchResponse:
        """
        Fetch a URL over HTTP and return HTML + extracted text.

        Raises:
          httpx.HTTPError subclasses for network / HTTP issues.
        """
        client = await self._get_client()

        merged_headers = dict(self.default_headers)
        merged_headers.update(headers)

        timeout = httpx.Timeout(timeout_ms / 1000)

        response = await client.get(
            url,
            headers=merged_headers,
            timeout=timeout,
        )
        response.raise_for_status()

        html = response.text
        text_content = self._extract_text_content(html)

        return FetchResponse(
            url=str(response.url),
            html=html,
            text_content=text_content,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.start()

        assert self._client is not None
        return self._client

    def _extract_text_content(self, html: str) -> str | None:
        """
        Convert fetched HTML into normalized document text.
        """
        if not html.strip():
            return None

        soup = parse_html(html)
        text = document_text(soup)
        return text or None