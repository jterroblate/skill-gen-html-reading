# Reading Player Architecture Reference

## Current Architecture

The player is a standalone HTML document generated from structured JSON. It uses:

- Dynamic passage tabs for **1, 3, or 5** passages
- A compact top action bar
- A two-column passage/question layout
- Inline CSS and JS
- HTML5 drag/drop for heading matching
- Browser-side score report PDF through jsPDF/html2canvas CDN

The generator is intentionally scoped to rendering validated JSON. It does not
parse source documents or invoke LLMs.

## Page Structure

```text
Page
├── .tab-bar
│   └── .tab-btn × passage count
├── .action-bar
│   ├── submitAnswers button
│   ├── resetAll button
│   └── #scoreBadge
├── .pdf-section
├── .header
│   ├── h1
│   └── #headerSub
└── .layout
    └── .passage-panel[data-p] × passage count
        ├── .passage-col
        │   ├── .p-title
        │   ├── .p-meta
        │   ├── .heading-slot + .answer-reveal before paragraph (heading passages)
        │   └── .para × paragraph count
        └── .questions-col
            ├── question heading
            ├── .heading-pool (heading passages)
            └── .q-block × question count
```

## Data Injection

`passageInfo` and `passageNums` are injected into JavaScript via `json.dumps`, not
manual single-quoted string assembly. Passage/question text is escaped before it
enters HTML text or attributes.

This matters because IELTS materials often contain:

- `<` / `>`
- `&`
- single and double quotes
- slash `/`
- long dash `—`
- curly quotes `‘’` / `“”`

The escaping fixture must pass smoke tests.

## Heading Matching

Heading passages use:

```html
<div class="heading-pool">
  <span class="heading-item" draggable="true" data-heading="i">i. Heading text</span>
</div>

<div class="heading-drop-row" data-para="A" data-q="1">
  <div class="heading-drop-label">Q1 · Paragraph A heading</div>
  <div class="heading-slot" data-p="3" data-para="A" data-q="1"
       data-ans="ii" data-answer-text="ii. Full heading text">
    <span class="slot-placeholder">拖拽或点选右侧 heading 后放到这里</span>
  </div>
</div>
```

Rules:

- Heading slots appear before each matching paragraph in `.passage-col`.
- Each slot binds to the paragraph and question via `data-para` + `data-q`.
- Heading pool stays in `.questions-col` and uses full-width readable heading items.
- `.questions-col` must not render the old `1. Paragraph A`, `2. Paragraph B` answer list when inline passage-side slots are enabled.
- Users can drag a heading, or click a heading item and then click the target slot.
- `placeHeading()` writes the full heading text into the slot, not only the roman numeral.
- `gradePanel()` checks `.passage-col .heading-slot`; wrong slots show wrong-only styling but do not reveal the correct answer.
- `revealHeadingSlot()` writes the full correct heading into the passage-side slot.
- `resetAll()` clears slot values, feedback classes, selected/used heading state, reveal text, score, and submit state for the active passage only.

## Question Types

| Type | Element | Required data |
|---|---|---|
| `mcq` | `.mcq-group` + `.mcq-opt` | `stem`, `options`, `answer` |
| `tfng` / `true_false` | `.tfng-group` | `statement`, `answer` |
| `ynng` / `yes_no` | `.ynng-group` | `statement`, `answer` |
| `match` | `.match-select` | `text`, `options`, `answer` |
| `fill` | `.fill-input` | `answer`, optional `before/after` |
| `summary` | `.fill-input` per pair | `pairs` |
| `heading_info` | `.q-block` + reveal | `q`, optional `label/reveal` |

## Grading

`gradePanel()` grades only the current passage panel:

1. MCQ selected option letter vs `data-ans`
2. TFNG/YNNG selected value vs `data-ans`
3. Matching select value vs `data-ans`
4. Fill/summary input normalized lowercase vs `data-ans`
5. Heading slot `data-val` vs `data-ans`

It then stores state in `pState[currentPassage]`, disables submit, shows score,
and enables reveal buttons.

## Reset

`resetAll()` resets the current passage only:

- feedback classes
- selected choices
- fill inputs
- matching selects
- heading slots and pool items
- reveal visibility/buttons
- score badge and PDF section

## Validation Gate

`validate_reading.py` checks the generated HTML for:

- html/body/script tag counts
- duplicate trailing closing tags
- div balance
- required DOM elements/functions
- tab/passage count consistency
- non-empty paragraphs/questions/reveals
- required options/answers by type
- heading pool/slot/item structure
- visible answer leakage (MCQ options, TFNG statements)
- internal template phrases in reveal text

It also emits the current answer-leakage warning because answers are embedded in
source/data attributes.

## Compact Heading Dropbox Style (v2+)

Starting from v2, heading slots use a compact inline layout:

- `.heading-drop-row` is a flex row (label + drop slot on one line)
- Slot `min-height: 30px` (previously 42px)
- Row margin: `8px 0 4px`, padding: `6px 8px`
- Slot padding: `5px 8px`
- Label: `Q1 / Paragraph A` (previously `Q1 · Paragraph A heading`)
- Placeholder: `拖入 heading / Drop heading` (previously longer text)
- Reveal prefix: `Correct: ` (previously `正确答案：`)
- At 430px and below, the flex direction adapts for narrow viewports
- Validator checks `.passage-col .heading-slot` and `.questions-col .heading-slot == 0`

## Known Product Limitation

The current HTML is not a secure student version. It hides answers in the UI until
submit/reveal, but answers remain visible in source. A later strict student/teacher
split must solve this at the product level.
