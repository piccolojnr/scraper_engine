from __future__ import annotations

import pytest

from app.extractors.utils import (
    all_matching_selectors,
    attribute_list_from_selector,
    contains_any_keyword,
    document_text,
    extract_tables,
    first_matching_keyword_label,
    first_matching_pattern_label,
    first_matching_selector,
    normalize_whitespace,
    single_value_from_selector,
    snippet_around_match,
    snippet_around_regex_match,
    strip_html_comments,
    table_to_rows,
    text_list_from_selector,
)


def test_normalize_whitespace_collapses_and_trims() -> None:
    assert normalize_whitespace("  one \n two\t\tthree  ") == "one two three"


def test_strip_html_comments_removes_comments() -> None:
    html = "A<!-- hidden -->B"
    assert strip_html_comments(html) == "AB"


def test_document_text_extracts_readable_text(sample_soup) -> None:
    text = document_text(sample_soup)
    assert "Admission Info" in text
    assert "BSc Computer Science" in text


def test_first_matching_selector_uses_selector_precedence(sample_soup) -> None:
    selected = first_matching_selector(sample_soup, [".does-not-exist", ".intro", "#programmes li"])
    assert selected is not None
    assert selected.selector == ".intro"
    assert selected.text == "Welcome students ."
    assert "<p class=\"intro\">" in selected.html


def test_first_matching_selector_returns_none_when_no_match(sample_soup) -> None:
    selected = first_matching_selector(sample_soup, [".missing", "#nothing"])
    assert selected is None


def test_all_matching_selectors_returns_all_in_order(sample_soup) -> None:
    matches = all_matching_selectors(sample_soup, [".intro", "#programmes li", ".missing"])
    assert [m.selector for m in matches] == [".intro", "#programmes li"]
    assert matches[0].text == "Welcome students ."
    assert "BSc Computer Science BSc Mathematics" == matches[1].text


def test_text_list_from_selector_returns_values_and_selector(sample_soup) -> None:
    values, selector = text_list_from_selector(sample_soup, [".missing", "#programmes li"])
    assert selector == "#programmes li"
    assert values == ["BSc Computer Science", "BSc Mathematics"]


def test_attribute_list_from_selector_extracts_attribute_values(sample_soup) -> None:
    values, selector = attribute_list_from_selector(sample_soup, [".doc"], "href")
    assert selector == ".doc"
    assert values == ["/docs/prospectus.pdf"]


def test_attribute_list_from_selector_handles_multivalue_attributes(sample_soup) -> None:
    values, selector = attribute_list_from_selector(sample_soup, [".doc"], "class")
    assert selector == ".doc"
    assert values == ["doc"]


def test_single_value_from_selector_reads_text_first(sample_soup) -> None:
    value, selector = single_value_from_selector(sample_soup, [".intro"])
    assert selector == ".intro"
    assert value == "Welcome students ."


def test_single_value_from_selector_reads_attribute(sample_soup) -> None:
    value, selector = single_value_from_selector(sample_soup, [".doc"], attribute="href")
    assert selector == ".doc"
    assert value == "/docs/prospectus.pdf"


def test_contains_any_keyword_for_contains_and_exact() -> None:
    text = "University admission information for 2026"
    assert contains_any_keyword(text, ["admission", "deadline"], match_mode="contains")
    assert contains_any_keyword("  ADMISSION ", ["admission"], case_sensitive=False, match_mode="exact")
    assert not contains_any_keyword("ADMISSION", ["admission"], case_sensitive=True, match_mode="exact")


def test_contains_any_keyword_raises_for_invalid_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported match_mode"):
        contains_any_keyword("abc", ["a"], match_mode="invalid")


def test_first_matching_keyword_label_returns_label_and_keyword() -> None:
    label, keyword = first_matching_keyword_label(
        "Final admission deadline is out",
        [
            ("deadlines", ["deadline", "closing date"]),
            ("fees", ["fee"]),
        ],
    )
    assert label == "deadlines"
    assert keyword == "deadline"


def test_first_matching_pattern_label_returns_label_and_pattern() -> None:
    label, pattern = first_matching_pattern_label(
        "Fees: GHS 1,000 per year",
        [
            ("fees", [r"GHS\s*\d[\d,]*"]),
            ("deadline", [r"\d{1,2}\s+[A-Za-z]{3}"]),
        ],
    )
    assert label == "fees"
    assert pattern == r"GHS\s*\d[\d,]*"


def test_extract_tables_finds_nested_tables(nested_table_soup) -> None:
    tables, selector = extract_tables(nested_table_soup, [".table-container"])
    assert selector == ".table-container"
    assert len(tables) == 1
    assert tables[0].name == "table"


def test_table_to_rows_excludes_header_by_default(sample_soup) -> None:
    table = sample_soup.select_one("#fees")
    assert table is not None
    rows = table_to_rows(table)
    assert rows == [["BSc CS", "1000"], ["BSc Math", "900"]]


def test_table_to_rows_returns_all_rows_when_header_index_out_of_range(sample_soup) -> None:
    table = sample_soup.select_one("#fees")
    assert table is not None
    rows = table_to_rows(table, header_row_index=99)
    assert rows[0] == ["Programme", "Fee"]
    assert rows[-1] == ["BSc Math", "900"]


def test_snippet_around_match_returns_normalized_context() -> None:
    text = "prefix " + ("x" * 30) + "deadline is 30 Sep" + ("y" * 30) + " suffix"
    snippet = snippet_around_match(text, "deadline", radius=12)
    assert snippet is not None
    assert "deadline is 30 Sep" in snippet


def test_snippet_around_match_returns_none_when_missing() -> None:
    assert snippet_around_match("abc", "zzz") is None


def test_snippet_around_regex_match_returns_context() -> None:
    text = "Application opens 1 Jan and closes 30 Sep each year."
    snippet = snippet_around_regex_match(text, r"\d{1,2}\s+[A-Za-z]{3}", radius=8)
    assert snippet is not None
    assert "1 Jan" in snippet


def test_snippet_around_regex_match_returns_none_when_missing() -> None:
    assert snippet_around_regex_match("no dates here", r"\d{4}") is None
