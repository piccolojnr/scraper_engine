# University Scraper Config Generation Instructions

You are responsible for creating a **production-ready scraping configuration** for a university website.

This configuration will be used by an automated scraping engine to extract structured data such as:

- Admission status (open / closed / upcoming)
- Programmes
- Deadlines
- Cut-off points
- Fees
- Application info
- Scholarships
- University profile

Your output must strictly follow the system’s config schema and design philosophy.

---

## 🔴 CORE RULES (DO NOT BREAK THESE)

### 1. Prefer deterministic extraction over LLM

Use strategies in this priority order:

1. `selector` (CSS selectors)
2. `keyword` (simple classification)
3. `pattern` (regex-based classification)
4. `table` (structured HTML tables)
5. `llm` (ONLY when unavoidable)

🚫 Do NOT use LLM if:

- Data is in tables
- Data is clearly structured
- Simple selectors work

---

### 2. Each page must have a clear purpose

Every page config must belong to a category:

- `MAIN_PORTAL`
- `ADMISSIONS`
- `PROGRAMMES`
- `FEES`
- `DEADLINES`
- `SCHOLARSHIPS`
- `PROFILE`

Each page must extract **only relevant data**.

---

### 3. Always define extraction outputs explicitly

Each rule must define:

- `name`
- `strategy`
- `output_field`
- config block (`selector_config`, `keyword_config`, etc.)

---

### 4. Required fields must be marked

Critical fields must be:

```python
required=True
```

Examples:

- portal_status
- programmes_raw (if programmes page exists)

---

### 5. Use stable selectors only

Prefer:

- IDs
- class names tied to structure
- semantic containers (main, article)

Avoid:

- nth-child
- dynamic classes
- fragile deep nesting

---

### 6. Narrow extraction scope

Always try to scope extraction to:

```python
["main", ".content", ".container", ".entry-content"]
```

DO NOT extract from full page unless necessary.

---

## 🧠 PROCESS YOU MUST FOLLOW

### STEP 1 — Identify key pages

Find URLs for:

- main portal / homepage
- admissions page
- programmes page
- fees page
- deadlines page

If not explicitly available:

- search navigation menus
- follow “Apply”, “Admissions”, “Academics”

---

### STEP 2 — Classify each page

Assign category:

```python
PageCategory.MAIN_PORTAL
PageCategory.ADMISSIONS
PageCategory.PROGRAMMES
...
```

---

### STEP 3 — Determine fetch mode

Use:

```python
FetchMode.HTTP
```

If:

- content is visible in raw HTML

Use:

```python
FetchMode.BROWSER
```

If:

- SPA
- content loads dynamically
- requires clicks or waits

---

### STEP 4 — Define extraction rules per page

---

## 🧩 EXTRACTION STRATEGIES

---

### 🔹 1. Selector Strategy

Use for:

- titles
- lists
- links
- structured text

Example:

```python
ExtractRule(
    name="programmes_list",
    strategy=ExtractStrategy.SELECTOR,
    output_field="programmes_raw",
    many=True,
    selector_config=SelectorExtractConfig(
        selectors=[".programme-list li", ".course-list li"],
    ),
)
```

---

### 🔹 2. Keyword Strategy

Use for:

- classification (open / closed)

Example:

```python
ExtractRule(
    name="portal_status",
    strategy=ExtractStrategy.KEYWORD,
    output_field="portal_status",
    required=True,
    keyword_config=KeywordExtractConfig(
        selectors=[".announcement", "main"],
        labels=[
            KeywordLabelGroup(
                label="open",
                keywords=["applications are open", "admissions are open"],
            ),
            KeywordLabelGroup(
                label="closed",
                keywords=["applications are closed"],
            ),
        ],
    ),
)
```

---

### 🔹 3. Pattern Strategy

Use when:

- phrasing varies
- regex is needed

---

### 🔹 4. Table Strategy

Use for:

- fees
- cut-offs
- deadlines

Example:

```python
ExtractRule(
    name="fees_table",
    strategy=ExtractStrategy.TABLE,
    output_field="fees_raw",
    many=True,
    table_config=TableExtractConfig(
        selectors=["table"],
    ),
)
```

---

### 🔹 5. LLM Strategy (LAST RESORT)

Use ONLY if:

- content is unstructured
- tables don’t exist
- selectors fail

Example:

```python
ExtractRule(
    name="cutoffs_semantic",
    strategy=ExtractStrategy.LLM,
    output_field="cutoffs_raw",
    llm_config=LLMExtractConfig(
        selectors=["main"],
        instruction="Extract cut-off points into structured format...",
    ),
)
```

---

## 🏗️ CONFIG STRUCTURE

You must output a full config like:

```python
from app.config.models import *

CONFIG = UniversityConfig(
    id="ug",
    university_name="University of Ghana",
    base_url="https://ug.edu.gh",
    pages=[
        ...
    ],
)
```

---

## 📦 OUTPUT REQUIREMENTS

You must return:

1. Full Python config file
2. Clean imports
3. No explanations inside code
4. Valid structure matching schema

---

## 🚫 COMMON MISTAKES TO AVOID

- Using LLM unnecessarily
- Using overly generic selectors like "body"
- Not marking required fields
- Mixing multiple concerns in one page
- Returning inconsistent output_field names

---

## 🎯 FINAL CHECK BEFORE OUTPUT

Ensure:

- Each page has:
  - correct fetch mode
  - relevant extraction rules

- Each rule:
  - has correct strategy
  - has correct config block
  - has meaningful selectors

- Output fields match expected naming:
  - programmes_raw
  - deadlines_raw
  - fees_raw
  - cutoffs_raw
  - portal_status

---

## ✅ SUCCESS CRITERIA

A correct config:

- runs without errors
- extracts meaningful structured data
- avoids unnecessary LLM usage
- is stable across page reloads
- maps cleanly into normalization

---

Now proceed to:

1. Analyze the university website
2. Identify pages
3. Design config
4. Output final config file
