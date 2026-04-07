# UniScraper – AGENTS.md

This document defines how AI agents (and developers) should understand,
extend, and modify this codebase safely.

This is a **config-driven, entity-based scraping system** for university
admissions portals.

---

# 🧠 SYSTEM OVERVIEW

## Core Idea

We do NOT scrape into a fixed schema.

We:

1. Scrape pages → extract **entities**
2. Normalize entities → produce structured output

```

Pages → Entities → Normalized Output

```

---

## Key Concepts

### 1. Config-Driven Scraping

Each university is defined by a config:

```

configs/<university>.py

```

Config describes:

- pages to visit
- what entities to extract
- how to extract fields

---

### 2. Entity-Based Extraction

We DO NOT extract page-level fields anymore.

We extract:

- UNIVERSITY
- PORTAL
- COURSE
- (future: SCHOLARSHIP, DEADLINE, etc.)

Each page can produce **multiple entities**.

---

### 3. Extraction Pipeline

```

UniversityRunner
→ PageRunner
→ Fetch page
→ Locate records
→ Extract fields (via extractors)
→ Produce EntityResults
→ Normalizer
→ Convert entities → normalized output

```

---

# 📦 DIRECTORY STRUCTURE

```

app/
config/
models.py        # Config schema (SOURCE OF TRUTH)
registry.py      # Loads configs

runner/
university_runner.py
page_runner.py

extractors/
base.py          # StepExtractor interface
factory.py       # Returns extractors
selector.py
keyword.py
pattern.py
table.py
llm.py

runtime/
context.py       # Runtime state

normalizers/
orchestrator.py  # Entity → normalized output

schemas/
results.py       # Output models

```

---

# 🔒 HARD RULES (DO NOT BREAK)

## 1. NO ExtractRule

❌ Old system used `ExtractRule`  
✅ New system uses `ExtractionStep`

If you reintroduce `ExtractRule`, you are breaking the architecture.

---

## 2. Extractors MUST be step-based

All extractors must implement:

```python
extract_entity_field(context, request)
```

They must NOT:

- depend on old rule objects
- mutate global state
- write directly to output

---

## 3. PageRunner owns orchestration

Extractors:

- DO NOT control flow
- DO NOT loop fields
- DO NOT handle fallbacks

PageRunner does:

- step execution
- fallback logic
- error handling

---

## 4. Config is the source of truth

DO NOT hardcode scraping logic in:

- extractors
- runners
- normalizers

Everything must come from config.

---

## 5. Entities are independent

Each entity:

- must stand alone
- must not depend on other entities
- must not assume page order

---

## 6. Normalizers are pure

Normalizers:

- only read entity results
- do NOT fetch pages
- do NOT re-extract data

---

# ⚙️ HOW EXTRACTION WORKS

## StepExecution

Each field has:

```
EntityFieldPlan
  → steps[]
```

Each step:

- tries extraction
- may succeed or fail
- may stop or continue

---

## RecordLocator

Before extracting fields:

```
Page → RecordLocator → RecordScopes
```

Each scope = one entity instance.

Examples:

- SINGLE_RECORD → whole page
- SELECTOR_GROUP → multiple cards
- TABLE_ROWS → table rows

---

## Field Extraction

For each entity:

```
for field in fields:
  for step in steps:
    try extract
```

---

# 🧩 EXTRACTOR RESPONSIBILITIES

Extractors:

- receive scoped context
- run ONE strategy
- return structured result

They must NOT:

- decide fallback logic
- combine strategies
- interpret business meaning

---

## Example

SelectorExtractor:

- reads selectors
- returns value

KeywordExtractor:

- maps text → label

LLMExtractor:

- converts content → structured output

---

# 🛠️ HOW TO ADD FEATURES

## Add a new extraction strategy

1. Create extractor in `extractors/`
2. Implement `StepExtractor`
3. Register in `ExtractorFactory`
4. Add config support

---

## Add new entity type

1. Add enum in config models
2. Update normalizer
3. Add config usage

---

## Add new university

1. Create `configs/<uni>.py`
2. Export `CONFIG`
3. Run:

```
python main.py <config_id>
```

---

# ⚠️ COMMON PITFALLS

## ❌ Reintroducing page-level extraction

Wrong:

```
page.extract → fields
```

Correct:

```
page → entity_extractors → entities
```

---

## ❌ Making extractors too smart

Bad:

- combining selector + keyword inside extractor

Good:

- each extractor does ONE thing
- fallback handled by PageRunner

---

## ❌ Overusing LLM

LLM should be:

- fallback
- summarization
- normalization helper

NOT primary extraction when selectors work.

---

## ❌ Skipping RecordLocator

If you skip record locator:

- multi-portal pages break
- table extraction becomes unusable

---

# 🧪 DEBUGGING GUIDE

## If no data is extracted

Check:

- selectors incorrect?
- record locator wrong?
- page fetch failed?

---

## If too many duplicates

Check:

- record locator too broad
- selector grabbing entire page

---

## If fields missing

Check:

- fallback steps missing
- step order wrong

---

## If LLM is failing

Check:

- input too long
- selectors not narrowing content

---

# 🚀 FUTURE EXTENSIONS

Planned improvements:

- smarter record locator (DOM segmentation)
- config auto-generation (AI agent)
- config repair agent
- caching layer (per step)
- parallel page execution
- portal deduplication logic

---

# 🧠 FINAL PRINCIPLE

This system is designed to scale to **300+ universities**.

That only works if:

- configs are declarative
- extractors are simple
- runners are deterministic

If you violate that, the system will collapse under complexity.

---

# ✅ TL;DR

- Config defines everything
- PageRunner orchestrates
- Extractors are dumb + focused
- Entities are first-class
- Normalizer builds final output

---
