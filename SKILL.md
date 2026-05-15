---
name: skill-gen-html-reading
description: >
  Generate interactive IELTS reading practice HTML from structured JSON data with
  heading-matching drag-and-drop, MCQ, TFNG/YNNG, matching select, fill, summary
  completion, submit/reveal/reset/scoring, source-audit, DOCX-to-JSON extraction,
  and smoke-testable regression fixtures. Trigger when user requests: reading
  practice HTML, 阅读刷题HTML, reading player, heading matching drag-and-drop,
  or an IELTS reading practice interface.
---

# IELTS Reading DOCX/JSON to Interactive HTML Generator — v1.0.0-candidate

## Current Scope

This skill has three stable modules:

- **Module A (stable): teacher DOCX → raw extraction → source audit → clean structured JSON candidate.**
- **Module B (stable): structured JSON → standalone IELTS Reading interactive HTML.**
- **Module C (stable): schema validation, source audit, regression smoke tests, visible answer leakage checks, heading interaction QA.**

Modules are designed for a **teacher-version source → student-practice HTML** workflow.
Module A is intentionally audit-first: it preserves source traces, warnings, and
confidence instead of silently fixing source conflicts.

## Supported Question Types

- MCQ (multiple choice, A/B/C/D)
- TFNG (True / False / Not Given)
- YNNG (Yes / No / Not Given)
- Matching select (paragraph/information matching)
- Fill (single blank inline)
- Summary (multi-blank completion paragraph)
- Heading matching (drag-and-drop inline compact dropboxes)

## What It Does Not Support

- PDF input parsing
- OCR or screenshot understanding
- Arbitrary Word layout reconstruction (only teacher DOCX with clear passage/question/answer-key structure)
- Pure-text automatic question generation from unstructured prose
- Strict student-version security against viewing answers in HTML source
- LLM or agent-mediated question extraction

## Output

The generator produces a single standalone HTML file with:

- Dynamic passage tabs; supported counts: **1, 3, or 5**
- Left column: passage text with inline heading dropboxes
- Right column: questions, heading pool, and instructions
- Compact inline heading matching slots (drag/drop plus click-heading-then-click-slot)
- Submit → red/green feedback without revealing correct answers
- Reveal buttons after submit; heading reveal writes the full correct heading into the passage-side answer box
- Reset current passage clears all state
- Score display and browser-side score report PDF via jsPDF/html2canvas CDN

**Important limitation**: answers are embedded in HTML `data-ans` attributes and hidden
reveal blocks. The output is fine for practice UX but is **not a strict secure student version**.

## Quick Start

### Module B only: JSON → HTML

```bash
python3 -B scripts/generate_reading.py \
  --data fixtures/minimal_1_passage.json \
  --output /tmp/reading_minimal.html
```

Validate generated HTML:

```bash
python3 -B scripts/validate_reading.py /tmp/reading_minimal.html
```

Run smoke tests:

```bash
python3 -B scripts/smoke_test.py
python3 -B scripts/smoke_test_docx_pipeline.py
```

### Full pipeline: DOCX → HTML

```bash
python3 -B scripts/build_from_docx.py \
  --docx /path/to/teacher.docx \
  --out-dir /path/to/docx_to_json_audit \
  --clean-json /path/to/clean_candidate.json \
  --html-output /path/to/reading_practice.html \
  --allow-partial
```

## Input Data Contract

Formal schema: `schema/reading_data.schema.json`

The generator also performs built-in schema/data validation before writing HTML.
See fixtures in `fixtures/` for examples.

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

## CLI Entry Points

