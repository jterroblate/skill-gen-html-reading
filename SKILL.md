---
name: skill-gen-html-reading
description: >
  Generate interactive IELTS reading practice HTML from structured JSON data with
  heading-matching drag-and-drop, MCQ, TFNG/YNNG, matching select, fill, summary
  completion, submit/reveal/reset/scoring, and smoke-testable fixtures. Trigger
  when user requests: reading practice HTML, 阅读刷题HTML, reading player, heading
  matching drag-and-drop, or an IELTS reading practice interface.
---

# IELTS Reading Player Generator

## Current Scope

This skill has two modules:

- **Module A (pilot): teacher DOCX / source draft → raw extraction → source audit → clean structured JSON candidate.**
- **Module B (stable): structured JSON → standalone IELTS Reading interactive HTML.**

Module A is intentionally audit-first. It preserves source traces, warnings, and
confidence instead of silently fixing source conflicts. It is currently tuned for
IELTS Reading teacher-version documents with clear passage/question/answer-key
structure; it is **not** a general Word layout parser.

It does **not** currently support:

- PDF input parsing
- OCR or screenshot understanding
- arbitrary Word layout reconstruction
- pure-text automatic question generation from unstructured prose
- strict student-version security against viewing answers in HTML source

Do not present this skill as a fully general raw-material → reading-pack
generator. For production, use Module A audit output first, then feed confirmed
clean JSON into Module B.

## Output

The generator produces a single standalone HTML file with:

- Dynamic passage tabs; supported passage counts: **1, 3, or 5**
- Left column: passage text
- Right column: questions and heading pool
- Heading matching: passage-side answer drop boxes before each target paragraph; drag/drop plus click-heading-then-click-slot support
- Question types: MCQ, TFNG, YNNG, matching select, fill, summary completion
- Submit → red/green feedback without revealing correct answers
- Reveal buttons after submit; heading reveal writes the full correct heading into the passage-side answer box
- Reset current passage, including heading slot values, used heading state, feedback, score, and reveals
- Score display
- Browser-side score report PDF via jsPDF/html2canvas CDN

Important limitation: answers are embedded in HTML `data-ans` attributes and hidden
reveal blocks. The output is fine for practice UX but is **not a strict secure
student version**.

## Quick Start

### Module B: JSON → HTML

From this skill directory:

```bash
python3 -B scripts/generate_reading.py \
  --data fixtures/minimal_1_passage.json \
  --output /tmp/reading_minimal.html
```

Validate generated HTML:

```bash
python3 -B scripts/validate_reading.py /tmp/reading_minimal.html
```

Run the full non-destructive smoke suite:

```bash
python3 -B scripts/smoke_test.py
```

Smoke tests generate temporary HTML under a system temp directory and do not write
outputs into the skill directory.

### Module A: DOCX → clean JSON candidate

```bash
python3 -B scripts/build_from_docx.py \
  --docx /path/to/teacher.docx \
  --out-dir /path/to/docx_to_json_audit \
  --allow-partial
```

Typical outputs:

- `raw_docx_extraction.json`
- `source_audit.json`
- `source_audit.md`
- `clean_reading_data_candidate.json`
- `extraction_warnings.json`

Run Module A smoke tests:

```bash
python3 -B scripts/smoke_test_docx_pipeline.py
```

## Input Data Contract

The formal schema is documented in:

- `schema/reading_data.schema.json`

The runtime generator also performs built-in schema/data validation before writing
HTML. Good fixtures are in `fixtures/`; the bad fixture must fail validation.

Top-level structure:

```json
{
  "title": "IELTS Reading · Unit Name",
  "header_title": "IELTS Academic Reading · Unit Name",
  "header_sub": "optional first-passage subtitle override",
  "passages": [
    {
      "num": 1,
      "title": "Passage Title",
      "band": "6.0",
      "genre": "Social Observation",
      "meta": "Band 6.0 · Social Observation",
      "paras": [
        {"label": "A", "text": "Paragraph text..."}
      ],
      "questions": {
        "type": "regular",
        "blocks": []
      }
    }
  ]
}
```

Supported passage counts: **1, 3, or 5**.

## Question Blocks

### MCQ

```json
{"q": 1, "type": "mcq", "stem": "...", "options": ["A) ...", "B) ..."], "answer": "A", "reveal": "..."}
```

### TFNG / YNNG

```json
{"q": 2, "type": "tfng", "statement": "...", "answer": "TRUE", "reveal": "..."}
{"q": 3, "type": "ynng", "statement": "...", "answer": "YES", "reveal": "..."}
```

### Matching Select

```json
{"q": 4, "type": "match", "text": "Which paragraph mentions...?", "options": ["A", "B"], "answer": "B", "reveal": "..."}
```

### Fill

```json
{"q": 5, "type": "fill", "before": "The key word is", "after": ".", "answer": "routine", "reveal": "..."}
```

### Summary

```json
{"q": 6, "type": "summary", "pairs": [[6, "The idea is", "simple", "."]], "reveals": ["simple — evidence..."]}
```

### Heading Matching

For heading passages, set `questions.type` to `heading`, provide `headings`,
paragraph-label `answers`, and optional `heading_info` blocks for visible question
labels/reveals.

```json
{
  "type": "heading",
  "headings": [["i", "A small commitment"], ["ii", "A later change"]],
  "answers": {"A": "i", "B": "ii"},
  "blocks": [
    {"q": 1, "type": "heading_info", "label": "A", "reveal": "i — evidence..."}
  ]
}
```

## Validation and Warnings

`validate_reading.py` checks:

- html/body/script open/close tag counts
- duplicate trailing closing tags
- div balance
- required DOM classes and interaction functions
- passage tab/panel counts
- non-empty passage text, question text, and reveal text
- MCQ options and `data-ans`
- fill/summary answers
- heading pool, heading item, heading slot, and drag/drop functions

Expected warning:

```text
WARNING: current output is not a strict student version because answers are embedded in HTML source/data attributes.
```

This warning is intentional until a later strict student/teacher split exists.

## Fixtures

- `fixtures/minimal_1_passage.json` — minimal valid 1-passage fixture
- `fixtures/escaping_edge_cases.json` — 3-passage fixture with `<`, `>`, `&`, quotes, slash, long dash
- `fixtures/full_5_passage_all_types.json` — 5-passage fixture covering supported types
- `fixtures/bad_missing_required.json` — invalid fixture that must fail schema/data validation

## Related

- `references/production-workflow.md`
- `references/player-architecture.md`
- `schema/reading_data.schema.json`
