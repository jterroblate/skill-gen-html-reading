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


LEAK_MARK_RE = re.compile(r"\s*(?:[✓✔√]|\[(?:correct|answer)\]|\((?:correct|answer)\))\s*", re.I)
INTERNAL_FALLBACK_EN = "The teacher version marks this as the correct answer, but no detailed explanation was provided in the source document."


def clean_visible(text: str) -> str:
    text = EMBED_RE.sub("", text)
    text = LEAK_MARK_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_answer(text: str) -> str:
    text = clean_visible(text)
    text = re.sub(r"\s+(TRUE|FALSE|NOT GIVEN|YES|NO)\s*$", "", text, flags=re.I).strip()
    text = re.sub(r"\s+([A-F])\s*$", "", text).strip()
    text = re.sub(r"\s+([ivx]+)\s*$", "", text, flags=re.I).strip()
    return text


def trailing_answer(text: str) -> str | None:
    t = text.strip()
    m = EMBED_RE.search(t)
    if m:
        return m.group(1).upper().strip()
    if re.search(r"[✓✔√]|\[(?:correct|answer)\]|\((?:correct|answer)\)|\bCorrect\b", t, re.I):
        return "ANSWER"
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
    text = item.get("text", "")
    if re.search(r"[✓✔√]|\[(?:correct|answer)\]|\((?:correct|answer)\)|\bCorrect\b", text, re.I):
        return True
    for run in item.get("runs", []):
        color = (run.get("color") or "").upper()
        if run.get("bold") and color and color not in {"000000", "777777"}:
            return True
    return False


def item_is_explanation(item: dict[str, Any]) -> bool:
    t = item.get("text", "").strip()
    if not t:
        return False
    if item.get("role") == "answer_key_entry":
        return True
    if re.match(r"^(Paragraph|Para)\s+[A-F]:", t, re.I):
        return True
    runs = item.get("runs", [])
    return bool(runs) and all((r.get("italic") or (r.get("color") or "").upper() == "777777") for r in runs)


def neutral_reveal(ans: str) -> str:
    return f"答案：{ans}。教师版标记该项为正确答案，但源文件未提供详细解析。"


def reveal_from_explanation(ans: str, explanation: str | None) -> str:
    exp = clean_visible(explanation or "")
    if exp:
        # Remove duplicated leading answer token but keep paragraph evidence.
        exp = re.sub(rf"^\s*{re.escape(str(ans))}\s*[-—:]?\s*", "", exp, flags=re.I).strip()
        return f"答案：{ans}。{exp}"
    return neutral_reveal(ans)


def parse_key_entry(text: str) -> tuple[int, str, str] | None:
    m = re.match(r"^(\d+)\.\s*(.+)$", text.strip(), re.S)
    if not m:
        return None
    q = int(m.group(1)); rest = m.group(2).strip()
    hm = re.match(r"Paragraph\s+([A-Z])\s+([ivx]+)\b(.*)$", rest, re.I)
    if hm:
        return q, hm.group(2).lower(), rest
    m2 = re.match(r"(TRUE|FALSE|NOT GIVEN|YES|NO|[A-F]|[ivx]+)\b[\s:—-]*(.*)$", rest, re.I)
    if m2:
        ans = m2.group(1).upper() if m2.group(1).upper() in {"TRUE","FALSE","NOT GIVEN","YES","NO"} or re.match(r"^[A-F]$", m2.group(1)) else m2.group(1).lower()
        return q, ans, rest
    # Fill/summary teacher explanation lines: answer appears before dash / Para / Paragraph.
    m3 = re.match(r"([^—–]+?)\s*(?:[—–]|\s-\s|(?:Para(?:graph)?\s+[A-F]:))(.*)$", rest, re.I)
    if m3:
        ans = clean_visible(m3.group(1)).strip()
        if ans:
            return q, ans, rest
    # Bare fill answer in an answer key, e.g. "3. clear".
    bare = clean_visible(rest)
    if bare and len(bare.split()) <= 4:
        return q, bare, rest
    return None


def split_numbered_segments(text: str) -> list[str]:
    matches = list(re.finditer(r"(?<!\d)(\d+)\.\s+", text))
    if len(matches) <= 1:
        return [text]
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append(text[m.start():end].strip())
    return out


