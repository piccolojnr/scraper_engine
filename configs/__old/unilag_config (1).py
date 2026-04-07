"""
Scraper configuration for the University of Lagos (UNILAG).

This configuration adheres to the schema defined in ``app.config.models`` and
captures essential admission‑related information from the University of Lagos
admissions office website.  The goal is to surface the current status of the
admissions portal, enumerate the undergraduate programmes offered by the
university, surface scholarship announcements published on the main university
news site and provide a brief profile describing the university.  Where
possible, selectors are scoped to semantic containers (e.g. the accordion
lists on the programmes page) to improve resilience against minor markup
changes.  Optional pages such as deadlines and fee schedules have been
omitted because no stable, publicly accessible source was found during
research; this configuration can be extended in the future if the
university publishes such data in a scrapeable format.

Evidence used to build this configuration:

* The admissions office home page lists contact information and provides
  quick links to the programmes list and notices.  The page describes
  UNILAG as the "University of First Choice" and offers details about the
  admissions office and its services【872506564926376†L16-L24】【275874284136439†L31-L41】.

* The notices page on the admissions site provides the registration
  procedure for the Post‑UTME screening exercise; while it doesn’t list
  specific deadlines, it contains instructions for applicants【591395282380110†L19-L33】.

* The programmes page presents undergraduate programmes grouped by faculty
  within an accordion interface.  Each faculty section contains an unordered
  list of programmes (e.g. Creative Arts, English, French, History &
  Strategic Studies under the Faculty of Arts; Adult Education, Business
  Education under the Faculty of Education; Biomedical Engineering,
  Chemical & Petroleum Engineering under Engineering; Botany, Computer
  Science and Geology under Science).  These lists appear as ``<li>``
  elements inside accordion bodies in the page source【556434693160794†L15-L27】【556434693160794†L47-L71】
  【556434693160794†L74-L83】【556434693160794†L110-L125】.

* The "About Us" page on the admissions site contains a short profile of
  the University of Lagos, noting its reputation as the University of First
  Choice and describing the role of the admissions office【275874284136439†L17-L31】.

* The university’s main site hosts a scholarship archive where posts
  announce scholarship opportunities.  An example entry describes the
  Lagos State Government scholarship, noting that it is open to
  undergraduate students with a minimum CGPA of 3.50 and that applicants
  should purchase a form through the Lagos scholarship portal【996684028261352†L96-L104】.
  Another post announces the Offa Development Foundation scholarship and
  states that the application closes by mid‑April【996684028261352†L111-L124】.  These
  paragraphs live inside the generic news page structure and can be
  extracted using a broad ``p`` selector.

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
    id="unilag2",
    university_name="University of Lagos",
    country="Nigeria",
    pages=[
        # Admissions portal – home page.  This page provides high‑level
        # information about the university and links to programmes and notices.
        # To determine whether the portal is currently accepting
        # applications, a keyword extraction strategy is used.  The body of
        # the page is scanned for phrases such as ``admissions open``,
        # ``applications are closed`` or ``coming soon``.  These labels feed
        # the ``portal_status`` field required by downstream systems.  If
        # none of the keywords are found the value will be ``unknown``.
        PageConfig(
            name="admissions_portal",
            category=PageCategory.ADMISSIONS,
            url="https://admissions.unilag.edu.ng/",
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
                                    "registration ongoing",
                                ],
                            ),
                            KeywordLabelGroup(
                                label="closed",
                                keywords=[
                                    "admission closed",
                                    "admissions are closed",
                                    "applications are closed",
                                    "sale of forms closed",
                                    "registration closed",
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

        # Programmes page.  The admissions site lists undergraduate
        # programmes by faculty within an accordion.  Each programme is
        # contained in a <li> element inside the accordion body.  Selecting
        # ``div.accordion-body li`` returns the programme names.  Since
        # multiple items are expected, ``many=True`` is set.
        PageConfig(
            name="programmes",
            category=PageCategory.PROGRAMMES,
            url="https://admissions.unilag.edu.ng/programmes.html",
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
                        selectors=["div.accordion-body li", "ul li"],
                    ),
                ),
            ],
        ),

        # Notices page.  The notices page hosts important announcements and
        # instructions for prospective students, such as procedures for
        # Post‑UTME registration.  While explicit deadlines are not always
        # present, capturing the page content allows a human or downstream
        # system to interpret any published dates.  A simple selector
        # strategy extracts all paragraphs and list items.  This page is
        # optional, so ``required`` is not set.
        PageConfig(
            name="notices",
            category=PageCategory.DEADLINES,
            url="https://admissions.unilag.edu.ng/notices2.html",
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="notices_content",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="deadlines_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["p", "li"],
                    ),
                ),
            ],
        ),

        # Scholarships page.  The university’s main site maintains a
        # scholarship tag archive where posts announce scholarship and
        # bursary opportunities.  Extracting all paragraphs from this page
        # captures the summary of each scholarship announcement.  The
        # extraction is not marked required because scholarships may
        # fluctuate, but the field provides valuable context when present.
        PageConfig(
            name="scholarships",
            category=PageCategory.SCHOLARSHIPS,
            url="https://unilag.edu.ng/tag/scholarship/",
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="scholarship_posts",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="scholarships_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["p"],
                    ),
                ),
            ],
        ),

        # Profile page.  Since the main university website uses dynamic
        # components that hinder static scraping, the admissions office
        # "About Us" page is used as a proxy for the university profile.  It
        # describes UNILAG’s reputation as the University of First Choice
        # and outlines the responsibilities of the admissions office.  All
        # paragraphs are extracted.
        PageConfig(
            name="profile",
            category=PageCategory.PROFILE,
            url="https://admissions.unilag.edu.ng/about-us.html",
            priority=1,
            fetch=FetchConfig(
                mode=FetchMode.HTTP,
                timeout_ms=30_000,
            ),
            extract=[
                ExtractRule(
                    name="profile_description",
                    strategy=ExtractStrategy.SELECTOR,
                    output_field="profile_raw",
                    many=True,
                    selector_config=SelectorExtractConfig(
                        selectors=["p"],
                    ),
                    required=True,
                ),
            ],
        ),
    ],
)