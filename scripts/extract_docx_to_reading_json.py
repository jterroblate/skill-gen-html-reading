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
END_RE = re.compile(r"^-+\s*END OF PASSAGE(?:\s+\d+)?\s*-+", re.I)
PASSAGE_TITLE_RE = re.compile(
    r"^(?:(?:Reading\s+)?Passage\s*(?P<num1>\d+)|P(?P<num2>\d+))(?:(?:\s*[—–\-·:]\s*|\s+)(?P<title>.+))?$",
    re.I,
)
BAND_RE = re.compile(r"^(?:Level:\s*)?(?:Band:?\s*)(?P<band>[^|·]+?)(?:\s*[|·]\s*(?P<genre>.*))?$", re.I)
GENRE_RE = re.compile(r"^Genre:\s*(?P<genre>.+)$", re.I)
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


def parse_passage_title(text: str) -> dict[str, str] | None:
    t = text.strip().strip('“”')
    m = PASSAGE_TITLE_RE.match(t)
    if not m:
        return None
    raw_title = (m.group("title") or "").strip().strip('"“”')
    num = m.group("num1") or m.group("num2") or ""
    return {"num": num, "title": raw_title}


def parse_meta(text: str) -> dict[str, str] | None:
    t = text.strip()
    m = BAND_RE.match(t)
    if m:
        return {"band": m.group("band").strip(), "genre": (m.group("genre") or "").strip()}
    m = GENRE_RE.match(t)
    if m:
        return {"band": "", "genre": m.group("genre").strip()}
    return None


def paragraph_role(text: str) -> str:
    t = text.strip()
    if not t:
        return "blank"
    if END_RE.match(t):
        return "passage_end"
    if t == "Questions" or re.match(r"^Questions\s+\d+", t, re.I):
        return "questions_marker"
    if t == "Answer Key" or t.lower().startswith("answer key"):
        return "answer_key_marker"
    if parse_meta(t):
        return "passage_meta"
    if parse_passage_title(t):
        return "passage_title"
    if t.startswith("Linked Speaking Topics:"):
        return "linked_topics"
    if PARA_LABEL_RE.match(t):
        return "passage_paragraph"
    if ROMAN_RE.match(t):
        return "heading_item"
    if re.match(r"^[A-F]\.\s+[ivx]+", t, re.I):
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



