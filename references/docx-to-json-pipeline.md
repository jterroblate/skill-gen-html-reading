# DOCX → Reading JSON Pipeline

## Scope

Module A converts a teacher-version IELTS Reading DOCX into auditable structured data. It does **not** generate HTML directly. HTML remains Module B (`scripts/generate_reading.py`) and consumes only clean schema-compatible JSON.

Supported source path:

```text
Teacher DOCX
→ raw_docx_extraction.json
→ source_audit.json + source_audit.md
→ clean_reading_data_candidate.json
→ HTML (via Module B)
```

## Scripts

- `scripts/extract_docx_to_reading_json.py`
  - Reads DOCX paragraphs/runs via `python-docx`.
  - Detects passage titles using multiple patterns:
    - `Reading Passage N — Title`
    - `P1 · Title`
    - Bare title line followed by Band/Level/Genre meta
  - Detects meta lines:
    - `Band X.X | Genre`
    - `Level: Band X.X · Genre`
    - `Genre: ...`
  - Handles implicit passage boundaries (next title+meta starts new passage)
  - Detects question markers like `Questions 1–4` (not just bare `Questions`)
  - Detects heading items (roman numerals), heading answer lines
  - Produces raw extraction JSON with paragraph indices, style names, run styling, roles, passage/question candidates, answer-key candidates, source traces, and extraction warnings.
  - Output is intentionally close to the source and may contain conflicts.

- `scripts/audit_reading_source.py`
  - Reads raw extraction JSON.
  - Detects source conflicts and structural issues:
    - `passage_detection_failure`: 0 or < 3 passages on full-unit source
    - `answer_key_conflict`: embedded answer vs answer key mismatch
    - `summary_answer_mismatch`: blank count vs answer count
    - `missing_question`: question in key but not in area
    - `heading_structure_issue`: pool count < targets
    - `paragraph_split_issue`: merged labels
  - Writes machine-readable `source_audit.json` and Markdown `source_audit.md`.
  - Verdicts: PASS, PARTIAL PASS, FAIL.

- `scripts/normalize_reading_json.py`
  - Reads raw extraction + audit + optional human confirmations.
  - Produces schema-compatible clean reading JSON candidate.
  - Extracts MCQ (with checkmark/correct-marker cleanup), TFNG/YNNG (inline mark stripping), matching select, fill, summary multi-blank, heading item/answer lines.
  - Uses teacher explanation text as reveal content; falls back to neutral `答案：{ans}。教师版标记该项为正确答案，但源文件未提供详细解析。`
  - Keeps `extraction_warnings` / `source_audit_summary` in top-level extra fields.
  - Blocking conflicts without confirmation can stop output unless `--allow-partial` is set.

- `scripts/build_from_docx.py`
  - One-command entrypoint for DOCX → raw → audit → clean JSON (→ optional HTML).
  - `--allow-partial` bypasses blocking issue check for development.
  - `--confirmed-answers` points to a manual override file.

## Data Layers

### 1. raw_docx_extraction.json

Purpose: preserve source evidence.

Key fields:
- `input_file`, `generated_at`
- `paragraphs[]`: index, text, style, runs (text/bold/italic/color), role, passage_id
- `passages[]`: passage_id, title, band, genre, linked_topics, source_locations, paragraphs, question_area, answer_key, heading_list, heading_answers, summary_answer_lines
- `extraction_warnings[]`: implicit_passage_boundary, paragraph_split_issue, others

### 2. source_audit.json / source_audit.md

Purpose: make uncertainty visible.

Issue fields:
- `issue_id`, `severity` (blocking/major/minor), `issue_type`
- `passage_id`, `question_number`, `source_locations`
- `conflicting_values`, `evidence`, `suggested_resolution`
- `confidence`, `needs_human_confirmation`

### 3. clean_reading_data_candidate.json

Purpose: schema-compatible Module B input.

Must follow `schema/reading_data.schema.json` and may include extra top-level fields:
- `extraction_warnings`
- `source_audit_summary`
- `source_files`

## Human Confirmation

Optional `confirmed_answers.json`:

```json
{
  "P1_Q8": {
    "answer": "routine",
    "confirmed_by": "JT",
    "note": "Matches passage and blank context."
  }
}
```

Rules:
- Human confirmations override embedded DOCX answers and audit suggestions.
- The normalizer records confirmation use in warnings.
- If a blocking issue lacks confirmation, normalization fails unless `--allow-partial`.

## Non-goals

- PDF/OCR/screenshot parsing
- General Word layout fidelity
- HTML generation inside extractor/auditor/normalizer
- Silent answer correction
- Strict exam-security output
