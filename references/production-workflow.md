# Reading Player Production Workflow

## Full Pipeline

### Step 1: Define Passage Data

Create a JSON file with all 5 passages. Each passage includes:
- Title and metadata (band, genre)
- Paragraphs with labels (A, B, C, ...)
- Question blocks with types, stems, options, answers

### Step 2: Generate HTML

```bash
python scripts/generate_reading.py \
  --title "IELTS Reading · U01 日常节奏" \
  --output "/path/to/刷题.html" \
  --data /path/to/passage_data.json
```

### Step 3: Validate

```bash
python scripts/validate_reading.py "/path/to/刷题.html"
```

### Step 4: Review in Browser

Open the HTML file in Chrome:
```bash
open "/path/to/刷题.html"
```

### Step 5: Test Interactions

1. **Tab switching**: Click P1–P5 to verify passage switching
2. **Heading drag**: Drag headings from pool to slots before paragraphs
3. **Submit**: Click submit to verify red/green feedback
4. **Reveal**: Click "显示解析" buttons
5. **Reset**: Click reset to verify all state clears
6. **PDF Export**: Click "下载 PDF" to verify export
7. **Score**: Verify score badge updates correctly
8. **All question types**: Test MCQ, TFNG, Match-Select, Fill-Input

## Quick Reference

### Data JSON Structure

```json
{
  "title": "IELTS Reading · U01 Daily Rhythm",
  "header_title": "IELTS Academic Reading · U01 日常节奏",
  "header_sub": "P1 \"Title\" · Band X.X-X.X · Genre",
  "passages": [
    {
      "num": 1,
      "title": "Passage Title",
      "band": "5.5-6.0",
      "genre": "Social Observation",
      "meta": "Band 5.5-6.0 · Social Observation · Linked: keywords",
      "paras": [
        {"label": "A", "text": "Paragraph text..."}
      ],
      "questions": {
        "type": "regular|heading",
        "headings": [["i", "Heading text"], ...],  // only for heading type
        "answers": {"A": "iii", ...},                // only for heading type
        "blocks": [
          {"q": 1, "type": "mcq", "stem": "...", "options": ["A) ...", "B) ..."], "answer": "A", "reveal": "..."}
        ]
      }
    }
  ]
}
```

### Question Types

| Type Field | Builder Used | Data Fields |
|-----------|-------------|-------------|
| `mcq` | `build_mcq()` | `q`, `stem`, `options` (list), `answer`, `reveal` |
| `tfng` | `build_tfng()` | `q`, `statement`, `answer`, `reveal` |
| `ynng` | `build_ynng()` | `q`, `statement`, `answer`, `reveal` |
| `match` | `build_match_select()` | `q`, `text`, `options` (list), `answer`, `reveal` |
| `fill` | `build_fill()` | `q`, `before`, `after`, `answer`, `width`, `reveal` |
| `heading_info` | (inline) | `q`, `reveal` |

### Important: heading-info blocks
For heading-matching passages, create `heading_info` blocks for each heading question (Q1–Q5 or Q1–Q6). These just show the paragraph label + reveal button. The actual drag-slot is in the passage column.

### Important: action-bar position
The submit/reset/score bar is placed **between the tab bar and header**, not at the bottom. The PDF export section is also at the top. This keeps the layout clean and avoids wasted space.

### Important: heading text display
The `placeHeading` function reads `item.textContent.trim()` to get the **full heading text** (e.g., "iii. Recognising when change is needed"), not just the key. The display uses `<b>fullText</b>`.

## Common Issues

### 1. Div Balance
If divs are unbalanced, the layout will break. Always validate after generation.
The most common cause is a missing closing `</div>` in a question block builder.

### 2. Surrogates in emoji
Use actual UTF-8 emoji characters, not surrogate escapes like `\ud83d\udd04`.
Use `\U0001F504` (Python) or the raw emoji character directly.

### 3. Passage-col heading-slot grading
The `gradePanel()` function checks BOTH `qCol.querySelectorAll('.heading-slot')` AND
`panel.querySelectorAll('.passage-col .heading-slot')`. If one is missing, heading
answers won't be graded.

### 4. Pool lookup
`placeHeading` and `clickSlot` find the heading pool using
`slot.closest('.passage-panel').querySelector('.heading-pool')`.
This works for both passage-col and questions-col slots because both are inside `.passage-panel`.
