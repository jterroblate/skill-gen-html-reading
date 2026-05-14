#!/usr/bin/env python3
"""Extract teacher-version IELTS Reading DOCX into raw auditable JSON.

This is Module A raw extraction. It preserves source traces and does not try to
pretend the source is clean.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document

ROMAN_RE = re.compile(r"^(i{1,3}|iv|v|vi{0,3}|ix|x)\.\s+", re.I)
PARA_LABEL_RE = re.compile(r"\[([A-Z])\]\s*(.*)", re.S)
END_RE = re.compile(r"^-\s*END OF PASSAGE\s+(\d+)\s*-", re.I)
BAND_RE = re.compile(r"^Band\s+([^|]+)(?:\|\s*(.*))?", re.I)
Q_LINE_RE = re.compile(r"^(\d+)\.\s+(.*)")
EMBED_ANSWER_RE = re.compile(r"\[([A-Z ]+|TRUE|FALSE|NOT GIVEN|YES|NO)\]", re.I)
SUMMARY_BLANK_RE = re.compile(r"\((\d+)\)\s*_+")


def run_info(run) -> dict[str, Any]:
    color = None
    if run.font.color and run.font.color.rgb:
        color = str(run.font.color.rgb)
    return {
        "text": run.text,
        "bold": bool(run.bold),
        "italic": bool(run.italic),
        "color": color,
    }


def paragraph_role(text: str) -> str:
    t = text.strip()
    if not t:
        return "blank"
    if END_RE.match(t):
        return "passage_end"
    if t == "Questions":
        return "questions_marker"
    if t == "Answer Key":
        return "answer_key_marker"
    if BAND_RE.match(t):
        return "passage_meta"
    if t.startswith("Linked Speaking Topics:"):
        return "linked_topics"
    if PARA_LABEL_RE.match(t):
        return "passage_paragraph"
    if ROMAN_RE.match(t):
        return "heading_item"
    if re.match(r"^[A-F]\.\s+[ivx]+$", t, re.I):
        return "heading_answer"
    if t.startswith("Answers:"):
        return "answer_line"
    if re.match(r"^\d+\s*-\s*\d+\.\s*", t) or re.match(r"^\d+\.\s*(?:[A-D]|TRUE|FALSE|NOT GIVEN|YES|NO)\b", t):
        return "answer_key_entry"
    if Q_LINE_RE.match(t):
        return "question_or_option"
    if re.match(r"^[A-D]\.\s+", t):
        return "option"
    if "______" in t:
        return "summary_text"
    if t.lower().startswith(("choose ", "do the statements", "complete the summary", "which paragraph", "write the correct")) or t.startswith("NB "):
        return "instruction"
    return "text"


def split_embedded_paragraphs(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"\[([A-Z])\]\s*", text))
    if not matches:
        return []
    out = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), text[start:end].strip()))
    return out


def parse_answer_tokens(text: str) -> dict[str, str]:
    """Parse simple answer key/answer line into q -> answer."""
    t = text.strip()
    if t.startswith("Answers:"):
        t = t.split(":", 1)[1].strip()
    out: dict[str, str] = {}
    # (11) output, (12) mental
    pairs = re.findall(r"\((\d+)(?:-\d+)?\)\s*([^,;]+)", t)
    if pairs:
        for q, ans in pairs:
            out[q] = ans.strip()
        return out
    # 11-13. output,mental,desks
    m = re.match(r"(\d+)\s*-\s*(\d+)\.\s*(.*)", t)
    if m:
        start, end, rest = int(m.group(1)), int(m.group(2)), m.group(3)
        vals = [x.strip() for x in rest.split(",")]
        for q, ans in zip(range(start, end + 1), vals):
            out[str(q)] = ans
        return out
    m = re.match(r"(\d+)\.\s*(.*)", t)
    if m:
        out[m.group(1)] = m.group(2).strip()
    return out


def extract_docx(docx_path: Path) -> dict[str, Any]:
    doc = Document(docx_path)
    paragraphs = []
    for idx, p in enumerate(doc.paragraphs, 1):
        text = p.text.strip()
        if not text:
            continue
        role = paragraph_role(text)
        paragraphs.append({
            "index": idx,
            "text": text,
            "style": p.style.name if p.style else "",
            "runs": [run_info(r) for r in p.runs if r.text],
            "role": role,
            "passage_id": None,
        })

    passages = []
    warnings = []
    i = 0
    p_id = 0
    while i < len(paragraphs):
        cur = paragraphs[i]
        nxt = paragraphs[i + 1] if i + 1 < len(paragraphs) else None
        if nxt and nxt["role"] == "passage_meta" and cur["role"] == "text":
            p_id += 1
            title = cur["text"]
            band_match = BAND_RE.match(nxt["text"])
            band = band_match.group(1).strip() if band_match else ""
            genre = (band_match.group(2) or "").strip() if band_match else ""
            linked = ""
            j = i + 2
            if j < len(paragraphs) and paragraphs[j]["role"] == "linked_topics":
                linked = paragraphs[j]["text"].split(":", 1)[1].strip()
                j += 1
            passage = {
                "passage_id": p_id,
                "title": title,
                "band": band,
                "genre": genre,
                "linked_topics": linked,
                "source_locations": [cur["index"], nxt["index"]],
                "paragraphs": [],
                "question_area": [],
                "answer_key": [],
                "heading_list": [],
                "heading_answers": {},
                "summary_answer_lines": [],
            }
            in_questions = False
            in_answer_key = False
            while j < len(paragraphs):
                item = paragraphs[j]
                item["passage_id"] = p_id
                if item["role"] == "passage_end":
                    passage["source_end"] = item["index"]
                    break
                if item["role"] == "questions_marker":
                    in_questions = True
                    j += 1
                    continue
                if item["role"] == "answer_key_marker":
                    in_answer_key = True
                    j += 1
                    continue
                if not in_questions:
                    parts = split_embedded_paragraphs(item["text"])
                    if len(parts) > 1:
                        warnings.append({
                            "type": "paragraph_split_issue",
                            "passage_id": p_id,
                            "location": item["index"],
                            "message": "Multiple paragraph labels found in one DOCX paragraph.",
                        })
                    if parts:
                        for label, txt in parts:
                            passage["paragraphs"].append({"label": label, "text": txt, "source_index": item["index"]})
                    else:
                        passage["paragraphs"].append({"label": "", "text": item["text"], "source_index": item["index"]})
                elif in_answer_key:
                    passage["answer_key"].append(item)
                else:
                    passage["question_area"].append(item)
                    if item["role"] == "heading_item":
                        key, text = item["text"].split(".", 1)
                        passage["heading_list"].append([key.strip(), text.strip()])
                    if item["role"] == "heading_answer":
                        lab, ans = item["text"].split(".", 1)
                        passage["heading_answers"][lab.strip()] = ans.strip()
                    if item["role"] == "answer_line":
                        passage["summary_answer_lines"].append(item)
                j += 1
            passages.append(passage)
            i = j + 1
        else:
            i += 1

    # Set paragraph passage ids in flat list best-effort.
    for p in passages:
        start = min(p.get("source_locations", [0]))
        end = p.get("source_end", 10**9)
        for item in paragraphs:
            if start <= item["index"] <= end:
                item["passage_id"] = p["passage_id"]

    return {
        "schema_version": "reading_docx_raw_v1",
        "input_file": str(docx_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paragraphs": paragraphs,
        "passages": passages,
        "extraction_warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    data = extract_docx(Path(args.docx))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote raw extraction: {out}")
    print(f"Passages: {len(data['passages'])}")
    print(f"Warnings: {len(data['extraction_warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
