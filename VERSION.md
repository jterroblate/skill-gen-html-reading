# VERSION.md

**Version**: v1.0.0-candidate  
**Last verified commit**: `8d0c51d`  
**Date**: 2026-05-15

## Verified On

- **U01** (used as initial fixture during development)
- **U02** (童年与成长 — 5 passages, 59 questions, all types)
- **U03** (人际关系 — 5 passages, 62 questions, all types)

No real passage/question/answer content from these units is committed to this repository. Only structural features are covered by synthetic regression fixtures.

## Supported Question Types

- MCQ (A/B/C/D)
- TFNG (True / False / Not Given)
- YNNG (Yes / No / Not Given)
- Matching select (paragraph/information matching)
- Fill (single blank)
- Summary (multi-blank completion)
- Heading matching (drag-and-drop inline compact dropboxes)

## Required QA Before Release

1. `python3 -B scripts/smoke_test.py` — PASS
2. `python3 -B scripts/smoke_test_docx_pipeline.py` — PASS
3. `python3 -B scripts/validate_reading.py` on generated output — PASS
4. Browser spot check:
   - Tab switching for correct passage count
   - MCQ/TFNG/YNNG selection and submission feedback
   - Fill/summary input and matching select
   - Heading drag/drop and click-heading-then-click-slot
   - Heading slots in `.passage-col` only, not `.questions-col`
   - Submit and reveal (no answer leakage in visible text)
   - Reset clears all state
   - 390px viewport with no horizontal overflow

## v1.0.0-Candidate Rationale

This version is a **v1.0.0-candidate** because:

- All three modules (A: DOCX→JSON, B: JSON→HTML, C: validation/smoke) are stable.
- Two real teacher DOCX units (U02, U03) have been verified through the full pipeline.
- Regression fixtures lock in all fixed formats and detection patterns.
- Smoke tests document coverage.

It is not yet v1.0.0 because it has only been run on 3 units (U01 as fixture, U02/U03 as real DOCX). The next new unit run without code changes should upgrade to v1.0.0.

## Known Limitations

- Answers are embedded in HTML `data-ans` attributes. Not a strict secure student version.
- DOCX extraction is tuned for teacher-version IELTS Reading DOCX with clear passage/question/answer-key structure; not a general Word layout parser.
- The normalizer extracts fewer atomic questions than source totals in some edge cases (documented in per-unit acceptance reports).
- No PDF/OCR/screenshot input support.
- No automatic question generation from unstructured prose.
