# Reading Player Architecture Reference

## Two-Column Panel Model

The reading player uses a **two-column flex layout** with a sticky action bar at the top.
Passage switching is instant (no page load) via CSS class toggling on `.passage-panel`.

### Component Tree

```
Page
├── .tab-bar
│   ├── .tab-btn "P1" → switchPassage(1)
│   ├── .tab-btn "P2" → switchPassage(2)
│   ├── .tab-btn "P3" → switchPassage(3)
│   ├── .tab-btn "P4" → switchPassage(4)
│   └── .tab-btn "P5" → switchPassage(5)
├── .action-bar (compact, at top)
│   ├── .btn-primary (提交答案)
│   ├── .btn-secondary (重置本篇)
│   └── .score-badge
├── .pdf-section (compact, at top, hidden)
│   ├── Name input
│   ├── Date input
│   └── Download PDF button
├── .header
│   ├── h1 (page title)
│   └── .sub (current passage title + band)
└── .layout
    ├── .passage-col (left, scrollable)
    │   ├── .p-title
    │   ├── .p-meta
    │   ├── .heading-slot (×N, for heading-matching passages)
    │   ├── .answer-reveal (after heading-slot, for heading-matching)
    │   └── .para (×N)
    └── .questions-col (right, scrollable)
        ├── Questions 1–N header
        ├── .heading-pool (draggable heading items, for heading-matching only)
        ├── .q-block (MCQ/TFNG/Summary/Info-Match)
        │   ├── .q-text
        │   ├── .mcq-group / .tfng-group / select / input
        │   └── .answer-reveal
        └── .action-bar (inside qcol, sticky at bottom)
```

## Heading Matching Architecture

### Drag Source (Heading Items)

```html
<div class="heading-pool" id="p3-heading-pool">
  <span class="heading-item" draggable="true" data-heading="i"
        ondragstart="dragHeading(event)" ondragend="dragEnd(event)">
    i. A small commitment that grew naturally
  </span>
  <span class="heading-item" draggable="true" data-heading="ii"
        ondragstart="dragHeading(event)" ondragend="dragEnd(event)">
    ii. How movement changed my thinking
  </span>
  ...
</div>
```

- `draggable="true"` enables HTML5 drag
- `data-heading` stores the key (e.g., "iii")
- `.used` class + `draggable=false` after placing
- `.dragging` class during drag for visual feedback

### Drop Target (Heading Slots)

```html
<div class="heading-slot" data-p="3" data-para="A" data-q="1" data-ans="iii"
     ondragover="allowDrop(event)" ondrop="dropHeading(event)" onclick="clickSlot(this)">
  <span class="slot-placeholder">拖拽标题至此</span>
</div>
<div class="answer-reveal" data-reveal="1">✅ iii — Recognising when change is needed</div>
```

- Always placed **before** the paragraph it matches
- `data-p`, `data-para`, `data-q`, `data-ans` store matching metadata
- `.filled` class after a heading is dropped
- `.dragover` class during drag hover
- `.correct` (green) / `.wrong-only` (red) after submit
- Clicking a filled slot clears it (via `clickSlot`)

### Place Heading Flow

1. `dragHeading()` → sets `dataTransfer` with heading key
2. `allowDrop()` → prevents default, adds `.dragover`
3. `dropHeading()` → reads heading key, calls `placeHeading()`
4. `placeHeading()` → finds pool in same `.passage-panel`, gets full text from item,
   marks item as `.used`, sets slot HTML to full heading text
5. `clickSlot()` → clears slot, unmarks pool item

### Key JS Difference from U03

In U03, heading-slots and pool are both in `.questions-col`.
In this player, heading-slots are in `.passage-col`.

```javascript
// WRONG (U03): finds pool within questions-col
var pool = slot.closest('.questions-col').querySelector('.heading-pool');

// CORRECT: finds pool anywhere in the passage panel
var pool = slot.closest('.passage-panel').querySelector('.heading-pool');
```

## Question Types

| Type | CSS | HTML Element | Answer |
|------|-----|-------------|--------|
| MCQ | `.mcq-group` | `div.mcq-opt` (clickable) | Letter A/B/C/D |
| TFNG / YNNG | `.tfng-group` / `.ynng-group` | `div.tfng-btn` / `div.ynng-btn` | TRUE/FALSE/NOT GIVEN or YES/NO/NOT GIVEN |
| Info Match | `.match-select` | `<select>` with A/B/C/D/E/F options | Letter |
| Heading Match | `.heading-slot` | Drag-and-drop slot | Heading key (e.g., "iii") |
| Fill-in | `.fill-input` | `<input>` | Text (case-insensitive match) |

## Grading

`gradePanel()` function:
1. Clears all `.wrong-only` and `.correct` classes
2. Iterates `.mcq-group`, `.tfng-group`, `.ynng-group`, `.match-select`, `.fill-input`, `.heading-slot`
3. Questions-col and passage-col heading-slots are both checked
4. Adds `.correct` (green) or `.wrong-only` (red) to each answered element

## Reset Flow

1. Clear `.wrong-only`, `.correct`, `.selected` classes
2. Reset all `.heading-slot`: restore placeholder text, remove `.filled`
3. Reset all pool items: remove `.used`, set `draggable=true`
4. Hide `.answer-reveal` elements
5. Hide `.pdf-section`
6. Re-enable submit button, clear score badge

## PDF Export

Built with jsPDF + html2canvas (loaded from CDN). After submit:
- Collects student name, date, score data
- Generates PDF with passage title, score, and wrong-answer details
- Downloads via `doc.save()`
