# Reading Source Audit Rules

The audit layer detects source risk before a DOCX is normalized into clean HTML-generator JSON.

## Verdict

- `PASS`: no blocking/major issues.
- `PARTIAL PASS`: major issues exist but a clean candidate may be generated with warnings or confirmations.
- `FAIL`: blocking issues prevent reliable clean JSON generation without human confirmation.

## Required Rules

### summary_answer_mismatch

Trigger when:

- A summary question contains N blanks but the answer line/key provides a different number of answers.
- Answer numbering ranges do not match blank numbers.
- A candidate answer looks suspicious for blank context.

Heuristics:

- Count `(number) ______` blanks in summary text.
- Parse answer lines such as `Answers: (11) output, (12) mental` and answer-key lines such as `11-13. output,mental,desks`.
- Compare counts and question numbers.
- Flag context mismatch when a candidate answer is incompatible with nearby lexical context, e.g. answer contains spaces for `about (12) ___ minutes`, or non-noun-looking answer after `life ___`.

### answer_key_conflict

Trigger when:

- Question-area embedded answer, e.g. `[FALSE]`, conflicts with answer-key entry, e.g. `9. TRUE`.
- MCQ option marked `[ANSWER]` conflicts with answer key.

Behavior:

- Record both values.
- Do not silently choose.
- Suggested answer may be provided if passage evidence and context are clear, but still mark confirmation need for major conflicts.

### missing_question

Trigger when:

- Answer key contains a question number absent from the question area.
- Question numbering jumps unexpectedly.

Behavior:

- Mark as major or blocking depending on whether a source can recover the question text.
- Do not fabricate missing questions. If an older HTML or human confirmation is used, record source and confidence.

### paragraph_split_issue

Trigger when:

- Passage paragraph labels skip, duplicate, or appear merged, e.g. `[E] ... [F] ...` in one DOCX paragraph.
- Heading answers reference a paragraph label that does not exist in extracted passage paragraphs.

Behavior:

- Suggest split when a bracket label marker is present inside a paragraph.
- Require confirmation if split point is not explicit.

### heading_structure_issue

Trigger when:

- Heading pool count is less than target paragraph count.
- Heading answer labels reference absent passage labels.
- Heading questions render as select/legacy list in clean JSON candidate.

### generator_display_issue

Trigger when:

- A problem belongs to JSON→HTML rendering rather than DOCX source quality, e.g. question header range based on block count rather than max question number.

Behavior:

- Classify separately; do not treat as source issue.
- Fix in Module B only if needed, with existing smoke tests.

## Report Tables

Markdown reports must include:

1. Overall Verdict
2. Input Files
3. Extraction Summary
4. Blocking Issues
5. Major Issues
6. Minor Issues
7. Question-Level Audit Table
8. Suggested Final Answer Table
9. Recommended Next Action
