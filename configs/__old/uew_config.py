"""
Scraper configuration for the University of Education, Winneba (UEW).

This configuration adheres to the schema defined in ``app.config.models``
and is tailored to extract key admission‑related information from the
official UEW websites.  Because many of UEW’s admissions pages rely
heavily on JavaScript, the scraper focuses on static resources such as
PDF brochures and announcements that are publicly accessible via
plain HTTP.  The configuration covers the admissions portal status,
programme listings, tuition/fee schedules, important deadlines,
available scholarships and the university’s mission/vision.

Key design notes:

* **Admissions portal** – The main “Apply to UEW” page announces whether
  applications are open or closed for a given academic year.  A keyword
  extraction rule scans the body text for phrases such as
  “Admissions Now Open” or “Applications are now officially closed” and
  maps them to labels ``open`` and ``closed`` accordingly【654552302289585†L64-L83】.

* **Programmes** – The undergraduate admissions brochure (PDF)
  published on the UEW site lists all undergraduate programmes with
  descriptions and entry requirements.  Since the PDF is plain text,
  an LLM extraction rule instructs the model to extract only the
  programme names, omitting codes and entry requirements【325800950028851†L17-L46】.

* **Tuition fees** – Provisional fee schedules are published as PDFs for
  various categories of students.  The configuration points to the
  regular (full‑time) undergraduate fresher fee schedule for the
  2025/2026 academic year.  An LLM rule asks the model to pull out
  major fee components (e.g. Main University Fees, Tuition Fees,
  Third Party Services, SRC Dues and Residential Facilities User Fees)
  along with their amounts for each programme【346337140224858†L34-L90】.

* **Deadlines** – The admission calendar page provides a month‑by‑month
  outline of key activities (applications opening, deadlines for
  various modes, release of admission letters and examinations).  A
  small LLM extractor summarises these events into discrete items【648958649991202†L66-L114】.

* **Scholarships** – UEW operates several financial aid schemes.
  The Vice‑Chancellor’s Scholarship Fund page details eligibility
  criteria, benefits and renewal conditions in a series of lists【961700786229173†L43-L99】.
  A selector extracts all list items as raw scholarship text.

* **Profile** – The university’s mission, vision and core values are
  presented on the “Mission, Vision and Values” page.  Selecting
  paragraphs that immediately follow the ``h3`` headings captures
  these statements succinctly【43687817743989†L65-L74】.
"""

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
# ``country`` field assists downstream grouping.  Each page uses a
# priority of 1 to indicate equal importance when crawling.
CONFIG = UniversityConfig(
    id="uew",
    university_name="University of Education, Winneba",
    country="Ghana",
    pages=[
        # Admissions portal page.  The Apply to UEW page announces
        # whether admissions for the current academic year are open or
        # closed.  Keyword matching over the body text maps status
        # phrases to ``open`` or ``closed``.  An ``upcoming`` label is
        # provided for phrases indicating a future opening.
        PageConfig(
            name="admissions_portal",
            category=PageCategory.ADMISSIONS,
            url="https://www.uew.edu.gh/admissions/apply",
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
                                    "admissions now open",
                                    "applications are invited",
                                    "applications now open",
                                    "sale of forms open",
                                    "apply now",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "admissions closed",
                                    "applications closed",
                                    "applications are closed",
                                    "now officially closed",
                                    "no longer being accepted",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="upcoming",
                                keywords=[
                                    "coming soon",
                                    "will open",
                                    "opens on",
                                ],
                            ),
                        ],
                        case_sensitive=False,
                    ),
                ),
            ],
        ),

        # Programmes list.  The undergraduate admissions brochure lists
        # all programmes offered by UEW.  An LLM extraction rule
        # instructs the model to extract programme names only (omit
        # codes and entry requirements).  The PDF is converted to
        # plain text prior to processing by the scraper engine.
        PageConfig(
            name="programmes",
            category=PageCategory.PROGRAMMES,
            url="https://www.uew.edu.gh/sites/default/files/2023-05/undergraduate-admission-brochure.pdf",
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
                            "offered by the University of Education, Winneba. Do not include entry "
                            "requirements or codes. List each programme as a separate item."
                        ),
                    ),
                ),
            ],
        ),

        # Tuition and fee schedule.  The regular (full‑time) undergraduate
        # fresher fee schedule for the 2025/2026 academic year is
        # provided in PDF form.  An LLM extractor summarises major fee
        # components and their amounts for each programme or category.
        PageConfig(
            name="tuition_fees",
            category=PageCategory.TUITION_FEES,
            url="https://www.uew.edu.gh/sites/default/files/2026-01/provisonal_fees_for_2025-2026_regular_ug_freshers.pdf",
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
                            "Review the fee schedule and extract each major fee component (e.g., Main University "
                            "Fees, Tuition Fees, Fees for Third Party Services, SRC Dues, Residential Facilities User "
                            "Fees) together with the corresponding amounts for each programme category. Return "
                            "each component and amount as a separate item."
                        ),
                    ),
                ),
            ],
        ),

        # Admission calendar (deadlines).  UEW’s admission calendar
        # outlines important events for each month (applications open,
        # deadlines, release of admission letters, examinations).  An
        # LLM extractor converts these events into a list of human‑readable
        # deadline entries.
        PageConfig(
            name="deadlines",
            category=PageCategory.DEADLINES,
            url="https://www.uew.edu.gh/admissions/apply/admission-calender",
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="deadline_events",
                    strategy=ExtractStrategy.LLM,
                    output_field="deadlines_raw",
                    many=True,
                    required=True,
                    llm_config=LLMExtractConfig(
                        selectors=[],
                        instruction=(
                            "From the admission calendar, extract each month and its corresponding key "
                            "activity (e.g., 'April – Applications open for all programmes', 'August – Deadline for "
                            "Sandwich Applications', 'November – Deadline for sale of regular/distance application forms'). "
                            "Return each month/event pair as a separate item."
                        ),
                    ),
                ),
            ],
        ),

        # Scholarships page.  The Vice‑Chancellor’s Scholarship Fund page
        # lists eligibility criteria, benefits and procedures in unordered
        # lists.  Extract all list items as raw scholarship text.  The
        # ``many=True`` flag ensures each list entry is returned separately.
        PageConfig(
            name="scholarships",
            category=PageCategory.SCHOLARSHIPS,
            url="https://uew.edu.gh/students/vice-chancellors-scholarship-fund",
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="scholarship_items",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="scholarships_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["li"],
                    ),
                ),
            ],
        ),

        # University profile.  Mission, vision and core values are
        # presented in paragraphs following ``h3`` headings on the
        # Mission, Vision and Values page.  Selecting ``h3 + p``
        # captures the mission and vision statements.  The result is
        # returned as a single concatenated string.
        PageConfig(
            name="profile",
            category=PageCategory.PROFILE,
            url="https://www.uew.edu.gh/about-uew/mission-vision-and-values",
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
                        selectors=["h3 + p"],
                    ),
                ),
            ],
        ),
    ],
)