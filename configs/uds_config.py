"""
Scraper configuration for the University for Development Studies (UDS).

This configuration follows the schema defined in ``app.config.models`` and
captures key information about the UDS admissions cycle.  The pages
selected here target official university resources that are accessible
without authentication and contain structured or semi‑structured data
needed by downstream processes.  Where static HTML tables are
available (for programmes), a CSS selector strategy is used.  Where
information is embedded within PDFs or within long narrative text (such
as tuition fee schedules or scholarship announcements), a small
LLM‑powered extractor is employed with an explicit instruction.  The
admissions announcement is treated as the canonical source for the
portal status and start date of the application window; keyword
matching infers whether the portal is open, closed or upcoming.

The mission and vision statements are taken from the university's
"Mission and Vision" page in the About section, capturing the
university’s guiding principles.【86759947653872†L75-L95】  Programme lists are extracted
from the public “All Programmes” page that exposes an HTML table of
undergraduate and postgraduate offerings with programme names and
faculties.【316732538991650†L194-L218】  Tuition fee details are published as PDFs for
each campus; here the Tamale campus summary for the 2023/2024
academic year is used as a representative schedule【843351972940561†L85-L123】.  A
scholarship announcement from the UDS Graduate School detailing the
Educational Pathways International (EPI) scholarship is included to
capture deadlines and contact information for financial aid【214187689285065†L29-L44】.
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
    LLMExtractConfig,
    KeywordLabelGroup,
    PageCategory,
    FetchMode,
)


# ---------------------------------------------------------------------------
# University‑wide configuration
#
# ``id`` is a short, unique identifier for the institution.  The
# ``country`` field assists in grouping universities by region.
CONFIG = UniversityConfig(
    id="uds",
    university_name="University for Development Studies",
    country="Ghana",
    pages=[
        # Admissions announcement page.  UDS advertises the sale of
        # admission forms and e‑voucher costs via an announcement
        # article.  A keyword strategy scans the body text for phrases
        # indicating that applications are open, closed or upcoming.
        PageConfig(
            name="admissions_portal",
            category=PageCategory.ADMISSIONS,
            url=cast(HttpUrl ,"https://uds.edu.gh/announcements/university-for-development-studies-uds-20262027-applications-open-anc"),
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
                                    "applications open",
                                    "applications are open",
                                    "sale of admission forms",
                                    "application forms are now on sale",
                                    "e-vouchers will be available",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "applications closed",
                                    "applications are closed",
                                    "sale of forms closed",
                                    "deadline has passed",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="upcoming",
                                keywords=[
                                    "coming soon",
                                    "opens on",
                                    "will open",
                                ],
                            ),
                        ],
                        case_sensitive=False,
                    ),
                ),
            ],
        ),

        # Programmes page.  The university lists all undergraduate and
        # postgraduate programmes in two HTML tables (IDs ``undertable`` and
        # ``posttable``).  Selecting all anchor tags from both tables
        # captures the programme names for downstream normalisation.
        PageConfig(
            name="programmes",
            category=PageCategory.PROGRAMMES,
            url=cast(HttpUrl ,"https://uds.edu.gh/academics/programmes/"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="programme_list",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="programmes_raw",
                    many=True,
                    required=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["#undertable a", "#posttable a"],
                    ),
                ),
            ],
        ),

        # Tuition fees schedule.  The Tamale campus fee schedule for the
        # 2023/2024 academic year is published as a PDF.  Because the
        # document contains semi‑structured tabular data, an LLM
        # extraction strategy is used.  The instruction asks the model to
        # identify key fee components and their corresponding values.  To
        # simplify integration, the fees are returned as a list of
        # dictionary‑like items (raw strings) that will later be
        # normalised by downstream logic.
        PageConfig(
            name="tuition_fees",
            category=PageCategory.TUITION_FEES,
            url=cast(HttpUrl ,"https://uds.edu.gh/logmein/uploads/documents/2023-2024_ACADEMIC_YEAR_FEES-TAMALE.pdf"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="fees_summary",
                    strategy=ExtractStrategy.LLM,
                    output_field="fees_raw",
                    many=True,
                    required=True,
                    llm_config=LLMExtractConfig(
                        selectors=[],
                        instruction=(
                            "Review the tuition and fee schedule and list each major fee "
                            "component (e.g., Academic Facility User Fee, Other University "
                            "Charges, Departmental/Practical Fees, Development Levy, "
                            "Student Union Dues) along with the corresponding monetary "
                            "amounts for fresh students.  Return each component and its "
                            "amount as a separate item.  If totals are provided, include "
                            "them as well."
                        ),
                    ),
                ),
            ],
        ),

        # Admissions deadlines.  Although the announcement page doubles
        # as the portal status source, the same article contains the
        # start date for the sale of admission forms.  An LLM extractor
        # summarises date mentions (e.g., the opening date of January
        # 16, 2026) and any deadline information for scholarships or
        # forms.  The output is returned as a single string for
        # downstream parsing.
        PageConfig(
            name="deadlines",
            category=PageCategory.DEADLINES,
            url=cast(HttpUrl ,"https://uds.edu.gh/announcements/university-for-development-studies-uds-20262027-applications-open-anc"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="deadlines_info",
                    strategy=ExtractStrategy.LLM,
                    output_field="deadlines_raw",
                    many=False,
                    required=True,
                    llm_config=LLMExtractConfig(
                        selectors=[],
                        instruction=(
                            "From the announcement article, extract any dates or date ranges "
                            "related to the sale of admission forms or application deadlines. "
                            "Include the context around each date so that a human can later "
                            "determine whether it represents an opening date, closing date, "
                            "or other relevant deadline."
                        ),
                    ),
                ),
            ],
        ),

        # Scholarship announcements.  The UDS Graduate School posts
        # scholarship opportunities, such as the Educational Pathways
        # International (EPI) scholarship, on its news page.  A
        # selector extracts the paragraphs from the article, which
        # contain the description, deadline and contact details【214187689285065†L29-L44】.
        PageConfig(
            name="scholarships",
            category=PageCategory.SCHOLARSHIPS,
            url=cast(HttpUrl ,"https://www.gs.uds.edu.gh/news/20242025-academic-year-educational-pathways-international-epi-scholarship-application-opens"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="scholarship_details",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="scholarships_raw",
                    many=False,
                    required=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["p"],
                    ),
                ),
            ],
        ),

        # Mission and vision page.  The mission and vision of UDS are
        # articulated on a dedicated page under the About section.
        # Selecting all paragraphs within the article captures both
        # statements【86759947653872†L75-L95】.  ``many=False`` concatenates the
        # paragraphs into a single string.
        PageConfig(
            name="profile",
            category=PageCategory.PROFILE,
            url=cast(HttpUrl ,"https://uds.edu.gh/about/mission-and-vision"),
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
                    required=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["article p"],
                    ),
                ),
            ],
        ),
    ],
)