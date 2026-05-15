#!/usr/bin/env python3
"""Validate generated IELTS reading practice HTML.

This validator is intentionally conservative: errors block use, warnings describe
known delivery limitations (for example, embedded answers in the HTML source).
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class ReadingHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.start_counts = {}
        self.end_counts = {}
        self.attrs_by_class = []
        self.stack = []
        self.div_balance = 0

    def handle_starttag(self, tag, attrs):
        self.start_counts[tag] = self.start_counts.get(tag, 0) + 1
        attr = dict(attrs)
        self.tags.append((tag, attr))
        if tag == "div":
            self.div_balance += 1
        cls = attr.get("class", "")
        if cls:
            self.attrs_by_class.append((tag, cls, attr))

    def handle_endtag(self, tag):
        self.end_counts[tag] = self.end_counts.get(tag, 0) + 1
        if tag == "div":
            self.div_balance -= 1


def count(pattern: str, html: str) -> int:
    return len(re.findall(pattern, html, flags=re.IGNORECASE))


def class_present(parser: ReadingHTMLParser, cls_name: str) -> bool:
    return any(cls_name in cls.split() for _, cls, _ in parser.attrs_by_class)


def attrs_for_class(parser: ReadingHTMLParser, cls_name: str):
    return [attrs for _, cls, attrs in parser.attrs_by_class if cls_name in cls.split()]


def text_inside_blocks(html: str, cls: str):
    pattern = re.compile(rf'<[^>]+class="[^"]*\b{re.escape(cls)}\b[^"]*"[^>]*>(.*?)</[^>]+>', re.I | re.S)
    return [re.sub(r'<[^>]+>', '', m.group(1)).strip() for m in pattern.finditer(html)]


def strip_tags(fragment: str) -> str:
    return re.sub(r'<[^>]+>', '', fragment)


def validate(path: str) -> bool:
    html_path = Path(path)
    html = html_path.read_text(encoding="utf-8")
    errors = []
    warnings = []

    parser = ReadingHTMLParser()
    parser.feed(html)

    if len(html) < 10000:
        errors.append(f"File too small: {len(html)} bytes (expected > 10KB)")

    # 1. HTML structure and duplicate closing tags.
    structural_counts = {
        "html_open": count(r"<html\b", html),
        "html_close": count(r"</html>", html),
        "body_open": count(r"<body\b", html),
        "body_close": count(r"</body>", html),
        "script_open": count(r"<script\b", html),
        "script_close": count(r"</script>", html),
    }
    for name, value in structural_counts.items():
        if value < 1:
            errors.append(f"Missing structural tag: {name}")
    if structural_counts["html_open"] != 1 or structural_counts["html_close"] != 1:
        errors.append(f"Expected exactly one html open/close pair, got {structural_counts['html_open']}/{structural_counts['html_close']}")
    if structural_counts["body_open"] != 1 or structural_counts["body_close"] != 1:
        errors.append(f"Expected exactly one body open/close pair, got {structural_counts['body_open']}/{structural_counts['body_close']}")
    if structural_counts["script_open"] != structural_counts["script_close"]:
        errors.append(f"script tag mismatch: {structural_counts['script_open']} open, {structural_counts['script_close']} close")
    if parser.div_balance != 0:
        errors.append(f"div balance mismatch: parser balance {parser.div_balance}")
    if re.search(r"</script>\s*</body>\s*</html>\s*</script>", html, re.I):
        errors.append("Duplicate trailing </script></body></html> detected")
    tail = html[-300:]
    if count(r"</body>", tail) > 1 or count(r"</html>", tail) > 1:
        errors.append("Duplicate body/html closing tags near file tail")

    # 2. Required DOM/components.
    required_classes = [
        "tab-bar", "tab-btn", "action-bar", "header", "layout", "passage-panel",
        "passage-col", "questions-col", "q-block", "score-badge", "answer-reveal"
    ]
    for cls in required_classes:
        if not class_present(parser, cls):
            errors.append(f"Missing required DOM class: .{cls}")
    required_snippets = {
        "submit button": "submitAnswers()",
        "reset button": "resetAll()",
        "reveal button code": "reveal-btn-single",
        "score display": "scoreBadge",
        "switch passage": "switchPassage",
        "grade/check function": "gradePanel",
        "submit/check button logic": "submitAnswers",
        "reset function": "resetAll",
        "heading reveal-to-slot function": "revealHeadingSlot",
        "click heading alternative": "selectHeadingItem",
    }
    for name, snippet in required_snippets.items():
        if snippet not in html:
            errors.append(f"Missing {name}: {snippet}")

    # 3. Passage and question completeness.
    panels = attrs_for_class(parser, "passage-panel")
    tabs = attrs_for_class(parser, "tab-btn")
    if len(panels) not in (1, 3, 5):
        errors.append(f"Expected 1, 3, or 5 passage panels, found {len(panels)}")
    if len(tabs) != len(panels):
        errors.append(f"Tab/passage mismatch: {len(tabs)} tabs vs {len(panels)} panels")
    if not any(text_inside_blocks(html, "para")):
        errors.append("No non-empty passage paragraphs found")
    q_texts = text_inside_blocks(html, "q-text")
    if not q_texts or any(not t for t in q_texts):
        errors.append("Empty or missing question text found")
    reveal_texts = text_inside_blocks(html, "answer-reveal")
    if not reveal_texts or any(not t for t in reveal_texts):
        errors.append("Empty or missing reveal/explanation text found")

    # 4. Question type structure.
    for attrs in attrs_for_class(parser, "mcq-group"):
        if not attrs.get("data-ans"):
            errors.append("MCQ group missing data-ans")
    mcq_groups = re.findall(r'<div class="mcq-group"[^>]*>(.*?)</div>\s*<div class="answer-reveal"', html, re.S)
    for i, group in enumerate(mcq_groups, 1):
        if count(r'class="mcq-opt"', group) < 2:
            errors.append(f"MCQ group {i} has fewer than 2 options")
    for cls in ("tfng-group", "ynng-group"):
        for attrs in attrs_for_class(parser, cls):
            if not attrs.get("data-ans"):
                errors.append(f".{cls} missing data-ans")
    for attrs in attrs_for_class(parser, "match-select"):
        if not attrs.get("data-ans"):
            errors.append("match-select missing data-ans")
    for attrs in attrs_for_class(parser, "fill-input"):
        if not attrs.get("data-ans"):
            q = attrs.get("data-q", "?")
            errors.append(f"fill-input missing data-ans (question Q{q}; likely summary/fill block answer missing)")
    # Contextual summary diagnostics: locate malformed generated summary inputs by passage/block/question.
    panel_starts_for_summary = [m.start() for m in re.finditer(r'<div class="passage-panel\b', html)]
    for pi, start in enumerate(panel_starts_for_summary, 1):
        end = panel_starts_for_summary[pi] if pi < len(panel_starts_for_summary) else html.find('<script>', start)
        section = html[start:end if end > 0 else len(html)]
        for bi, m in enumerate(re.finditer(r'<div class="summary-paragraph"[\s\S]*?</div>', section), 1):
            block = m.group(0)
            q_nums = re.findall(r'class="fill-input"[^>]*data-q="([^"]*)"', block)
            bad_inputs = [x.group(0) for x in re.finditer(r'<input[^>]*class="[^"]*fill-input[^"]*"[^>]*>', block) if 'data-ans=' not in x.group(0)]
            if bad_inputs:
                errors.append(f"Passage {pi} summary block {bi} malformed: {len(bad_inputs)} fill-input(s) missing data-ans; question numbers: {q_nums or ['?']}")
            if len(q_nums) != len(set(q_nums)):
                errors.append(f"Passage {pi} summary block {bi} has duplicate summary question numbers: {q_nums}")

    heading_pools = attrs_for_class(parser, "heading-pool")
    heading_slots = attrs_for_class(parser, "heading-slot")
    if heading_pools:
        if not heading_slots:
            errors.append("Heading pool exists but no heading slots found")
        if not class_present(parser, "heading-item"):
            errors.append("Heading pool exists but no heading items found")
        for attrs in heading_slots:
            if not attrs.get("data-ans"):
                errors.append("Heading slot missing data-ans")
            if not attrs.get("data-para") or not attrs.get("data-q"):
                errors.append("Heading slot must bind to paragraph and question via data-para/data-q")
            if not attrs.get("data-answer-text"):
                errors.append("Heading slot missing full data-answer-text for reveal")
        for snippet in ("dragHeading", "dropHeading", "placeHeading", "allowDrop", "selectHeadingItem", "revealHeadingSlot"):
            if snippet not in html:
                errors.append(f"Heading interaction code missing: {snippet}")

        panel_starts = [m.start() for m in re.finditer(r'<div class="passage-panel\b', html)]
        panel_chunks = []
        for i, start in enumerate(panel_starts):
            end = panel_starts[i + 1] if i + 1 < len(panel_starts) else html.find('</div><!-- /layout -->', start)
            if end < 0:
                end = html.find('<script>', start)
            panel_chunks.append(html[start:end])
        for idx, section in enumerate(panel_chunks, 1):
            if '<div class="heading-pool"' not in section:
                continue
            qcol_idx = section.find('<div class="questions-col"')
            if qcol_idx < 0:
                errors.append(f"Heading passage section {idx} missing questions-col")
                continue
            passage_col = section[:qcol_idx]
            questions_col = section[qcol_idx:]
            pc_slots = count(r'class="heading-slot"', passage_col)
            qc_slots = count(r'class="heading-slot"', questions_col)
            rows = count(r'class="heading-drop-row"', passage_col)
            paras = count(r'class="para"', passage_col)
            if pc_slots == 0:
                errors.append(f"Heading passage section {idx}: heading drop boxes must be inside passage column")
            if qc_slots:
                errors.append(f"Heading passage section {idx}: heading drop boxes must not be in questions column")
            if pc_slots != paras:
                errors.append(f"Heading passage section {idx}: heading slot count {pc_slots} must match paragraph count {paras}")
            if rows != pc_slots:
                errors.append(f"Heading passage section {idx}: heading-drop-row count {rows} must match heading slot count {pc_slots}")
            if not re.search(r'class="heading-drop-row"[\s\S]*?class="heading-slot"[\s\S]*?<p class="para"', passage_col):
                errors.append(f"Heading passage section {idx}: heading slot must render immediately before passage paragraph")
            if count(r'class="heading-item"', questions_col) <= pc_slots:
                errors.append(f"Heading passage section {idx}: heading pool should include more headings than matched paragraphs")
            legacy_answer_items = re.findall(
                r'<div class="q-block"[^>]*>\s*<div class="q-text"[^>]*>\s*<span class="num">\d+\.?</span>\s*Paragraph\s+[A-Z]\s*</div>\s*</div>',
                questions_col,
                flags=re.I,
            )
            if legacy_answer_items:
                errors.append(
                    f"Heading passage section {idx}: questions column still contains legacy Paragraph A/B/C answer list ({len(legacy_answer_items)} item(s))"
                )
            if re.search(r'<select[^>]*class="[^"]*heading-select', questions_col, flags=re.I):
                errors.append(f"Heading passage section {idx}: questions column still contains legacy heading-select controls")

    # 5. Student-visible answer leakage and internal-template reveal checks.
    mcq_visible = [strip_tags(m.group(1)) for m in re.finditer(r'<div class="mcq-opt"[^>]*>(.*?)</div>', html, re.I | re.S)]
    for i, txt in enumerate(mcq_visible, 1):
        if re.search(r'[✓✔√]|\[(?:correct|answer)\]|\((?:correct|answer)\)|\bCorrect(?:\s+answer)?\b|\bAnswer:', txt, re.I):
            errors.append(f"MCQ visible option {i} leaks answer marker: {txt[:80]}")
    q_visible = text_inside_blocks(html, "q-text")
    for i, txt in enumerate(q_visible, 1):
        if re.search(r'\[(?:TRUE|FALSE|NOT GIVEN|YES|NO)\]', txt, re.I):
            errors.append(f"Question text {i} leaks inline answer marker: {txt[:80]}")
    reveal_texts_full = text_inside_blocks(html, "answer-reveal")
    internal_phrases = ["extracted from teacher answer key", "marked option", "source trace", "raw extraction", "normalizer fallback"]
    for i, txt in enumerate(reveal_texts_full, 1):
        low = txt.lower()
        hit = next((p for p in internal_phrases if p in low), None)
        if hit:
            warnings.append(f"Reveal {i} contains internal/template phrase {hit!r}")

    # 6. Answer leakage policy warning.
    if "data-ans=" in html or "answer-reveal" in html:
        warnings.append("current output is not a strict student version because answers are embedded in HTML source/data attributes.")

    if errors:
        print(f"VALIDATION FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        for e in errors:
            print(f"  ERROR: {e}")
        for w in warnings:
            print(f"  WARNING: {w}")
        return False

    print(f"VALIDATION PASSED ✅ ({len(warnings)} warning(s))")
    print(f"  Size: {len(html)} bytes")
    print(f"  Passages: {len(panels)}")
    print(f"  Script tags: {structural_counts['script_open']} open / {structural_counts['script_close']} close")
    for w in warnings:
        print(f"  WARNING: {w}")
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: validate_reading.py <path-to-html>')
        sys.exit(1)
    ok = validate(sys.argv[1])
    sys.exit(0 if ok else 1)