def parse_key(answer_key: list[dict[str, Any]]) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    for item in answer_key:
        t = item["text"].strip()
        if t.startswith("Answers:"):
            t = t.split(":", 1)[1].strip()
        for q, ans in re.findall(r"\((\d+)(?:-\d+)?\)\s*([^,;]+)", t):
            out[int(q)] = {"answer": clean_visible(ans), "explanation": t}
        m = re.match(r"(\d+)\s*-\s*(\d+)\.\s*(.*)", t)
        if m:
            vals = [clean_visible(x) for x in m.group(3).split(",")]
            for q, ans in zip(range(int(m.group(1)), int(m.group(2)) + 1), vals):
                out[q] = {"answer": ans, "explanation": t}
            continue
        for seg in split_numbered_segments(t):
            parsed = parse_key_entry(seg)
            if parsed:
                q, ans, exp = parsed
                out[q] = {"answer": clean_visible(ans), "explanation": exp}
    return out


def answer_for(q: int, embedded: str | None, key: dict[int, dict[str, str]], default: str = "") -> str:
    if embedded and embedded != "ANSWER":
        return clean_visible(embedded).upper() if embedded.upper() in {"TRUE","FALSE","NOT GIVEN","YES","NO"} else clean_visible(embedded)
    if q in key:
        return key[q]["answer"]
    return clean_visible(default)


def key_reveal(q: int, ans: str, key: dict[int, dict[str, str]], explanation: str | None = None) -> str:
    if explanation:
        return reveal_from_explanation(ans, explanation)
    if q in key:
        return reveal_from_explanation(ans, key[q].get("explanation"))
    return neutral_reveal(ans)


def collect_following_explanation(qarea: list[dict[str, Any]], start: int) -> tuple[str | None, int]:
    if start < len(qarea) and item_is_explanation(qarea[start]):
        t = qarea[start].get("text", "")
        # Do not consume a real question misclassified as answer_key_entry.
        if Q_RE.match(t.strip()) and trailing_answer(t):
            return None, start
        return t, start + 1
    return None, start


