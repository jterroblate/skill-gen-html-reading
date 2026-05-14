# Reading Player Production Workflow

## Scope

This skill currently stabilizes the **JSON → standalone HTML** layer.

It does not parse PDF/DOCX/OCR/screenshots, does not extract questions from raw
text, and does not run a complete agent-mediated LLM generation pipeline. Prepare
validated JSON first, then use this skill to render and QA the interactive HTML.

## One-Command Smoke Gate

Before shipping changes to the skill, run:

```bash
python3 -B scripts/smoke_test.py
```

The smoke test:

1. Confirms `schema/reading_data.schema.json` is valid JSON.
2. Runs built-in schema/data validation on good fixtures.
3. Generates temporary HTML for each good fixture.
4. Runs `scripts/validate_reading.py` on each generated HTML.
5. Confirms `fixtures/bad_missing_required.json` fails schema/data validation.
6. Writes only to a system temp directory.

Expected final line:

```text
SMOKE TEST PASSED ✅
```

Expected validator warning:

```text
WARNING: current output is not a strict student version because answers are embedded in HTML source/data attributes.
```

That warning is intentional for the current phase.

## Production Steps

### Step 1: Prepare JSON

Create JSON matching `schema/reading_data.schema.json`. Use checked-in fixtures as
examples:

- `fixtures/minimal_1_passage.json`
- `fixtures/escaping_edge_cases.json`
- `fixtures/full_5_passage_all_types.json`

Supported passage counts are **1, 3, or 5**. Each passage requires:

- `num`
- `title`
- `paras`
- `questions`

Each paragraph requires:

- `label`
- `text`

Each question block must use one supported type:

- `mcq`
- `tfng` / `true_false`
- `ynng` / `yes_no`
- `match`
- `fill`
- `summary`
- `heading_info` for heading passages

Heading passages additionally require:

- `questions.headings`
- `questions.answers`

### Step 2: Generate HTML

```bash
python3 -B scripts/generate_reading.py \
  --data /path/to/reading_data.json \
  --output /path/to/reading_practice.html
```

Generation fails before writing if required fields are missing, question types are
unsupported, answer/options are empty, or passage count is not 1/3/5.

### Step 3: Validate HTML

```bash
python3 -B scripts/validate_reading.py /path/to/reading_practice.html
```

Validator errors block delivery. Validator warnings must be understood and either
accepted for this phase or resolved in a later phase.

### Step 4: Manual Review

Open the generated HTML only when the user has explicitly authorized browser use.
Then manually test:

1. Passage tab switching
2. MCQ selection
3. TFNG/YNNG selection
4. Matching select
5. Fill and summary inputs
6. Heading drag/drop and click-heading-then-click-slot fallback
7. Heading answer boxes render in `.passage-col` before each target paragraph, not in `.questions-col`
8. Heading `.questions-col` contains only the title, brief instruction, and List of Headings / heading pool; it must not repeat `Paragraph A/B/C` answer-list rows
9. Submit scoring marks correct/wrong without exposing correct headings
9. Reveal buttons write full correct headings into the passage-side answer boxes
10. Reset current passage clears heading slots, used pool state, feedback, reveals, and score
10. Browser-side PDF score report, if network/CDN is available

## Validator Errors vs Warnings

Errors mean the output is structurally unsafe or incomplete and should not ship.
Examples:

- script/body/html tag mismatch
- duplicate closing tags
- div imbalance
- missing required DOM classes
- empty passage/question/reveal text
- missing MCQ options or answers
- heading pool without passage-side heading slots
- heading slots missing `data-para`, `data-q`, or full `data-answer-text`
- heading slot count not matching target paragraph count
- heading slots rendered in the questions column

Warnings currently include known product limitations. The main warning is answer
embedding in HTML source/data attributes; this means the output is not a strict
secure student version.

## Known Limitations

- No raw material ingestion: PDF/DOCX/OCR/screenshots/plain text are out of scope.
- No LLM task generation, answer evidence extraction, or agent result merge.
- No strict student/teacher split.
- No Word output.
- PDF support is only a browser-side score report using CDN libraries.
- Browser console/mobile layout gates are not automated yet.

## Later Phases

Do these after the JSON → HTML base is stable:

1. Agent/LLM task generation from raw text.
2. Agent result merge and semantic QA.
3. Teacher version with answers, explanations, evidence, and highlights.
4. Strict student version that does not expose answers in source.
5. PDF/Word export for student and teacher materials.
6. Browser automation smoke for console errors and mobile layout.