def detect_passage_start(paragraphs: list[dict[str, Any]], i: int) -> dict[str, Any] | None:
    """Return normalized passage start info at paragraph index i, if present.

    Supports explicit markers (Reading Passage 1 — Title, P1 · Title), marker-only
    followed by title+meta, and legacy bare title followed by meta.
    """
    cur = paragraphs[i] if i < len(paragraphs) else None
    if not cur:
        return None
    nxt = paragraphs[i + 1] if i + 1 < len(paragraphs) else None
    nxt2 = paragraphs[i + 2] if i + 2 < len(paragraphs) else None

    explicit = parse_passage_title(cur["text"])
    if explicit:
        # Reading Passage 1 — Title / P1 · Title, followed by meta.
        if explicit.get("title") and nxt and nxt["role"] == "passage_meta":
            return {"title": explicit["title"], "marker_index": cur["index"], "title_index": cur["index"], "meta_index": nxt["index"], "meta_text": nxt["text"], "next_i": i + 2, "declared_num": explicit.get("num")}
        # Reading Passage 1, then separate title, then meta.
        if not explicit.get("title") and nxt and nxt["role"] == "text" and nxt2 and nxt2["role"] == "passage_meta":
            return {"title": nxt["text"], "marker_index": cur["index"], "title_index": nxt["index"], "meta_index": nxt2["index"], "meta_text": nxt2["text"], "next_i": i + 3, "declared_num": explicit.get("num")}
        # Marker-only directly followed by meta: use marker as title, still start.
        if nxt and nxt["role"] == "passage_meta":
            return {"title": explicit.get("title") or cur["text"], "marker_index": cur["index"], "title_index": cur["index"], "meta_index": nxt["index"], "meta_text": nxt["text"], "next_i": i + 2, "declared_num": explicit.get("num")}

    # Legacy format: bare title line followed by Band/Level/Genre meta.
    if cur["role"] == "text" and nxt and nxt["role"] == "passage_meta":
        return {"title": cur["text"], "marker_index": None, "title_index": cur["index"], "meta_index": nxt["index"], "meta_text": nxt["text"], "next_i": i + 2, "declared_num": None}
    return None

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
        start = detect_passage_start(paragraphs, i)
        if not start:
            i += 1
            continue

        p_id += 1
        meta = parse_meta(start["meta_text"]) or {"band": "", "genre": ""}
        passage = {
            "passage_id": p_id,
            "declared_passage_num": start.get("declared_num"),
            "title": start["title"],
            "band": meta.get("band", ""),
            "genre": meta.get("genre", ""),
            "linked_topics": "",
            "source_locations": [x for x in [start.get("marker_index"), start.get("title_index"), start.get("meta_index")] if x],
            "paragraphs": [],
            "question_area": [],
            "answer_key": [],
            "heading_list": [],
            "heading_answers": {},
            "summary_answer_lines": [],
        }
        j = start["next_i"]
        if j < len(paragraphs) and paragraphs[j]["role"] == "linked_topics":
            passage["linked_topics"] = paragraphs[j]["text"].split(":", 1)[1].strip()
            j += 1

        in_questions = False
        in_answer_key = False
        while j < len(paragraphs):
            # Boundary fallback: a new title+meta starts a new passage even without END marker.
            new_start = detect_passage_start(paragraphs, j)
            if new_start:
                passage["source_end"] = paragraphs[j - 1]["index"] if j > 0 else start.get("meta_index")
                warnings.append({
                    "type": "implicit_passage_boundary",
                    "passage_id": p_id,
                    "location": paragraphs[j]["index"],
                    "message": "Started a new passage from title+meta without an explicit END OF PASSAGE separator.",
                    "suggested_resolution": "Source lacks explicit passage separator; extractor used next passage title/meta as boundary.",
                })
                break

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
                    passage["heading_answers"][lab.strip()] = ans.strip().split()[0].strip(".;,")
                if item["role"] == "answer_line":
                    passage["summary_answer_lines"].append(item)
            j += 1

        if "source_end" not in passage:
            passage["source_end"] = paragraphs[j - 1]["index"] if j > start["next_i"] else start.get("meta_index")
        passages.append(passage)
        # If boundary fallback fired, j points at the next passage start. Otherwise skip END marker.
        i = j if j < len(paragraphs) and detect_passage_start(paragraphs, j) else j + 1

    question_markers = [p for p in paragraphs if p["role"] == "questions_marker"]
    if question_markers and not passages:
        warnings.append({
            "type": "passage_detection_failure",
            "passage_id": 0,
            "location": question_markers[0]["index"],
            "message": "Questions were detected but no passage start was found.",
            "suggested_resolution": "Check unsupported title pattern, unsupported meta line pattern, missing explicit separator, or inconsistent paragraph styles.",
        })
    if len(passages) <= 1 and question_markers:
        warnings.append({
            "type": "passage_detection_failure",
            "passage_id": passages[0]["passage_id"] if passages else 0,
            "location": question_markers[0]["index"],
            "message": f"Only {len(passages)} passage(s) extracted although the source contains question markers; this may be a full IELTS set with missed passage boundaries.",
            "suggested_resolution": "Possible causes: title pattern unsupported; meta line pattern unsupported; missing explicit passage separator; paragraph style inconsistent.",
        })

    # Set paragraph passage ids in flat list best-effort.
    for p in passages:
        start_idx = min(p.get("source_locations", [0]))
        end_idx = p.get("source_end", 10**9)
        for item in paragraphs:
            if start_idx <= item["index"] <= end_idx:
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
