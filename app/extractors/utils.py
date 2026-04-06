from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup, Tag


WHITESPACE_RE = re.compile(r"\s+")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(slots=True, frozen=True)
class SelectedContent:
    """
    Result of resolving one selector against parsed HTML.
    """

    selector: str
    text: str
    html: str


def parse_html(html: str) -> BeautifulSoup:
    """
    Parse raw HTML into a BeautifulSoup document.
    """
    return BeautifulSoup(html, "html.parser")


def normalize_whitespace(value: str) -> str:
    """
    Collapse repeated whitespace and trim.
    """
    return WHITESPACE_RE.sub(" ", value).strip()


def strip_html_comments(html: str) -> str:
    """
    Remove HTML comments from a document string.
    """
    return HTML_COMMENT_RE.sub("", html)


def extract_text_from_tag(tag: Tag) -> str:
    """
    Extract readable text from a tag with normalized whitespace.
    """
    return normalize_whitespace(tag.get_text(" ", strip=True))


def extract_html_from_tag(tag: Tag) -> str:
    """
    Serialize a tag back to HTML.
    """
    return str(tag)


def document_text(soup: BeautifulSoup) -> str:
    """
    Extract normalized text from the whole document.
    """
    return normalize_whitespace(soup.get_text(" ", strip=True))


def first_matching_selector(
    soup: BeautifulSoup,
    selectors: Iterable[str],
) -> SelectedContent | None:
    """
    Return the first selector that matches at least one element.

    The returned text/html are aggregated across all matched elements for that selector.
    """
    for selector in selectors:
        elements = soup.select(selector)
        if not elements:
            continue

        text_parts: list[str] = []
        html_parts: list[str] = []

        for element in elements:
            text = extract_text_from_tag(element)
            html = extract_html_from_tag(element)

            if text:
                text_parts.append(text)
            if html:
                html_parts.append(html)

        combined_text = normalize_whitespace(" ".join(text_parts))
        combined_html = "\n".join(html_parts).strip()

        return SelectedContent(
            selector=selector,
            text=combined_text,
            html=combined_html,
        )

    return None


def all_matching_selectors(
    soup: BeautifulSoup,
    selectors: Iterable[str],
) -> list[SelectedContent]:
    """
    Return aggregated content for every selector that matches.
    """
    matches: list[SelectedContent] = []

    for selector in selectors:
        elements = soup.select(selector)
        if not elements:
            continue

        text_parts: list[str] = []
        html_parts: list[str] = []

        for element in elements:
            text = extract_text_from_tag(element)
            html = extract_html_from_tag(element)

            if text:
                text_parts.append(text)
            if html:
                html_parts.append(html)

        matches.append(
            SelectedContent(
                selector=selector,
                text=normalize_whitespace(" ".join(text_parts)),
                html="\n".join(html_parts).strip(),
            )
        )

    return matches


def text_list_from_selector(
    soup: BeautifulSoup,
    selectors: Iterable[str],
) -> tuple[list[str], str | None]:
    """
    Return a flat list of normalized text entries from the first selector that matches.

    Useful for selector-based list extraction like:
      - programme lists
      - bullet points
      - paragraphs
    """
    for selector in selectors:
        elements = soup.select(selector)
        if not elements:
            continue

        values: list[str] = []
        for element in elements:
            text = extract_text_from_tag(element)
            if text:
                values.append(text)

        if values:
            return values, selector

    return [], None


def attribute_list_from_selector(
    soup: BeautifulSoup,
    selectors: Iterable[str],
    attribute: str,
) -> tuple[list[str], str | None]:
    """
    Return attribute values from the first selector that matches.

    Useful for href/src/data-* extraction.
    """
    for selector in selectors:
        elements = soup.select(selector)
        if not elements:
            continue

        values: list[str] = []
        for element in elements:
            raw = element.get(attribute)
            if raw is None:
                continue

            if isinstance(raw, list):
                values.extend(normalize_whitespace(str(v)) for v in raw if str(v).strip())
            else:
                value = normalize_whitespace(str(raw))
                if value:
                    values.append(value)

        if values:
            return values, selector

    return [], None


