#!/usr/bin/env python3
"""Normalize raw DOCX extraction into schema-compatible reading JSON."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "scripts" / "generate_reading.py"

Q_RE = re.compile(r"^(\d+)\.\s+(.*)")
OPT_RE = re.compile(r"^([A-D])[\.)]\s+(.*)")
EMBED_RE = re.compile(r"\[([A-Z ]+|TRUE|FALSE|NOT GIVEN|YES|NO|ANSWER)\]", re.I)
SUMMARY_BLANK_RE = re.compile(r"\((\d+)\)\s*_+")


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_reading", GEN)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def strip_answer(text: str) -> str:
    text = EMBED_RE.sub("", text).strip()
    text = re.sub(r"\s+(TRUE|FALSE|NOT GIVEN|YES|NO)\s*$", "", text, flags=re.I).strip()
    text = re.sub(r"\s+([A-F])\s*$", "", text).strip()
    text = re.sub(r"\s+([ivx]+)\s*$", "", text, flags=re.I).strip()
    return text


def trailing_answer(text: str) -> str | None:
    t = text.strip()
    m = EMBED_RE.search(t)
    if m:
        return m.group(1).upper().strip()
    m = re.search(r"\s+(TRUE|FALSE|NOT GIVEN|YES|NO)\s*$", t, re.I)
    if m:
        return m.group(1).upper()
    m = re.search(r"\s+([A-F])\s*$", t)
    if m:
        return m.group(1)
    m = re.search(r"\s+([ivx]+)\s*$", t, re.I)
    if m:
        return m.group(1).lower()
    return None


def is_marked_option(item: dict[str, Any]) -> bool:
    for run in item.get("runs", []):
        color = (run.get("color") or "").upper()
        if run.get("bold") and color and color not in {"000000", "777777"}:
            return True
    return False


def parse_key(answer_key: list[dict[str, Any]]) -> dict[int, str]:
    out: dict[int, str] = {}
    for item in answer_key:
        t = item["text"].strip()
        if t.startswith("Answers:"):
            t = t.split(":", 1)[1].strip()
        for q, ans in re.findall(r"\((\d+)(?:-\d+)?\)\s*([^,;]+)", t):
            out[int(q)] = ans.strip()
        m = re.match(r"(\d+)\s*-\s*(\d+)\.\s*(.*)", t)
        if m:
            vals = [x.strip() for x in m.group(3).split(",")]
            for q, ans in zip(range(int(m.group(1)), int(m.group(2)) + 1), vals):
                out[q] = ans
        m = re.match(r"(\d+)\.\s*(.*)", t)
        if m:
            out[int(m.group(1))] = m.group(2).strip()
    return out


def parse_questions(p: dict[str, Any], audit: dict[str, Any], confirmations: dict[str, Any]) -> tuple[str, list[Any], list[str]]:
    qarea = p.get("question_area", [])
    pid = p["passage_id"]
    key = parse_key(p.get("answer_key", []))
    warnings = []
    blocks = []
    i = 0
    mode = "regular"
    if p.get("heading_list"):
        mode = "heading"
    while i < len(qarea):
        text = qarea[i]["text"].strip()
        # Skip instructions/headings/heading answer lines; heading matching is represented at passage level.
        if qarea[i]["role"] in {"instruction", "heading_item", "answer_line"}:
            i += 1; continue
        if mode == "heading":
            hm = re.match(r"^\d+\.\s*Paragraph\s+([A-Z])\s+([ivx]+)\b", text, re.I)
            if hm:
                label, ans = hm.group(1), hm.group(2).lower()
                p.setdefault("heading_answers", {})[label] = ans
                qn = int(Q_RE.match(text).group(1)) if Q_RE.match(text) else len(p.get("heading_answers", {}))
                blocks.append({"q": qn, "type": "heading_info", "label": label, "reveal": f"{ans} — extracted from teacher heading answer line."})
                i += 1; continue
        if qarea[i]["role"] == "heading_answer":
            i += 1; continue
        if "______" in text:
            nums = [int(x) for x in SUMMARY_BLANK_RE.findall(text)]
            if nums:
                pairs = []
                reveals = []
                cursor = 0
                for n in nums:
                    marker = f"({n})"
                    pos = text.find(marker, cursor)
                    before = text[cursor:pos]
                    # Remove marker + underscores
                    after_start = pos + len(marker)
                    while after_start < len(text) and text[after_start] in " _":
                        after_start += 1
                    # next marker or end
                    next_positions = [text.find(f"({m})", after_start) for m in nums if m > n]
                    next_positions = [x for x in next_positions if x >= 0]
                    next_pos = min(next_positions) if next_positions else len(text)
                    ans = resolve_answer(pid, n, key.get(n, ""), confirmations, audit, warnings)
                    pairs.append([n, before, ans, text[after_start:next_pos]])
                    reveals.append(f"{ans} — extracted from teacher answer key / confirmed source.")
                    cursor = next_pos
                blocks.append({"q": nums[0], "type": "summary", "pairs": pairs, "reveals": reveals})
            i += 1; continue
        m = Q_RE.match(text)
        if not m:
            i += 1; continue
        q = int(m.group(1)); stem = strip_answer(m.group(2))
        embedded = trailing_answer(text)
        # MCQ if next lines are A-D options.
        opts = []
        j = i + 1
        while j < len(qarea) and OPT_RE.match(qarea[j]["text"].strip()):
            mo = OPT_RE.match(qarea[j]["text"].strip())
            assert mo
            opt_text = strip_answer(qarea[j]["text"].strip())
            opts.append(opt_text)
            if "[ANSWER]" in qarea[j]["text"].upper() or is_marked_option(qarea[j]):
                embedded = mo.group(1)
            j += 1
        if opts:
            ans = resolve_answer(pid, q, embedded or key.get(q, ""), confirmations, audit, warnings)
            blocks.append({"q": q, "type": "mcq", "stem": stem, "options": opts, "answer": ans, "reveal": f"{ans} — extracted from teacher answer key / marked option."})
            i = j; continue
        if embedded in {"TRUE", "FALSE", "NOT GIVEN"} or (str(key.get(q, "")).upper() in {"TRUE", "FALSE", "NOT GIVEN"}):
            ans = resolve_answer(pid, q, embedded or key.get(q, ""), confirmations, audit, warnings).upper()
            blocks.append({"q": q, "type": "tfng", "statement": stem, "answer": ans, "reveal": f"{ans} — extracted from teacher answer key / embedded answer."})
        elif embedded in {"YES", "NO"} or (str(key.get(q, "")).upper() in {"YES", "NO"}):
            ans = resolve_answer(pid, q, embedded or key.get(q, ""), confirmations, audit, warnings).upper()
            blocks.append({"q": q, "type": "ynng", "statement": stem, "answer": ans, "reveal": f"{ans} — extracted from teacher answer key / embedded answer."})
        elif embedded in {"A", "B", "C", "D", "E", "F"} or re.match(r"^[A-F]$", str(key.get(q, ""))):
            # Paragraph matching, not MCQ.
            labels = [x.get("label") for x in p.get("paragraphs", []) if x.get("label")]
            ans = resolve_answer(pid, q, embedded or key.get(q, ""), confirmations, audit, warnings)
            blocks.append({"q": q, "type": "match", "text": stem, "options": labels, "answer": ans, "reveal": f"{ans} — extracted from teacher answer key."})
        i += 1
    return mode, blocks, warnings


def resolve_answer(pid: int, q: int, default: str, confirmations: dict[str, Any], audit: dict[str, Any], warnings: list[str]) -> str:
    key = f"P{pid}_Q{q}"
    if key in confirmations:
        ans = confirmations[key].get("answer", "")
        warnings.append(f"{key}: used human confirmed answer {ans!r}.")
        return ans
    return str(default).strip()


def normalize(raw: dict[str, Any], audit: dict[str, Any], confirmations: dict[str, Any], allow_partial: bool) -> dict[str, Any]:
    blocking = [i for i in audit.get("issues", []) if i.get("severity") == "blocking"]
    if blocking and not allow_partial:
        raise SystemExit(f"Blocking audit issues found ({len(blocking)}). Use confirmations or --allow-partial.")
    passages = []
    warnings = list(raw.get("extraction_warnings", []))
    for p in raw.get("passages", []):
        mode, blocks, local_warnings = parse_questions(p, audit, confirmations)
        warnings.extend(local_warnings)
        out = {
            "num": p["passage_id"],
            "title": p["title"],
            "band": p.get("band", ""),
            "genre": p.get("genre", ""),
            "meta": f"Band {p.get('band','')} · {p.get('genre','')} · Linked: {p.get('linked_topics','')}",
            "paras": [{"label": x.get("label", ""), "text": x.get("text", "")} for x in p.get("paragraphs", []) if x.get("label") and x.get("text")],
            "questions": {"type": mode, "blocks": blocks},
        }
        if mode == "heading":
            out["questions"]["headings"] = p.get("heading_list", [])
            out["questions"]["answers"] = p.get("heading_answers", {})
        passages.append(out)
    data = {
        "title": "IELTS Reading Practice · extracted from DOCX",
        "header_title": "IELTS Academic Reading · DOCX extracted candidate",
        "passages": passages,
        "extraction_warnings": warnings,
        "source_files": {"docx": raw.get("input_file")},
        "source_audit_summary": audit.get("summary", {}),
        "source_audit_verdict": audit.get("overall_verdict"),
    }
    gen = load_generator()
    gen.validate_data(data)
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--audit", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--confirmed-answers")
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()
    raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    confirmations = {}
    if args.confirmed_answers:
        confirmations = json.loads(Path(args.confirmed_answers).read_text(encoding="utf-8"))
    data = normalize(raw, audit, confirmations, args.allow_partial)
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote clean candidate JSON: {out}")
    print(f"Passages: {len(data['passages'])}")
    print(f"Audit verdict: {data.get('source_audit_verdict')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
