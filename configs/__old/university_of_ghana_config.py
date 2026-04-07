"""
Scraper configuration for the University of Ghana.

This configuration follows the schema defined in ``app.config.models`` and
captures key information about admissions, programmes, deadlines, fees,
scholarships and the general profile of the university.  The selectors were
chosen to be as stable as possible by targeting semantic containers such as
``main`` or specific classes that encapsulate the desired content.  Where lists
of items are expected (e.g. programmes, scholarships, deadlines), ``many=True``
is set so the scraper engine returns a list of strings.  Critical fields
needed by downstream processes are marked ``required=True`` (e.g.
``portal_status`` and ``programmes_raw``).
"""

from typing import cast

from pydantic import HttpUrl        

from app.config.models import (
    UniversityConfig,
    PageConfig,
    FetchConfig,
    ExtractRule,
    ExtractStrategy,
    SelectorExtractConfig,
    KeywordExtractConfig,
    TableExtractConfig,
    KeywordLabelGroup,
    PageCategory,
    FetchMode,
)


# ---------------------------------------------------------------------------
# University-wide configuration
#
# ``id`` should remain short and unique (e.g. a two‑letter code).  ``base_url``
# is not strictly required on individual pages because each page defines its
# own absolute URL.  The ``country`` field aids downstream grouping.
CONFIG = UniversityConfig(
    id="ug",
    university_name="University of Ghana",
    country="Ghana",
    pages=[
        # Admissions landing page.  This page announces whether the
        # application portal is open or closed.  A keyword strategy is used
        # because the status text appears in plain language on the page.  The
        # extraction is scoped to ``main`` and similar containers to avoid
        # picking up irrelevant text from the footer.
        PageConfig(
            name="admissions_home",
            category=PageCategory.ADMISSIONS,
            url=cast(HttpUrl, "https://admissions.ug.edu.gh/"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="portal_status",
                    strategy=ExtractStrategy.KEYWORD,
                    output_field="portal_status",
                    required=True,
                    keyword_config=KeywordExtractConfig(
                        selectors=["main", ".content", ".container"],
                        labels=[
                            KeywordLabelGroup(
                                label="open",
                                keywords=[
                                    "admission open",
                                    "admissions are open",
                                    "applications are open",
                                    "admission open",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "admission closed",
                                    "admissions are closed",
                                    "applications are closed",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="upcoming",
                                keywords=[
                                    "coming soon",
                                    "opens",
                                    "will open",
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        ),

        # Deadlines page.  The site presents several admission deadlines as
        # HTML tables.  Using the table extraction strategy ensures that all
        # rows and columns are captured in a structured format.  The
        # ``many=True`` flag indicates that multiple tables may exist on the
        # page (e.g. undergraduate, postgraduate, distance & continuing).
        PageConfig(
            name="deadlines",
            category=PageCategory.DEADLINES,
            url=cast(HttpUrl, "https://admissions.ug.edu.gh/deadlines") ,
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="deadlines_table",
                    strategy=ExtractStrategy.TABLE,
                    output_field="deadlines_raw",
                    many=True,
                    table_config=TableExtractConfig(
                        selectors=["table"],
                        header_row_index=0,
                    ),
                ),
                # A secondary keyword extraction to reflect open/closed status
                # for specific admission types listed on this page.  This
                # extraction is optional (not required) because the main portal
                # status is extracted from the admissions home page.
                ExtractRule(
                    name="deadlines_status",
                    strategy=ExtractStrategy.KEYWORD,
                    output_field="portal_status",
                    required=False,
                    keyword_config=KeywordExtractConfig(
                        selectors=["main"],
                        labels=[
                            KeywordLabelGroup(
                                label="open",
                                keywords=["ADMISSION OPEN", "admission open"],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=["ADMISSION CLOSED", "admission closed"],
                            ),
                        ],
                        case_sensitive=False,
                    ),
                ),
            ],
        ),

        # Programme catalogue.  The University lists all available programmes
        # under collapsible sections.  Each programme entry is represented by
        # a span within a link with the class ``programme-title``.  Selecting
        # the first span yields the programme name.  ``many=True`` instructs
        # the engine to return a list of programme names.
        PageConfig(
            name="programmes",
            category=PageCategory.PROGRAMMES,
            url=cast(HttpUrl, "https://ug.edu.gh/programme-catalogue"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="programmes_list",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="programmes_raw",
                    many=True,
                    required=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            ".programme-title span:first-child",
                            ".programme-title span",
                        ],
                    ),
                ),
            ],
        ),

        # Tuition fees page.  The schedule of fees page contains lists of PDF
        # links organised in ordered and unordered lists within the body of the
        # article.  Extracting all list items provides a raw representation of
        # the different fee categories.  ``many=True`` returns each list item
        # separately.
        PageConfig(
            name="fees",
            category=PageCategory.TUITION_FEES,
            url=cast(HttpUrl, "https://www.ug.edu.gh/aad/schedule-fees"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="fees_items",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="fees_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[".field--name-body li"],
                    ),
                ),
            ],
        ),

        # Scholarships page.  Scholarships offered through the Students Financial
        # Aid Office are presented as cards with headings inside ``h5`` tags.
        # Selecting ``.card h5`` captures each scholarship name.
        PageConfig(
            name="scholarships",
            category=PageCategory.SCHOLARSHIPS,
            url=cast(HttpUrl, "https://apply.ug.edu.gh/finaid/"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="scholarships_list",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="scholarships_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[".card h5", "h5"],
                    ),
                ),
            ],
        ),

        # University profile page.  The overview page under the About UG
        # navigation provides a concise description of the university’s history
        # and mission.  The ``summ-content`` div wraps several paragraphs and
        # lists; capturing the entire container yields the raw profile text.
        PageConfig(
            name="profile",
            category=PageCategory.PROFILE,
            url=cast(HttpUrl, "https://www.ug.edu.gh/about-ug/overview"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="profile_content",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="profile_raw",
                    many=False,
                    selector_config=SelectorExtractConfig(
                        selectors=[".summ-content"],
                    ),
                ),
            ],
        ),
    ],
)
