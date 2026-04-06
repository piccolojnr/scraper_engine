"""
Scraper configuration for Kwame Nkrumah University of Science and Technology (KNUST).

This configuration follows the schema defined in ``app.config.models`` and
captures key information about the KNUST admissions portal, available
programmes, tuition fee schedules, scholarship offerings and the university’s
mission and vision.  The selectors were selected to target semantic
containers (e.g. the ``buttons-container`` on the admissions portal,
``table.table-striped`` on the fees page, and specific list classes on the
scholarship page) to make the scraper resilient against minor HTML
rearrangements.  Where lists of items are expected (e.g. programme
categories or scholarships), ``many=True`` is set so the scraper engine
returns a list of strings.  Critical fields needed by downstream processes
are marked ``required=True`` (e.g. ``portal_status`` and ``programmes_raw``).

The admissions portal at ``https://apps.knust.edu.gh/admissions/apply``
provides the gateway for applicants.  While it does not explicitly state
“open” or “closed” in a single banner, keyword matching over the body
content still allows the scraper to infer the portal status: phrases such
as “admissions are open” or “applications are closed” will trigger the
appropriate label.  The “Available Programmes” section lists links to
regular and distance programmes for undergraduate, postgraduate and diploma
levels; these links are captured via a CSS selector on the portal’s
``buttons-container``.  Tuition fee schedules are published as a table of
PDF links on the main KNUST site; extracting the anchor tags provides
categories such as “Regular Freshers”, “Postgraduates Continuing” etc.
Scholarships offered by the CARISCA project are presented in a list on the
CARISCA site; these are captured via the ``elementor-icon-list-items``
selector.  Finally, the university’s strategic mandate page contains
paragraphs detailing the vision and mission statements and core values.
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
# ``id`` is a short, unique identifier for the institution.  ``base_url`` is
# optional on individual pages because each page defines its own absolute
# URL.  The ``country`` field aids downstream grouping.
CONFIG = UniversityConfig(
    id="kn",
    university_name="Kwame Nkrumah University of Science and Technology",
    country="Ghana",
    pages=[
        # Admissions portal.  This page contains high‑level instructions for
        # prospective applicants.  A keyword strategy is used to infer
        # whether the portal is currently accepting applications.  The
        # extraction is scoped to the ``body`` element to maximise the
        # likelihood of capturing status phrases wherever they appear.
        PageConfig(
            name="admissions_portal",
            category=PageCategory.ADMISSIONS,
            url=cast(HttpUrl ,"https://apps.knust.edu.gh/admissions/apply"),
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
                        selectors=["body"],
                        labels=[
                            KeywordLabelGroup(
                                label="open",
                                keywords=[
                                    "admission open",
                                    "admissions are open",
                                    "applications are open",
                                    "sale of forms open",
                                    "purchase e-voucher",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "admission closed",
                                    "admissions are closed",
                                    "applications are closed",
                                    "sale of forms closed",
                                    "deadline has passed",
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
                        case_sensitive=False,
                    ),
                ),
            ],
        ),

        # Programmes page.  The admissions portal lists programme categories
        # (regular, distance, etc.) under the ``buttons-container``.  Each
        # anchor tag corresponds to a programme category or document (PDF).
        # Selecting ``.buttons-container a`` captures all of these links.
        PageConfig(
            name="programmes",
            category=PageCategory.PROGRAMMES,
            url=cast(HttpUrl ,"https://apps.knust.edu.gh/admissions/apply#programmes"),
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
                        selectors=[".buttons-container a"],
                    ),
                ),
            ],
        ),

        # Tuition fees page.  The university publishes a schedule of fees
        # categories as a table of PDF links on its main site.  Extracting
        # the anchors within the ``table.table-striped`` returns each fee
        # category (e.g. Regular Freshers, Postgraduates Continuing).  The
        # ``many=True`` flag ensures that every cell link is returned.
        PageConfig(
            name="fees",
            category=PageCategory.TUITION_FEES,
            url=cast(HttpUrl ,"https://www.knust.edu.gh/academics/academics-fees/fees-schedule-20252026-academic-year"),
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
                        selectors=["table.table-striped a"],
                    ),
                ),
            ],
        ),

        # Scholarships page.  CARISCA scholarships are detailed on a dedicated
        # page hosted on the CARISCA sub‑site.  The programmes covered by the
        # scholarship are listed within ``ul.elementor-icon-list-items``.  Each
        # list item contains the name of a programme; extracting them with
        # ``many=True`` produces a list of scholarship programmes.
        PageConfig(
            name="scholarships",
            category=PageCategory.SCHOLARSHIPS,
            url=cast(HttpUrl ,"https://carisca.knust.edu.gh/scholarship/"),
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
                        selectors=["ul.elementor-icon-list-items li"],
                    ),
                ),
            ],
        ),

        # University profile page.  The strategic mandate page outlines the
        # mandate, vision, mission and core values of the university.  The
        # content is contained in paragraphs following heading tags; selecting
        # ``article p`` captures each paragraph.  Since the profile is
        # narrative text, ``many=False`` is set to return a single string
        # containing all paragraphs concatenated.
        PageConfig(
            name="profile",
            category=PageCategory.PROFILE,
            url=cast(HttpUrl ,"https://www.knust.edu.gh/about/knust/mandate"),
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
                        selectors=["article p"],
                    ),
                ),
            ],
        ),
    ],
)