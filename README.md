# skill-gen-html-reading

**IELTS Reading DOCX/JSON → Interactive HTML Generator**  
Version: [v1.0.0-candidate](VERSION.md)

## What It Does

Converts teacher-version IELTS Reading DOCX or structured JSON into standalone interactive reading practice HTML. The HTML supports MCQ, TFNG/YNNG, matching select, fill, summary completion, and heading matching with drag-and-drop, submit/reveal/reset/scoring.

## What It Does Not Do

- PDF/OCR/screenshot input
- General Word layout reconstruction
- Automatic question generation from unstructured prose
- Secure exam version (answers are in HTML source/data-attributes)

## Input Formats

1. **Teacher DOCX** (`.docx`) — via Module A DOCX pipeline
2. **Structured JSON** — matching `schema/reading_data.schema.json`

## Output Files

- `raw_docx_extraction.json` — DOCX raw extraction with source traces
- `source_audit.json` / `source_audit.md` — machine and human-readable audit reports
- `clean_reading_data_candidate.json` — schema-compatible JSON for Module B
- `reading_practice.html` — standalone interactive HTML

## Quick Start

### JSON → HTML

```bash
python3 -B scripts/generate_reading.py \
  --data fixtures/minimal_1_passage.json \
  --output /tmp/reading_minimal.html
python3 -B scripts/validate_reading.py /tmp/reading_minimal.html
```

### Full DOCX → HTML

```bash
python3 -B scripts/build_from_docx.py \
  --docx /path/to/teacher.docx \
  --out-dir /path/to/audit \
  --clean-json /path/to/clean.json \
  --html-output /path/to/practice.html
```

### Run all smoke tests

```bash
python3 -B scripts/smoke_test.py
python3 -B scripts/smoke_test_docx_pipeline.py
```

## Recommended Production Workflow

See `references/production-workflow.md` for detailed steps.

1. Extract DOCX → run `build_from_docx.py`
2. Check `source_audit.md` for PASS/blocking issues
3. Verify clean JSON validates (run `generate_reading.py`; it validates before writing)
4. Generate HTML → run `validate_reading.py`
5. Browser spot-check heading matching, submissions, reveals, reset, mobile viewport
6. Output with versioned filename (e.g. `_v1`, `_v2`) to avoid overwriting

## QA Commands

```bash
# Validate generated HTML
python3 -B scripts/validate_reading.py <path-to-html>

# Module B smoke
python3 -B scripts/smoke_test.py

# Module A (DOCX pipeline) smoke
python3 -B scripts/smoke_test_docx_pipeline.py
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `build_from_docx.py` exits with schema errors | Teacher DOCX format not recognized; check passage title/meta patterns |
| HTML validation fails | Missing answers in JSON, summary blank mismatch, leaked answer markers |
| Heading slots appear in questions column | JSON data not creating `heading_info` blocks correctly |
| MCQ options show `✓` / `[correct]` | DOCX used answer markers not stripped by normalizer |
| Reveal shows internal phrases | Source had no explanation; normalizer fell back to old template |

## Known Limitations

- Answers are visible in HTML source/data-attributes
- DOCX parsing tuned for IELTS Reading teacher versions
- Summary multi-blank blocks must use consolidated pair format
- 390px mobile layout is basic (column stack)
- Browser automation QA is not automated

## Version Status

[v1.0.0-candidate](VERSION.md) — pending verification on a fourth unit without code changes.

## References

- `references/docx-to-json-pipeline.md`
- `references/source-audit-rules.md`
- `references/production-workflow.md`
- `references/player-architecture.md`
- `schema/reading_data.schema.json`
