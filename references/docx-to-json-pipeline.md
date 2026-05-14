# DOCX → Reading JSON Pipeline

## Scope

Module A converts a teacher-version IELTS Reading DOCX into auditable structured data. It does **not** generate HTML directly. HTML remains Module B (`scripts/generate_reading.py`) and consumes only clean schema-compatible JSON.

Supported source path for the first implementation:

```text
Teacher DOCX / JSON draft
→ raw_docx_extraction.json
→ source_audit.json + source_audit.md
→ clean_reading_data_candidate.json
→ existing JSON→HTML generator
```

## Scripts

- `scripts/extract_docx_to_reading_json.py`
  - Reads DOCX paragraphs/runs via `python-docx`.
  - Produces raw extraction JSON with paragraph indices, style names, run styling, roles, passage/question candidates, answer-key candidates, source traces, and extraction warnings.
  - Output is intentionally close to the source and may contain conflicts.

- `scripts/audit_reading_source.py`
  - Reads raw extraction JSON.
  - Detects source conflicts and structural issues.
  - Writes machine-readable `source_audit.json` and Markdown `source_audit.md`.

- `scripts/normalize_reading_json.py`
  - Reads raw extraction + audit + optional human confirmations.
  - Produces schema-compatible clean reading JSON candidate.
  - Keeps `extraction_warnings` / `source_audit_summary` in top-level extra fields.
  - Blocking conflicts without confirmation can stop output unless `--allow-partial` is set.

- `scripts/build_from_docx.py`
  - One-command entrypoint for DOCX → raw → audit → clean JSON.
  - Optional `--html-output` delegates final HTML generation to `generate_reading.py`.

## Data Layers

### 1. raw_docx_extraction.json

Purpose: preserve source evidence.

Important fields:

- `input_file`
- `generated_at`
- `paragraphs[]`
  - `index`
  - `text`
  - `style`
  - `runs[]` with text/bold/italic/color
  - `role`
  - `passage_id`
- `passages[]`
  - `passage_id`, `title`, `band`, `genre`, `paragraphs`, `question_area`, `answer_key`
- `extraction_warnings[]`

### 2. source_audit.json / source_audit.md

Purpose: make uncertainty visible.

Issue fields:

- `issue_id`
- `severity`: `blocking`, `major`, `minor`
- `issue_type`
- `passage_id`
- `question_number`
- `source_locations`
- `conflicting_values`
- `evidence`
- `suggested_resolution`
- `confidence`
- `needs_human_confirmation`

### 3. clean_reading_data_candidate.json

Purpose: schema-compatible Module B input.

It must follow `schema/reading_data.schema.json` and may include extra top-level fields:

- `extraction_warnings`
- `source_audit_summary`
- `source_files`

## Human Confirmation

Optional confirmation file format:

```json
{
  "P1_Q8": {
    "answer": "routine",
    "confirmed_by": "JT",
    "note": "Matches passage and blank context."
  },
  "P2_Q9": {
    "answer": "FALSE",
    "confirmed_by": "JT",
    "note": "Passage says there is no single perfect ratio."
  }
}
```

Rules:

- Human confirmations override embedded DOCX answers and audit suggestions.
- The normalizer records confirmation use in warnings/source metadata.
- If a blocking issue lacks confirmation, normalization fails unless `--allow-partial` is passed.

## Non-goals

- PDF/OCR/screenshot parsing.
- General Word layout fidelity.
- HTML generation inside extractor/auditor/normalizer.
- Silent answer correction.
- Strict exam-security output.
