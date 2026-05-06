---
name: skill-gen-html-reading
description: >
  Generate interactive IELTS reading practice HTML with heading-matching drag-and-drop,
  MCQ, TFNG, info matching, and summary completion. Supports 5-passage layout with
  heading slots BEFORE each paragraph (draggable), submit/reveal/reset, and PDF export.
  Trigger when user requests: reading practice HTML, 阅读刷题HTML, reading player,
  heading matching drag-and-drop, or any IELTS reading practice interface.
---

# IELTS Reading Player Generator

## Purpose

Generate a fully interactive IELTS Academic Reading practice HTML file from supplied
passage content and question data. The output is a standalone HTML file with:

- 5 passages with tab switching (P1–P5)
- Left column: passage text with interactive elements
- Right column: questions + draggable heading pool
- **Heading matching**: drag-and-drop slots before each paragraph in the passage column
- Question types supported: MCQ, TFNG (True/False/Not Given), YNNG (Yes/No/Not Given),
  Matching Information (dropdown select), Summary Completion (fill input)
- Submit → red/green feedback → reveal explanations → PDF export

## Quick Start

```bash
python scripts/generate_reading.py \
  --title "IELTS Reading · U01 Daily Rhythm" \
  --output "/path/to/刷题.html" \
  --data /tmp/passage_data.json
```

Validate output:

```bash
python scripts/validate_reading.py "/path/to/刷题.html"
```

## Input JSON Schema

The `--data` JSON file defines all 5 passages:

```json
{
  "title": "IELTS Academic Reading · U01 日常节奏",
  "passages": [
    {
      "num": 1,
      "title": "The Morning People",
      "meta": "Band 5.5-6.0 · Social Observation · Linked: Morning routines, daily habits, self-discipline",
      "paras": [
        {"label": "A", "text": "At precisely 5:30 every morning..."},
        {"label": "B", "text": "Mrs Chen is what researchers describe..."},
        ...
      ],
      "questions": {
        "type": "regular",
        "blocks": [
          {"q": 1, "type": "mcq", "stem": "What characterises Mrs Chen's approach...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "B"},
          {"q": 2, "type": "tfng", "statement": "Mrs Chen started her routine...", "answer": "FALSE"},
          {"q": 3, "type": "fill", "text": "Irregular sleep patterns can cause ___...", "answer": "social jetlag"}
        ]
      }
    },
    {
      "num": 2,
      ...
    },
    ...
  ]
}
```

For heading-matching passages (the `type` field is `"heading"` instead of `"regular"`):

```json
{
  "num": 3,
  "title": "How I Learned to Walk Again",
  "paras": [{"label": "A", "text": "..."}, ...],
  "questions": {
    "type": "heading",
    "headings": [
      {"key": "i", "text": "A small commitment that grew naturally"},
      {"key": "ii", "text": "How movement changed my thinking"},
      ...
    ],
    "answers": {"A": "iii", "B": "i", "C": "ii", "D": "iv", "E": "v"},
    "blocks": [
      {"q": 6, "type": "mcq", ...},
      ...
    ]
  }
}
```

## HTML Architecture

```
┌─────────────────────────────────────────┐
│  Tab Bar: P1 P2 P3 P4 P5               │
├─────────────────────────────────────────┤
│  Action Bar: [提交答案] [重置本篇] 得分  │
├─ 成绩导出 (compact, shown after submit) ─┤
├─ Header: title + subtitle ──────────────┤
├─────────────────────────────────────────┤
│  ┌─ Passage Col ───┬─ Questions Col ──┐  │
│  │ [拖拽标题至此]   │  Heading Pool     │  │
│  │ [💡 显示解析]    │  (draggable)      │  │
│  │ Paragraph A      │  MCQ / TFNG       │  │
│  │ ...             │  Fill inputs       │  │
│  │ [拖拽标题至此]   │                    │  │
│  │ [💡 显示解析]    │                    │  │
│  │ Paragraph B      │                    │  │
│  │ ...             │                    │  │
│  └─────────────────┴──────────────────┘  │
└─────────────────────────────────────────┘
```

## Key Design Decisions

### Heading Matching
- Drop zone (`<div class="heading-slot">`) appears **before each paragraph** in passage column
- Heading pool (`<div class="heading-pool">`) with draggable `<span>` items stays in questions column
- PlaceHeading JS reads `item.textContent.trim()` for **full heading text display** (not just key)
- Click on filled slot clears it (returns heading to pool)
- Submit grades passage-col heading-slots via `gradePanel()`

### Action Bar Position
- Submit/Reset/Score buttons are in a compact bar **between the tab bar and header**
- PDF export section is also at the top (below action bar, above header)
- NOT at the bottom where it takes space

### Answer Reveal
- "💡 显示解析" buttons are **auto-generated** before each `.answer-reveal` element
- For heading matching: the answer-reveal is in the passage column (after heading-slot)
- Reveal buttons are disabled until submit, then enabled
- On reveal, correct answers are highlighted in green, wrong in red

## Related

- [player-architecture.md](references/player-architecture.md)
- [production-workflow.md](references/production-workflow.md)
- [skill-gen-reading-listening SKILL.md](../skill-gen-reading-listening/SKILL.md)