def parse_questions(p: dict[str, Any], audit: dict[str, Any], confirmations: dict[str, Any]) -> tuple[str, list[Any], list[str]]:
    qarea = p.get("question_area", [])
    key = parse_key(p.get("answer_key", []) + [x for x in qarea if x.get("role") == "answer_key_entry"])
    warnings = []
    blocks = []
    i = 0
    mode = "heading" if p.get("heading_list") else "regular"
    seen = set()
    while i < len(qarea):
        item = qarea[i]
        text = item["text"].strip()
        role = item.get("role")
        if role in {"instruction", "heading_item", "answer_line"} or text.lower().startswith(("list of headings", "distractors:", "explanations:", "speaking-transfer")):
            i += 1; continue
        if role == "answer_key_entry" or item_is_explanation(item):
            # Some DOCX lines are misclassified as answer_key_entry even though they are
            # real TFNG/YNNG questions with an inline [FALSE] marker. Process those below.
            inline = trailing_answer(text)
            if not (Q_RE.match(text) and inline):
                # Also recover compact fill/summary entries like "8. answer — Para... 9. answer — Para...".
                recovered = []
                for seg in split_numbered_segments(text):
                    parsed = parse_key_entry(seg)
                    if parsed:
                        q, ans, exp = parsed
                        if q not in seen and ans and not re.match(r"^(TRUE|FALSE|NOT GIVEN|YES|NO|[A-F]|[ivx]+)$", ans, re.I):
                            recovered.append({"q": q, "type": "fill", "before": "", "after": "", "answer": ans, "reveal": reveal_from_explanation(ans, exp)})
                blocks.extend(recovered); seen.update(b["q"] for b in recovered)
                i += 1; continue
        if mode == "heading":
            hm = re.match(r"^(\d+)\.\s*Paragraph\s+([A-Z])\s+([ivx]+)\b(.*)$", text, re.I)
            if hm:
                qn, label, ans = int(hm.group(1)), hm.group(2), hm.group(3).lower()
                p.setdefault("heading_answers", {})[label] = ans
                blocks.append({"q": qn, "type": "heading_info", "label": label, "reveal": reveal_from_explanation(ans, text)})
                seen.add(qn); i += 1; continue
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
                    after_start = pos + len(marker)
                    while after_start < len(text) and text[after_start] in " _":
                        after_start += 1
                    next_positions = [text.find(f"({m})", after_start) for m in nums if m > n]
                    next_positions = [x for x in next_positions if x >= 0]
                    next_pos = min(next_positions) if next_positions else len(text)
                    ans = answer_for(n, None, key)
                    pairs.append([n, clean_visible(before), ans, clean_visible(text[after_start:next_pos])])
                    reveals.append(key_reveal(n, ans, key))
                    seen.add(n); cursor = next_pos
                blocks.append({"q": nums[0], "type": "summary", "pairs": pairs, "reveals": reveals})
            i += 1; continue
        m = Q_RE.match(text)
        if not m:
            i += 1; continue
        q = int(m.group(1)); rest = m.group(2).strip()
        if q in seen:
            i += 1; continue
        has_following_options = i + 1 < len(qarea) and OPT_RE.match(qarea[i + 1]["text"].strip())
        direct_entry = parse_key_entry(text)
        if direct_entry and not has_following_options:
            _q, _ans, _exp = direct_entry
            if _q == q and _ans and not re.match(r"^(TRUE|FALSE|NOT GIVEN|YES|NO|[A-F]|[ivx]+)$", _ans, re.I):
                blocks.append({"q": q, "type": "fill", "before": "", "after": "", "answer": _ans, "reveal": reveal_from_explanation(_ans, _exp)})
                seen.add(q); i += 1; continue
        stem = strip_answer(rest)
        embedded = trailing_answer(text)
        opts = []
        j = i + 1
        while j < len(qarea) and OPT_RE.match(qarea[j]["text"].strip()):
            mo = OPT_RE.match(qarea[j]["text"].strip()); assert mo
            opt_body = clean_visible(mo.group(2))
            opts.append(f"{mo.group(1)}) {opt_body}")
            if is_marked_option(qarea[j]):
                embedded = mo.group(1)
            j += 1
        if opts:
            explanation, next_i = collect_following_explanation(qarea, j)
            ans = answer_for(q, embedded, key)
            if ans:
                blocks.append({"q": q, "type": "mcq", "stem": stem, "options": opts, "answer": ans, "reveal": key_reveal(q, ans, key, explanation)})
                seen.add(q)
            i = next_i; continue
        ans = answer_for(q, embedded, key)
        explanation, next_i = collect_following_explanation(qarea, i + 1)
        upper_ans = ans.upper() if ans else ""
        if upper_ans in {"TRUE", "FALSE", "NOT GIVEN"}:
            blocks.append({"q": q, "type": "tfng", "statement": stem, "answer": upper_ans, "reveal": key_reveal(q, upper_ans, key, explanation)})
            seen.add(q); i = next_i; continue
        if upper_ans in {"YES", "NO"}:
            blocks.append({"q": q, "type": "ynng", "statement": stem, "answer": upper_ans, "reveal": key_reveal(q, upper_ans, key, explanation)})
            seen.add(q); i = next_i; continue
        if re.match(r"^[A-F]$", ans or ""):
            labels = [x.get("label") for x in p.get("paragraphs", []) if x.get("label")]
            blocks.append({"q": q, "type": "match", "text": stem, "options": labels, "answer": ans, "reveal": key_reveal(q, ans, key, explanation)})
            seen.add(q); i = next_i; continue
        if ans:
            blocks.append({"q": q, "type": "fill", "before": stem if stem and stem != ans else "", "after": "", "answer": ans, "reveal": key_reveal(q, ans, key, explanation)})
            seen.add(q); i = next_i; continue
        i += 1
    if mode == "heading":
        existing_heading_labels = {b.get("label") for b in blocks if b.get("type") == "heading_info"}
        next_q = 1
        existing_qs = {int(b.get("q", 0)) for b in blocks if str(b.get("q", "")).isdigit()}
        for label, ans in sorted(p.get("heading_answers", {}).items()):
            if label in existing_heading_labels:
                continue
            while next_q in existing_qs:
                next_q += 1
            blocks.append({"q": next_q, "type": "heading_info", "label": label, "reveal": neutral_reveal(ans)})
            existing_qs.add(next_q); next_q += 1
    return mode, sorted(blocks, key=lambda b: int(b.get("q", 0))), warnings


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
