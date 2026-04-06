from typing import cast

from pydantic import HttpUrl

from app.config.models import (
    UniversityConfig,
    PageConfig,
    PageCategory,
    FetchConfig,
    FetchMode,
    ExtractRule,
    ExtractStrategy,
    SelectorExtractConfig,
    KeywordExtractConfig,
    KeywordLabelGroup,
    TableExtractConfig,
    StoreMode,
)

CONFIG = UniversityConfig(
    id="unilag",
    university_name="University of Lagos",
    country="Nigeria",
    pages=[

        # ─────────────────────────────────────────────
        # PAGE 1 — MAIN PORTAL (homepage)
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_homepage",
            category=PageCategory.MAIN,
            url=cast(HttpUrl ,"https://unilag.edu.ng"),
            priority=1,
            notes="Main homepage. Status keywords tuned to UTME/PUTME language used by UNILAG.",
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="portal_status",
                    strategy=ExtractStrategy.KEYWORD,
                    output_field="portal_status",
                    required=True,
                    keyword_config=KeywordExtractConfig(
                        selectors=["main", ".elementor-widget-container", "article"],
                        labels=[
                            KeywordLabelGroup(
                                label="open",
                                keywords=[
                                    "applications are open",
                                    "admission is open",
                                    "apply now",
                                    "post-utme",
                                    "putme",
                                    "now accepting applications",
                                    "application portal is open",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "applications are closed",
                                    "admission is closed",
                                    "portal is closed",
                                    "no longer accepting",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="upcoming",
                                keywords=[
                                    "applications will open",
                                    "admission coming soon",
                                    "watch this space",
                                ],
                            ),
                        ],
                    ),
                ),
                ExtractRule(
                    name="news_headlines",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="news_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            ".elementor-post__title a",
                            "h2.elementor-heading-title a",
                        ],
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 2 — ADMISSIONS OVERVIEW
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_admissions_overview",
            category=PageCategory.ADMISSIONS,
            url=cast(HttpUrl ,"https://unilag.edu.ng/admission/"),
            priority=2,
            notes="Main admissions hub. Links out to UG, PG, DLI, ICE and international portals.",
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="portal_status",
                    strategy=ExtractStrategy.KEYWORD,
                    output_field="portal_status",
                    required=True,
                    keyword_config=KeywordExtractConfig(
                        selectors=["main", ".elementor-widget-container"],
                        labels=[
                            KeywordLabelGroup(
                                label="open",
                                keywords=[
                                    "applications are open",
                                    "apply now",
                                    "putme",
                                    "post-utme",
                                    "application form",
                                    "now open",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "applications are closed",
                                    "admission closed",
                                    "portal is closed",
                                ],
                            ),
                        ],
                    ),
                ),
                ExtractRule(
                    name="admission_links",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="admission_links_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "main a[href*='admissions.unilag']",
                            "main a[href*='applications.unilag']",
                            ".elementor-widget-container a[href*='admission']",
                        ],
                        attribute="href",
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 3 — ADMISSIONS SUBDOMAIN (live portal)
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_admissions_portal",
            category=PageCategory.ADMISSIONS,
            url=cast(HttpUrl ,"https://admissions.unilag.edu.ng/index.html"),
            priority=2,
            notes=(
                "Dedicated admissions subdomain. More reliable status signals than main site. "
                "Shows active PUTME/DE cycles and quick links to application forms."
            ),
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
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
                                    "apply now",
                                    "application is open",
                                    "putme",
                                    "post-utme",
                                    "de/putme application",
                                    "now open",
                                    "screening",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "closed",
                                    "applications are closed",
                                    "portal is closed",
                                ],
                            ),
                        ],
                    ),
                ),
                ExtractRule(
                    name="admission_notices",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="admission_notices_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            ".section-title h2",
                            "h3",
                            "p strong",
                        ],
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 4 — ADMISSIONS NOTICES
        # Scoring modalities, UTME cutoff, verification
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_admissions_notices",
            category=PageCategory.ADMISSIONS,
            url=cast(HttpUrl ,"https://admissions.unilag.edu.ng/notices.html"),
            priority=3,
            notes=(
                "Contains scoring breakdown (JAMB=50%, O'Level=20%, PUTME=30%), "
                "minimum UTME score (200), age requirement and general admission rules."
            ),
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="admission_requirements_text",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="admission_requirements_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "main p",
                            ".container p",
                            "h5",
                            "p strong",
                        ],
                    ),
                ),
                ExtractRule(
                    name="utme_cutoff_score",
                    strategy=ExtractStrategy.KEYWORD,
                    output_field="cutoffs_raw",
                    keyword_config=KeywordExtractConfig(
                        selectors=["body"],
                        labels=[
                            KeywordLabelGroup(
                                label="cutoff_mentioned",
                                keywords=[
                                    "minimum of 200",
                                    "cut-off mark",
                                    "cutoff",
                                    "200 points",
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 5 — PROGRAMMES (admissions subdomain)
        # Most reliable source: clean ul > li structure
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_programmes",
            category=PageCategory.PROGRAMMES,
            url=cast(HttpUrl ,"https://admissions.unilag.edu.ng/programmes.html"),
            priority=1,
            notes=(
                "Full list of undergraduate programmes grouped by faculty. "
                "Very clean ul > li HTML — no LLM needed. "
                "Covers Arts, Sciences, Engineering, Law, Management, Medicine, etc."
            ),
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="programmes_list",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="programmes_raw",
                    required=True,
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            ".container ul li",
                            "main ul li",
                        ],
                    ),
                ),
                ExtractRule(
                    name="faculties_list",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="faculties_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            ".container h2",
                            "main h2",
                        ],
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 6 — FACULTIES (main site)
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_faculties",
            category=PageCategory.PROGRAMMES,
            url=cast(HttpUrl ,"https://unilag.edu.ng/faculties/"),
            priority=2,
            notes="Lists all 19 faculties with links to their individual subdomain websites.",
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="faculties_names",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="faculties_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            ".elementor-icon-list-text",
                            "main li",
                        ],
                    ),
                ),
                ExtractRule(
                    name="faculties_links",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="faculties_links_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            ".elementor-widget-container a[href*='unilag.edu.ng']",
                        ],
                        attribute="href",
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 7 — ENTRY REQUIREMENTS (undergraduate)
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_undergraduate_requirements",
            category=PageCategory.ENTRY_REQUIREMENTS,
            url=cast(HttpUrl ,"https://unilag.edu.ng/unilag-undergraduate-studies/"),
            priority=2,
            notes=(
                "Lists general UG entry requirements: UTME min 200, 5 O'Level credits, "
                "POST-UTME screening, age 16 by 30 Sept. Also links to application form."
            ),
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="entry_requirements",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="entry_requirements_raw",
                    required=True,
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            ".elementor-widget-container ul li",
                            "main ul li",
                        ],
                    ),
                ),
                ExtractRule(
                    name="application_form_url",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="application_url_raw",
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "a[href*='applications.unilag']",
                        ],
                        attribute="href",
                    ),
                ),
                ExtractRule(
                    name="portal_status",
                    strategy=ExtractStrategy.KEYWORD,
                    output_field="portal_status",
                    keyword_config=KeywordExtractConfig(
                        selectors=["main", ".elementor-widget-container"],
                        labels=[
                            KeywordLabelGroup(
                                label="open",
                                keywords=[
                                    "post-utme",
                                    "putme",
                                    "apply now",
                                    "application form",
                                    "now open",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "closed",
                                    "admission closed",
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 8 — HOW TO APPLY
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_how_to_apply",
            category=PageCategory.HOW_TO_APPLY,
            url=cast(HttpUrl ,"https://admissions.unilag.edu.ng/admission_requirements.html"),
            priority=2,
            notes=(
                "Admissions office portal page linking to the official 2025/2026 "
                "admission requirements PDF and the DE/PUTME application form."
            ),
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="application_links",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="application_links_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "a[href*='applications.unilag']",
                            "a[href*='.pdf']",
                            ".sidebar a",
                        ],
                        attribute="href",
                    ),
                ),
                ExtractRule(
                    name="how_to_apply_text",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="how_to_apply_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "main p",
                            ".container p",
                            "li",
                        ],
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 9 — POSTGRADUATE (SPGS subdomain)
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_postgraduate",
            category=PageCategory.GRADUATE,
            url=cast(HttpUrl ,"https://spgs.unilag.edu.ng/"),
            priority=3,
            notes=(
                "School of Postgraduate Studies portal. "
                "Defaulting to HTTP — upgrade to BROWSER if content is JS-rendered."
            ),
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="postgrad_portal_status",
                    strategy=ExtractStrategy.KEYWORD,
                    output_field="portal_status",
                    keyword_config=KeywordExtractConfig(
                        selectors=["main", ".container", "body"],
                        labels=[
                            KeywordLabelGroup(
                                label="open",
                                keywords=[
                                    "applications are open",
                                    "apply now",
                                    "admission is open",
                                    "portal is open",
                                    "now accepting",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "applications are closed",
                                    "portal is closed",
                                    "not accepting",
                                ],
                            ),
                        ],
                    ),
                ),
                ExtractRule(
                    name="postgrad_programmes",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="programmes_raw",
                    many=True,
                    store_mode=StoreMode.APPEND,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "main ul li",
                            "table td",
                            ".programmes li",
                        ],
                    ),
                ),
                ExtractRule(
                    name="postgrad_deadlines",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="deadlines_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "main p",
                            ".notice p",
                            ".deadline",
                        ],
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 10 — PROFILE (About UNILAG)
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_profile",
            category=PageCategory.PROFILE,
            url=cast(HttpUrl ,"https://unilag.edu.ng/about/"),
            priority=4,
            notes="About page. Captures VC name, mission, vision and establishment year (1962).",
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="university_description",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="university_profile_raw",
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            ".elementor-widget-container p",
                            "main p",
                            "article p",
                        ],
                    ),
                ),
                ExtractRule(
                    name="vc_name",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="vc_name_raw",
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "h2.elementor-heading-title",
                            "h3.elementor-heading-title",
                        ],
                    ),
                ),
            ],
        ),

        # ─────────────────────────────────────────────
        # PAGE 11 — TUITION FEES (Bursary)
        # ─────────────────────────────────────────────
        PageConfig(
            name="unilag_tuition_fees",
            category=PageCategory.TUITION_FEES,
            url=cast(HttpUrl ,"https://unilag.edu.ng/bursary/"),
            priority=3,
            notes=(
                "Bursary page. Fee data may be in tables or free-text paragraphs. "
                "Table strategy runs first; selector appends any additional prose."
            ),
            fetch=FetchConfig(mode=FetchMode.HTTP, timeout_ms=30_000),
            extract=[
                ExtractRule(
                    name="fees_table",
                    strategy=ExtractStrategy.TABLE,
                    output_field="fees_raw",
                    many=True,
                    table_config=TableExtractConfig(
                        selectors=["table"],
                        header_row_index=0,
                    ),
                ),
                ExtractRule(
                    name="fees_text",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="fees_raw",
                    many=True,
                    store_mode=StoreMode.APPEND,
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "main p",
                            ".elementor-widget-container p",
                            "main li",
                        ],
                    ),
                ),
                ExtractRule(
                    name="payment_portal_link",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="payment_url_raw",
                    selector_config=SelectorExtractConfig(
                        selectors=[
                            "a[href*='remita']",
                            "a[href*='payment']",
                        ],
                        attribute="href",
                    ),
                ),
            ],
        ),

    ],
)