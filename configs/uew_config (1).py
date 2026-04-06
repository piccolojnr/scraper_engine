"""
Scraper configuration for the University of Education, Winneba (UEW).

This configuration follows the schema defined in ``app.config.models`` and
captures key pieces of information about the UEW admissions cycle.  The
pages included here come from official UEW web domains and PDFs that
publish admissions notices, programme listings, fee schedules, scholarship
calls and the university’s mission and vision.  Each page is paired with
an extraction strategy tailored to the structure of the underlying
content.

Highlights of the sources:

* **Admissions portal:** The “Apply to UEW” page announces when
  applications open and close for the academic year.  It features
  prominent notices such as “2025/2026 Admissions Now Open” and
  later “Admissions Closed” for the same cycle【654552302289585†L64-L80】.  A
  keyword‐based extractor infers the portal status (open/closed/upcoming)
  from these messages.
* **Programmes list:** UEW’s academic programmes page exposes
  programme titles in static HTML.  Each programme is contained in a
  ``div`` with class ``programme‑list`` and an anchor tag linking to
  programme details; examples include ``BA Political Science
  Education``, ``2‑Year Diploma (Art Education)`` and ``B.B.A. (Accounting)``【660284692730462†L503-L518】.  A selector targeting these anchor
  tags captures the raw programme names for downstream normalisation.
* **Admissions calendar:** The admission calendar page outlines key
  milestones by month: applications open in April, deadlines for
  sandwich applications and mature entrance examinations in August,
  release of admission letters in September, matriculation in October
  and various deadlines in November【648958649991202†L66-L112】.  An LLM
  summarisation extracts this timeline into a concise list for the
  ``deadlines_raw`` field.
* **Application voucher costs:** UEW publishes the cost of online
  application vouchers for different applicant categories.  The
  “Cost of Application Vouchers” page lists GH¢255 for undergraduate
  (direct and mature) forms, GH¢325 for postgraduate forms and USD 100
  for international applicants【372335353258121†L520-L640】.  A simple
  CSS selector retrieves these amounts.
* **Tuition fees:** Detailed fee schedules are provided in PDF
  attachments.  One such document, ``provisonal_fees_for_2025‑2026
  _regular_ug_freshers.pdf``, itemises main fees, tuition fees,
  third‑party charges and other levies for each programme (e.g., B.Ed.
  Counselling Psychology with 298 GHS main fees and total 3,095 GHS
  including tuition and levies)【346337140224858†L24-L43】.  An LLM extractor
  summarises the key fee components and amounts.
* **Scholarships:** The Vice‑Chancellor’s Scholarship Fund (VCSF)
  announcement describes the purpose of the fund, eligibility criteria
  and the submission deadline.  Applicants must be Ghanaian UEW
  students on non‑full fee paying programmes, possess strong academic
  ability and financial need, and submit forms by the deadline.  The
  call for applications specifies a closing date (e.g., Thursday,
  29 February 2024)【680277667711100†L66-L81】.  An LLM summariser extracts
  these details for ``scholarships_raw``.
* **Profile:** UEW’s “Mission, Vision and Values” page states that the
  university’s mission is to train competent professional teachers,
  conduct research and contribute to educational policy, while its
  vision is to be an internationally reputable institution for teacher
  education【43687817743989†L65-L74】.  Core values include academic
  excellence, service to community and gender equity【43687817743989†L76-L83】.
  A small LLM extractor isolates these statements for the ``profile``
  page.

All pages use ``FetchMode.HTTP`` with a 30 second timeout.  For PDF
resources, the fetcher will download the document over HTTP and the
LLM extraction will operate on the parsed text.  Downstream systems
will normalise the raw outputs.
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
# ``country`` field assists in grouping universities by region.
CONFIG = UniversityConfig(
    id="uew",
    university_name="University of Education, Winneba",
    country="Ghana",
    pages=[
        # Admissions portal.  UEW announces the status of its admissions
        # cycle on the “Apply to UEW” page.  A keyword strategy scans the
        # page body for indicators that applications are open, closed or
        # upcoming.
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
                                    "applications open",
                                    "applications are invited",
                                    "now open",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "admissions closed",
                                    "applications closed",
                                    "now officially closed",
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

        # Programmes page.  This page lists programme names in
        # ``div.programme-list`` elements.  Selecting the anchor tags
        # under these divs captures the raw programme titles (first
        # page only; subsequent pages may be added later).
        PageConfig(
            name="programmes",
            category=PageCategory.PROGRAMMES,
            url="https://www.uew.edu.gh/admissions/apply/academic-programmes",
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
                        selectors=["div.programme-list a"],
                    ),
                ),
            ],
        ),

        # Admission calendar (deadlines).  The calendar outlines key
        # milestones by month, such as when applications open, when
        # mature entrance examinations are held and when application
        # forms stop selling【648958649991202†L66-L112】.  An LLM
        # summariser condenses this timeline into a list of month
        # descriptions.
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
                    name="deadlines_info",
                    strategy=ExtractStrategy.LLM,
                    output_field="deadlines_raw",
                    many=False,
                    required=True,
                    llm_config=LLMExtractConfig(
                        selectors=[],
                        instruction=(
                            "From the admission calendar, list each month and its key activity. "
                            "For example, summarise entries like 'April – Applications open for all programmes', "
                            "'August – Deadline for sandwich applications and mature entrance examination' and so on."
                        ),
                    ),
                ),
            ],
        ),

        # Application voucher costs.  UEW publishes the cost of
        # application vouchers for different categories on a dedicated
        # page.  Selecting the red grid items retrieves the monetary
        # values (GH¢255.00, GH¢325.00, USD 100.00)【372335353258121†L520-L640】.
        PageConfig(
            name="application_fees",
            category=PageCategory.TUITION_FEES,
            url="https://www.uew.edu.gh/admissions/apply/cost-application-vouchers",
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="voucher_costs",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="fees_raw",
                    many=True,
                    required=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["div.grid-item.bg-red-500"],
                    ),
                ),
            ],
        ),

        # Tuition fees schedule.  A provisional fee schedule for regular
        # undergraduate freshers is provided as a PDF.  The document
        # lists main fees, tuition fees, third‑party charges and totals
        # for each programme【346337140224858†L24-L43】.  An LLM
        # extraction summarises these components into a digestible list.
        PageConfig(
            name="tuition_fees",
            category=PageCategory.TUITION_FEES,
            url="https://uew.edu.gh/sites/default/files/2026-01/provisonal_fees_for_2025-2026_regular_ug_freshers.pdf",
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
                            "Parse the fee schedule and identify each fee component and its amount for freshers. "
                            "Include the main fees, tuition fees, third‑party services, SRC dues and total fees. "
                            "Return each fee component with its corresponding amount as a separate item."
                        ),
                    ),
                ),
            ],
        ),

        # Scholarships – Vice‑Chancellor’s Scholarship Fund call for applications.
        # This announcement outlines the purpose of the fund, eligibility
        # requirements and a submission deadline.  An LLM summariser
        # extracts the key points (purpose, eligibility and deadline)
        #【680277667711100†L66-L81】.
        PageConfig(
            name="scholarships",
            category=PageCategory.SCHOLARSHIPS,
            url="https://uew.edu.gh/vc/announcements/call-application-vice-chancellors-scholarship-fund",
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="scholarship_details",
                    strategy=ExtractStrategy.LLM,
                    output_field="scholarships_raw",
                    many=False,
                    required=True,
                    llm_config=LLMExtractConfig(
                        selectors=[],
                        instruction=(
                            "Summarise the call for applications by stating the purpose of the Vice‑Chancellor’s "
                            "Scholarship Fund, listing the eligibility criteria and specifying the submission deadline."
                        ),
                    ),
                ),
            ],
        ),

        # Profile page (mission and vision).  The university’s mission
        # statement and vision are presented on the "Mission, Vision and
        # Values" page【43687817743989†L65-L74】.  An LLM extractor isolates
        # these statements and the core values into a structured
        # description.
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
                    name="mission_and_values",
                    strategy=ExtractStrategy.LLM,
                    output_field="profile_raw",
                    many=False,
                    required=True,
                    llm_config=LLMExtractConfig(
                        selectors=[],
                        instruction=(
                            "Extract the mission statement, vision statement and core values from the page. "
                            "Return them clearly separated, for example as 'Mission: ...', 'Vision: ...', "
                            "'Core values: ...'."
                        ),
                    ),
                ),
            ],
        ),
    ],
)