# Reading Player Production Workflow

## Scope

This skill now supports a full **teacher DOCX → interactive HTML** pipeline.
Module A (DOCX → clean JSON) and Module B (JSON → HTML) are both stable.
Audit-first design preserves source evidence and flags conflicts before clean JSON generation.

## One-Command Smoke Gate

Before shipping changes to the skill, run:

```bash
python3 -B scripts/smoke_test.py
python3 -B scripts/smoke_test_docx_pipeline.py
```

Both must PASS.

The `smoke_test.py` (Module B):
1. Confirms `schema/reading_data.schema.json` is valid JSON.
2. Runs built-in schema/data validation on good fixtures.
3. Generates temporary HTML for each good fixture.
4. Runs `scripts/validate_reading.py` on each generated HTML.
5. Confirms `fixtures/bad_missing_required.json` fails schema/data validation.
6. Writes only to a system temp directory.

The `smoke_test_docx_pipeline.py` (Module A):
1. Tests clean mock raw extraction → audit → normalize → generate → validate.
2. Tests U03-style DOCX (Reading Passage N — Title, Level: Band meta, no END separators) through extraction.
3. Tests conflict raw extraction (detects answer_key_conflict and summary_answer_mismatch).
4. Tests question patterns fixture (MCQ leakage, TFNG inline, summary multi-blank, matching, heading, reveal fallback).

## Production Steps

### Step 1: Run DOCX through the pipeline

```bash
python3 -B scripts/build_from_docx.py \
  --docx /path/to/teacher_version.docx \
  --out-dir /path/to/audit_output \
  --clean-json /path/to/clean_candidate.json \
  --html-output /path/to/practice.html \
  --allow-partial
```

If the source is known to have answer missing or conflicts, prepare a `confirmed_answers.json` first and pass `--confirmed-answers /path/to/confirmations.json`.

### Step 2: Check the audit report

Open `audit_output/source_audit.md`.

- **FAIL** with blocking passage_detection_failure → inspect title/meta format, may need extraction pattern update.
- **PASS** → proceed.
- **PARTIAL PASS** → review major issues; resolve with confirmations or skip if acceptable (for development).

### Step 3: Verify clean JSON

The `generate_reading.py` script performs schema validation before writing HTML.
If it succeeds, the JSON is structurally valid.

### Step 4: Validate generated HTML

```bash
python3 -B scripts/validate_reading.py /path/to/practice.html
```

Errors block delivery. Warnings must be understood (expected: answer-in-source warning).

### Step 5: Browser spot check

Only perform when the user has explicitly authorized browser use.

Test:
1. Passage tab switching
2. MCQ selection and submit feedback
3. TFNG/YNNG selection and submit feedback
4. Matching select
5. Fill and summary inputs
6. Heading drag/drop and click-heading-then-click-slot fallback
7. Heading answer boxes render in `.passage-col` only, not `.questions-col`
8. `.questions-col` contains only instruction, heading pool; no legacy Paragraph A/B/C answer list
9. Submit scoring marks correct/wrong without exposing answers
10. Reveal buttons write correct answers into slots
11. Reset clears all state for current passage
12. 390px viewport with no horizontal overflow
13. Console errors = 0 (ignore favicon 404)

### Step 6: Version output

Do not overwrite previous outputs. Save with version suffix:

- `reading_unit_v1_docx_pipeline.json`
- `reading_unit_刷题_v1_docx_pipeline.html`

Update acceptance report if applicable.

## Validator Errors vs Warnings

**Errors** mean the output is structurally unsafe or incomplete and should not ship.
Examples:
- script/body/html tag mismatch
- duplicate closing tags
- div imbalance
- missing required DOM classes
- empty passage/question/reveal text
- missing MCQ options or answers
- heading pool without passage-side heading slots
- heading slots rendered in questions column
- visible answer leakage markers in MCQ options or TFNG statements
- internal template phrases in reveal text

**Warnings** currently include known product limitations:
- `current output is not a strict student version because answers are embedded in HTML source/data attributes.`

## Human Override File

When the teacher DOCX has an unusual answer format or the normalizer extracts an incorrect answer, create a `confirmed_answers.json`:

```json
{
  "P1_Q8": {
    "answer": "routine",
    "confirmed_by": "JT",
    "note": "Matches passage evidence."
  }
}
```

Pass it to the pipeline:

```bash
python3 -B scripts/build_from_docx.py \
  --docx teacher.docx \
  --out-dir audit_dir \
  --confirmed-answers confirmed_answers.json \
  --clean-json clean.json \
  --html-output practice.html
```

## Known Limitations

- Answers are embedded in HTML `data-ans` attributes. Not a strict secure student version.
- DOCX extraction is tuned for teacher-version IELTS Reading documents. General Word layouts may not parse.
- No PDF/OCR/screenshot input.
- No automatic question generation from unstructured prose.
- Browser automation QA (console errors, mobile layout) is not automated.
- Summary multi-blank blocks must use consolidated pair format in clean JSON.