| Step | Command | Key args |
|---|---|---|
| DOCX → full pipeline | `scripts/build_from_docx.py` | `--docx`, `--out-dir`, `--clean-json`, `--html-output`, `--confirmed-answers`, `--allow-partial` |
| DOCX → raw extraction | `scripts/extract_docx_to_reading_json.py` | `--docx`, `--output` |
| Raw → audit | `scripts/audit_reading_source.py` | `--raw`, `--json-output`, `--md-output`, `--clean-json`, `--html` |
| Raw + audit + confirm → clean JSON | `scripts/normalize_reading_json.py` | `--raw`, `--audit`, `--output`, `--confirmed-answers`, `--allow-partial` |
| Clean JSON → HTML | `scripts/generate_reading.py` | `--data`, `--output`, `--title` |
| HTML validation | `scripts/validate_reading.py` | HTML file path |
| Smoke tests | `scripts/smoke_test.py` | none |
| DOCX pipeline smoke test | `scripts/smoke_test_docx_pipeline.py` | none |

## Question Block Reference

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

## Validation

`validate_reading.py` checks:

- HTML structure (tag counts, div balance, closing tags)
- Required DOM classes and interaction functions
- Passage/tab/panel consistency
- Non-empty text, questions, reveals
- Complete MCQ options and `data-ans`
- Fill/summary answers
- Heading pool, slot count/position, interaction functions
- Visible answer leakage fails: MCQ options, TFNG/YNNG statements must not contain answer markers
- Reveal content must not contain internal template phrases (extracted from teacher answer key, marked option, source trace, etc.)
- Summary diagnostic: fill-input missing `data-ans`, duplicate question numbers

Expected warning:

```text
WARNING: current output is not a strict student version because answers are embedded in HTML source/data attributes.
```

This warning is intentional until a strict student/teacher split exists.

## Source Audit Rules

See `references/source-audit-rules.md` for full detail.

- `passage_detection_failure`: 0 or 1 passage extracted from a full-unit source → blocking or major
- `answer_key_conflict`: embedded answer in question area conflicts with Answer Key
- `summary_answer_mismatch`: blank count does not match answer line
- `missing_question`: answer key contains a question number absent from question area
- `heading_structure_issue`: heading pool < target paragraphs; label references missing
- `paragraph_split_issue`: multiple labels in one DOCX paragraph; label not extracted

## When Human Confirmation Is Required

- Source audit verdict = FAIL (blocking issues)
- Major answer conflicts (embedded answer ≠ answer key)
- Missing questions from source
- Summary blank/answer count mismatch
- Passage count significantly off
- Any blocking issue

A `confirmed_answers.json` file can override source-extracted answers:

```json
{
  "P1_Q8": {
    "answer": "routine",
    "confirmed_by": "JT",
    "note": "Matches passage and blank context."
  }
}
```

## When Generated HTML Is Ready for Delivery

1. Source audit verdict: PASS (or PARTIAL PASS with confirmed resolutions)
2. No blocking issues unresolved
3. No major unresolved issues
4. Clean JSON passes schema/runtime validation
5. Generated HTML passes `validate_reading.py`
6. Both smoke tests pass
7. Browser spot check passes (tab switching, MCQ/TFNG interaction, heading drag/click/check/reveal/reset, 390px no overflow)

## Fixtures

| Fixture | Purpose |
|---|---|
| `fixtures/minimal_1_passage.json` | Minimal valid 1-passage fixture |
| `fixtures/heading_matching_inline_dropboxes.json` | Single heading passage regression |
| `fixtures/escaping_edge_cases.json` | 3-passage fixture with special characters |
| `fixtures/full_5_passage_all_types.json` | 5-passage fixture covering all types including multi-blank summary |
| `fixtures/bad_missing_required.json` | Invalid fixture that must fail schema validation |
| `fixtures/docx_extraction/mock_raw_extraction_clean.json` | Clean DOCX extraction mock for pipeline smoke |
| `fixtures/docx_extraction/mock_raw_extraction_question_patterns.json` | MCQ leakage / TFNG inline / summary multi-blank / matching / heading / reveal regression |
| `fixtures/source_audit/mock_raw_extraction_conflict.json` | Fixture with intentional answer key conflicts |

## References

- `references/docx-to-json-pipeline.md` — Module A architecture and data layers
- `references/source-audit-rules.md` — Audit verdict and rule definitions
- `references/production-workflow.md` — Full production pipeline steps
- `references/player-architecture.md` — Module B HTML player structure
- `schema/reading_data.schema.json` — Formal input data schema