def single_value_from_selector(
    soup: BeautifulSoup,
    selectors: Iterable[str],
    attribute: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Return one value from the first selector that matches.

    If attribute is provided, returns the first non-empty attribute value.
    Otherwise returns the normalized text content.
    """
    for selector in selectors:
        elements = soup.select(selector)
        if not elements:
            continue

        for element in elements:
            if attribute:
                raw = element.get(attribute)
                if raw is None:
                    continue

                if isinstance(raw, list):
                    joined = normalize_whitespace(" ".join(str(v) for v in raw if str(v).strip()))
                    if joined:
                        return joined, selector
                else:
                    value = normalize_whitespace(str(raw))
                    if value:
                        return value, selector
            else:
                text = extract_text_from_tag(element)
                if text:
                    return text, selector

    return None, None


def contains_any_keyword(
    text: str,
    keywords: Iterable[str],
    *,
    case_sensitive: bool = False,
    match_mode: str = "contains",
) -> bool:
    """
    Check whether text matches any keyword.

    match_mode:
      - contains: keyword appears anywhere in text
      - exact: normalized text equals keyword
    """
    haystack = normalize_whitespace(text)
    if not case_sensitive:
        haystack = haystack.lower()

    for keyword in keywords:
        needle = normalize_whitespace(keyword)
        if not case_sensitive:
            needle = needle.lower()

        if match_mode == "contains":
            if needle in haystack:
                return True
        elif match_mode == "exact":
            if needle == haystack:
                return True
        else:
            raise ValueError(f"Unsupported match_mode: {match_mode}")

    return False


def first_matching_keyword_label(
    text: str,
    labels: Iterable[tuple[str, list[str]]],
    *,
    case_sensitive: bool = False,
    match_mode: str = "contains",
) -> tuple[str | None, str | None]:
    """
    Return the first matching label and the keyword that matched.

    labels is an iterable of:
        (label, [keywords...])
    """
    haystack = normalize_whitespace(text)
    compare_text = haystack if case_sensitive else haystack.lower()

    for label, keywords in labels:
        for keyword in keywords:
            candidate = normalize_whitespace(keyword)
            compare_candidate = candidate if case_sensitive else candidate.lower()

            if match_mode == "contains":
                if compare_candidate in compare_text:
                    return label, keyword
            elif match_mode == "exact":
                if compare_candidate == compare_text:
                    return label, keyword
            else:
                raise ValueError(f"Unsupported match_mode: {match_mode}")

    return None, None


def first_matching_pattern_label(
    text: str,
    labels: Iterable[tuple[str, list[str]]],
    *,
    case_sensitive: bool = False,
) -> tuple[str | None, str | None]:
    """
    Return the first matching label and regex/text pattern that matched.

    Patterns are evaluated with re.search.
    """
    flags = 0 if case_sensitive else re.IGNORECASE

    for label, patterns in labels:
        for pattern in patterns:
            if re.search(pattern, text, flags=flags):
                return label, pattern

    return None, None


def extract_tables(
    soup: BeautifulSoup,
    selectors: Iterable[str],
) -> tuple[list[Tag], str | None]:
    """
    Return all matched table tags from the first selector that yields results.
    """
    for selector in selectors:
        elements = soup.select(selector)
        tables = [el for el in elements if el.name == "table"]

        if tables:
            return tables, selector

        # If selector matched wrapper nodes, also look for nested tables.
        nested_tables: list[Tag] = []
        for el in elements:
            nested_tables.extend(el.select("table"))

        if nested_tables:
            return nested_tables, selector

    return [], None


def table_to_rows(table: Tag, header_row_index: int = 0) -> list[list[str]]:
    """
    Convert an HTML table into raw row/cell text.

    This returns rows only. Header interpretation is left to the caller.
    """
    rows: list[list[str]] = []

    for tr in table.select("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue

        row = [extract_text_from_tag(cell) for cell in cells]
        if any(cell for cell in row):
            rows.append(row)

    if not rows:
        return []

    # header_row_index is accepted here for interface consistency,
    # but row shaping is intentionally left simple for v1.
    return rows


def snippet_around_match(
    text: str,
    needle: str,
    *,
    radius: int = 120,
    case_sensitive: bool = False,
) -> str | None:
    """
    Return a short snippet around the first occurrence of a substring.
    """
    haystack = text if case_sensitive else text.lower()
    target = needle if case_sensitive else needle.lower()

    index = haystack.find(target)
    if index == -1:
        return None

    start = max(0, index - radius)
    end = min(len(text), index + len(needle) + radius)
    return normalize_whitespace(text[start:end])


def snippet_around_regex_match(
    text: str,
    pattern: str,
    *,
    radius: int = 120,
    case_sensitive: bool = False,
) -> str | None:
    """
    Return a short snippet around the first regex match.
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    match = re.search(pattern, text, flags=flags)
    if not match:
        return None

    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return normalize_whitespace(text[start:end])