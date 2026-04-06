"""
Scraper configuration for the University of Ibadan (UI).

This configuration follows the schema defined in ``app.config.models`` and
captures admissions status, programme offerings and institutional profile
information from publicly accessible pages on the University of Ibadan
website.  Where possible the selectors are scoped to specific table or
paragraph elements to extract structured lists (e.g. undergraduate
programmes), while keyword rules are employed to infer portal status from
announcement text.  During research only a limited set of scrapeable
resources were discovered: the acceptance fee announcement which specifies
portal opening and closing dates, a legacy page listing approved
undergraduate programmes by faculty, and the official vision and mission
page describing the university’s purpose.  Tuition schedules and
scholarship details were either unavailable or embedded in inaccessible
PDFs, so they are omitted from this configuration.

Evidence used to build this configuration:

* The acceptance fee announcement for the 2025/2026 academic session on
  the university news site states that the admission portal will open on
  Monday, 10 November, 2025 and close on Friday, 05 December, 2025, and
  emphasises that there will be no extension of the deadline【221338296615454†L123-L133】.
  This page also specifies that candidates must pay a non‑refundable
  acceptance fee of N50,000 via the admission portal【221338296615454†L123-L133】.

* A page titled “UNIVERSITY OF IBADAN, IBADAN, NIGERIA” lists approved
  undergraduate degree programmes for the 2013/2014 academic session.
  The HTML contains a table where each programme is defined within
  `<p>` elements of table cells.  Example rows include Medicine & Surgery,
  Dentistry, Nursing Science, Biochemistry, Agricultural Economics,
  Computer Science, Law and many others【492479249389226†L539-L577】【492479249389226†L594-L643】
  【492479249389226†L756-L867】【492479249389226†L972-L1016】.

* The official vision and mission page declares that the University of
  Ibadan’s vision is “To be a world‑class institution for academic
  excellence geared towards meeting societal needs” and lists mission
  statements such as expanding the frontiers of knowledge and producing
  graduates who are worthy in character【283930899461719†L120-L133】.

"""

from app.config.models import (
    UniversityConfig,
    PageConfig,
    FetchConfig,
    ExtractRule,
    ExtractStrategy,
    SelectorExtractConfig,
    KeywordExtractConfig,
    KeywordLabelGroup,
    PageCategory,
    FetchMode,
)


# ---------------------------------------------------------------------------
# University configuration
#
# ``id`` is a short, unique identifier for the institution.  ``university_name``
# provides the human‑readable name and ``country`` notes the location.
CONFIG = UniversityConfig(
    id="ui",
    university_name="University of Ibadan",
    country="Nigeria",
    pages=[
        # Admissions portal / announcement page.  The acceptance fee news
        # article is used as a proxy for the admissions portal because it
        # contains explicit opening and closing dates for the admission
        # portal.  A keyword extraction strategy scans the entire body
        # text for phrases indicating whether admissions are open, closed
        # or upcoming.  In addition, we extract all paragraph text to
        # preserve deadline information.
        PageConfig(
            name="admissions_portal",
            category=PageCategory.ADMISSIONS,
            url=(
                "https://ui.edu.ng/news/utme-direct-entry-acceptance-fee-payment-"
                "prospective-candidates-20252026-admission-exercise"
            ),
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
                                    "portal will open",
                                    "portal is open",
                                    "admission portal will open",
                                    "sale of forms open",
                                    "registration ongoing",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "portal closed",
                                    "admission closed",
                                    "applications are closed",
                                    "registration closed",
                                    "no extension of the deadline",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="upcoming",
                                keywords=[
                                    "will open",
                                    "opens on",
                                    "opening soon",
                                    "coming soon",
                                ],
                            ),
                        ],
                        case_sensitive=False,
                    ),
                ),
                ExtractRule(
                    name="deadlines_text",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="deadlines_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["p", "li"],
                    ),
                    required=True,
                ),
            ],
        ),

        # Programmes page.  A legacy page lists approved undergraduate
        # programmes in a table.  Each programme is contained within a
        # <p> element inside the table cells.  Selecting ``table p``
        # extracts all programme names.  The field is required since
        # programmes are central to downstream processing.
        PageConfig(
            name="programmes",
            category=PageCategory.PROGRAMMES,
            url="https://ui.edu.ng/content/university-ibadan-ibadan-nigeria-0",
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
                        selectors=["table p"],
                    ),
                ),
            ],
        ),

        # Profile page.  The vision and mission page articulates the
        # university’s core purpose.  The vision is a short paragraph
        # while the mission statements are bullet points within list
        # items.  Extracting both paragraphs and list items ensures
        # these statements are captured.
        PageConfig(
            name="profile",
            category=PageCategory.PROFILE,
            url="https://ui.edu.ng/content/vision-and-mission",
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="vision_mission",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="profile_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["p", "li"],
                    ),
                    required=True,
                ),
            ],
        ),
    ],
)