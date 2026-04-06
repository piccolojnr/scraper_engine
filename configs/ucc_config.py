"""
Scraper configuration for the University of Cape Coast (UCC).

This configuration is constructed according to the schema defined in
``app.config.models``.  It aims to extract admissions portal status,
application deadlines, programme listings, tuition/fee information,
scholarship details and the university’s mission/vision.  Where
possible, selectors target stable HTML structures; for semi‑structured
documents such as PDFs, an LLM extraction strategy is used with
instructions to summarise the relevant content.  Critical fields such
as the portal status and list of programmes are marked as
``required`` to ensure downstream processors receive essential data.

Key design considerations:

* **Admissions portal** – The UCC application portal at ``apply.ucc.edu.gh``
  announces whether applications are open.  A keyword strategy scans
  the page’s body for phrases like “applications are invited” to
  infer the portal status.  Phrases indicating closure or upcoming
  openings trigger the corresponding labels.

* **Deadlines** – Application start and end dates are presented in a
  bootstrap table with class ``table table-bordered``.  A table
  extraction strategy captures rows for regular, sandwich, distance and
  other modes of study with their respective start/end dates【107592296142736†L108-L148】.

* **Programmes** – UCC publishes a PDF admissions brochure listing
  programmes and codes.  Because the PDF is unstructured text, an
  LLM extraction rule instructs the engine to read the document and
  extract the names of undergraduate programmes along with any codes.
  The underlying tool converts the PDF to plain text before
  processing, enabling the LLM to work over it【304900674642855†L150-L326】.

* **Fees** – Tuition and ancillary fees appear within another PDF
  related to sandwich admissions.  A second LLM rule instructs the
  engine to extract any monetary amounts (in Ghana cedis) and their
  descriptions from this document【386498021688882†L116-L124】.

* **Scholarships** – The Student’s Financial Support Office website
  enumerates eligibility criteria and application steps in list form【702388638675993†L120-L137】.  A simple
  selector extracts all list items from the page, capturing the raw
  scholarship information for later normalisation.

* **Profile** – UCC’s corporate strategic plan page contains
  block‑quoted vision and mission statements and detailed core
  values【324780748540574†L246-L274】.  Selecting the ``blockquote`` elements ensures
  that the vision and mission text is captured verbatim.
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
    LLMExtractConfig,
    KeywordLabelGroup,
    PageCategory,
    FetchMode,
)


# ---------------------------------------------------------------------------
# University‑wide configuration
#
# ``id`` should remain short and unique.  The ``country`` field aids
# downstream grouping.
CONFIG = UniversityConfig(
    id="ucc",
    university_name="University of Cape Coast",
    country="Ghana",
    pages=[
        # Admissions portal page.  Uses keyword matching over the body
        # content to determine whether applications are open, closed or
        # upcoming.  The portal prominently invites applications when
        # open【107592296142736†L108-L148】【107592296142736†L167-L195】.
        PageConfig(
            name="admissions_portal",
            category=PageCategory.ADMISSIONS,
            url=cast(HttpUrl ,"https://apply.ucc.edu.gh/"),
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
                                    "applications are invited",
                                    "admission open",
                                    "admissions are open",
                                    "applications are open",
                                    "sale of forms open",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "applications are closed",
                                    "admission closed",
                                    "admissions are closed",
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
                                    "opening soon",
                                ],
                            ),
                        ],
                        case_sensitive=False,
                    ),
                ),
            ],
        ),

        # Application deadlines table.  The deadlines for various modes
        # (regular, sandwich, distance, institute of education, etc.) are
        # presented as a bordered table on the application portal【107592296142736†L108-L148】.
        PageConfig(
            name="deadlines",
            category=PageCategory.DEADLINES,
            url=cast(HttpUrl ,"https://apply.ucc.edu.gh/"),
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
                    many=False,
                    table_config=TableExtractConfig(
                        selectors=["table.table-bordered"],
                        header_row_index=0,
                    ),
                ),
            ],
        ),

        # Programme catalogue.  UCC lists its programmes and codes in
        # the admissions brochure (regular.pdf).  Because the PDF is
        # essentially plain text, an LLM extraction rule is used.  The
        # instruction guides the model to extract the programme names and
        # associated codes from the document【304900674642855†L150-L326】.
        PageConfig(
            name="programmes",
            category=PageCategory.PROGRAMMES,
            url=cast(HttpUrl ,"https://application.ucc.edu.gh/public/static/docs/regular.pdf"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="programme_list",
                    strategy=ExtractStrategy.LLM,
                    output_field="programmes_raw",
                    many=True,
                    required=True,
                    llm_config=LLMExtractConfig(
                        selectors=[],
                        instruction=(
                            "From the admissions brochure, extract a list of undergraduate programme names "
                            "and their codes. Each item should include the programme name (e.g., "
                            "'B.Sc. Computer Science') and, if present, its code."
                        ),
                    ),
                ),
            ],
        ),

        # Tuition and fees.  The sandwich admissions brochure includes
        # examples of tuition and fee figures for fresh and continuing
        # students【386498021688882†L116-L124】.  Another LLM rule extracts these monetary
        # amounts and their descriptions from the PDF.
        PageConfig(
            name="fees",
            category=PageCategory.TUITION_FEES,
            url=cast(HttpUrl ,"https://application.ucc.edu.gh/public/static/docs/sandwich.pdf"),
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="fee_items",
                    strategy=ExtractStrategy.LLM,
                    output_field="fees_raw",
                    many=True,
                    required=False,
                    llm_config=LLMExtractConfig(
                        selectors=[],
                        instruction=(
                            "Identify all tuition or fee amounts (in Ghana cedis) mentioned in the document "
                            "along with the context or category they belong to (e.g., fresh students, continuing "
                            "students, programme types). Return each fee and its description as a separate item."
                        ),
                    ),
                ),
            ],
        ),

        # Scholarships page.  The Student’s Financial Support Office site
        # lists objectives, eligibility criteria and application steps in
        # unordered lists【702388638675993†L120-L137】.  Extract all list items for raw
        # scholarship data.  ``many=True`` returns each list item separately.
        PageConfig(
            name="scholarships",
            category=PageCategory.SCHOLARSHIPS,
            url=cast(HttpUrl ,"https://stufso.ucc.edu.gh/"),
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
                        selectors=["li"],
                    ),
                ),
            ],
        ),

        # Profile page.  UCC’s vision and mission statements are
        # presented within blockquote elements on the corporate strategic
        # plan page【324780748540574†L246-L274】.  Selecting all blockquotes captures
        # the vision, mission and other narrative statements.
        PageConfig(
            name="profile",
            category=PageCategory.PROFILE,
            url=cast(HttpUrl ,"https://ucc.edu.gh/main/explore-ucc/corporate-strategic-plan/vision-mission-and-core-values"),
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
                    many=True,
                    required=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["blockquote"],
                    ),
                ),
            ],
        ),
    ],
)