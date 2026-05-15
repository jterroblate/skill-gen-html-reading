#!/usr/bin/env python3
"""Audit raw DOCX extraction before normalization."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUMMARY_BLANK_RE = re.compile(r"\((\d+)\)\s*_+")
Q_LINE_RE = re.compile(r"^(\d+)\.\s+(.*)")
EMBED_RE = re.compile(r"\[([A-Z ]+|TRUE|FALSE|NOT GIVEN|YES|NO)\]", re.I)


def parse_answer_tokens(text: str) -> dict[str, str]:
    t = text.strip()
    if t.startswith("Answers:"):
        t = t.split(":", 1)[1].strip()
    out: dict[str, str] = {}
    for q, ans in re.findall(r"\((\d+)(?:-\d+)?\)\s*([^,;]+)", t):
        out[q] = ans.strip()
    if out:
        return out
    m = re.match(r"(\d+)\s*-\s*(\d+)\.\s*(.*)", t)
    if m:
        vals = [x.strip() for x in m.group(3).split(",")]
        for q, ans in zip(range(int(m.group(1)), int(m.group(2)) + 1), vals):
            out[str(q)] = ans
        return out
    m = re.match(r"(\d+)\.\s*(.*)", t)
    if m:
        out[m.group(1)] = m.group(2).strip()
    return out


def embedded_questions(question_area: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    qs: dict[str, dict[str, Any]] = {}
    for item in question_area:
        m = Q_LINE_RE.match(item["text"])
        if not m:
            continue
        q, rest = m.group(1), rest_clean(m.group(2))
        em = EMBED_RE.search(item["text"])
        qs[q] = {
            "text": rest,
            "embedded_answer": em.group(1).strip().upper() if em else None,
            "source_index": item["index"],
            "role": item["role"],
        }
    return qs


def rest_clean(text: str) -> str:
    return EMBED_RE.sub("", text).strip()


def answer_key_map(answer_key: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in answer_key:
        parsed = parse_answer_tokens(item["text"])
        for q, ans in parsed.items():
            out[q] = {"answer": ans.strip(), "source_index": item["index"], "raw": item["text"]}
    return out


def issue(seq: int, severity: str, typ: str, passage_id: int, q: str | None, locs: list[int], msg: str,
          conflicting_values: dict[str, Any] | None = None, suggested: str | None = None,
          confidence: float = 0.5, needs: bool = True) -> dict[str, Any]:
    return {
        "issue_id": f"ISSUE-{seq:04d}",
        "severity": severity,
        "issue_type": typ,
        "passage_id": passage_id,
        "question_number": q,
        "source_locations": locs,
        "conflicting_values": conflicting_values or {},
        "evidence": msg,
        "suggested_resolution": suggested,
        "confidence": confidence,
        "needs_human_confirmation": needs,
    }


def audit(raw: dict[str, Any]) -> dict[str, Any]:
    issues = []
    suggestions: dict[str, dict[str, Any]] = {}
    seq = 1
    type_counts = Counter()
    question_count = 0
    answer_count = 0
    paragraph_count = sum(len(p.get("paragraphs", [])) for p in raw.get("passages", []))
    passage_count = len(raw.get("passages", []))
    all_paragraphs = raw.get("paragraphs", [])
    question_marker_count = sum(1 for x in all_paragraphs if x.get("role") == "questions_marker")
    question_like_count = sum(1 for x in all_paragraphs if Q_LINE_RE.match(x.get("text", "")))
    looks_like_full_unit = question_marker_count >= 3 or question_like_count >= 20 or passage_count in (0, 1) and question_marker_count > 0

    if passage_count == 0:
        issues.append(issue(seq, "blocking", "passage_detection_failure", 0, None, [],
                            "No passages were extracted. Possible causes: title pattern unsupported; meta line pattern unsupported; missing explicit passage separator; paragraph style inconsistent.",
                            {"question_markers": question_marker_count, "question_like_lines": question_like_count},
                            suggested="Inspect DOCX title/meta formatting and update extraction patterns before normalization.", confidence=0.95, needs=True))
        seq += 1
    elif passage_count < 3 and looks_like_full_unit:
        issues.append(issue(seq, "major", "passage_detection_failure", 0, None, [],
                            f"Only {passage_count} passage(s) extracted from a source that looks like a complete IELTS reading set. Possible causes: title pattern unsupported; meta line pattern unsupported; missing explicit passage separator; paragraph style inconsistent.",
                            {"question_markers": question_marker_count, "question_like_lines": question_like_count},
                            suggested="Do not treat this as PASS; verify passage boundaries and rerun extraction.", confidence=0.9, needs=True))
        seq += 1

    for w in raw.get("extraction_warnings", []):
        issues.append(issue(seq, "minor", w.get("type", "extraction_warning"), w.get("passage_id", 0) or 0, None,
                            [w.get("location")] if w.get("location") else [],
                            w.get("message", "Raw extractor warning."),
                            suggested=w.get("suggested_resolution"), confidence=0.7, needs=False))
        seq += 1

    for p in raw.get("passages", []):
        pid = p["passage_id"]
        q_area = p.get("question_area", [])
        q_map = embedded_questions(q_area)
        key_map = answer_key_map(p.get("answer_key", []))
        question_count += len(q_map)
        answer_count += len(key_map) + len(p.get("heading_answers", {}))

        # Question area answer vs answer key conflicts.
        for q, qinfo in q_map.items():
            embedded = qinfo.get("embedded_answer")
            keyed = key_map.get(q, {}).get("answer")
            if embedded and keyed:
                norm_key = keyed.upper().strip()
                if norm_key != embedded.upper().strip():
                    issues.append(issue(seq, "major", "answer_key_conflict", pid, q,
                                        [qinfo["source_index"], key_map[q]["source_index"]],
                                        "Embedded answer in question area conflicts with Answer Key.",
                                        {"embedded_answer": embedded, "answer_key": keyed},
                                        suggested=embedded, confidence=0.7, needs=True))
                    seq += 1
            if embedded:
                suggestions[f"P{pid}_Q{q}"] = {"answer": embedded, "source": "embedded_question_answer", "confidence": 0.75}
            elif keyed:
                suggestions[f"P{pid}_Q{q}"] = {"answer": keyed, "source": "answer_key", "confidence": 0.65}

        # Missing questions in key.
        for q, kinfo in key_map.items():
            if q not in q_map and not any(q in parse_answer_tokens(x.get("text", "")) for x in p.get("summary_answer_lines", [])):
                issues.append(issue(seq, "major", "missing_question", pid, q, [kinfo["source_index"]],
                                    "Answer Key contains a question number absent from extracted question area.",
                                    {"answer_key": kinfo["answer"]}, confidence=0.6, needs=True))
                seq += 1

        # Summary blank/answer checks.
        for item in q_area:
            if "______" not in item["text"]:
                continue
            blanks = SUMMARY_BLANK_RE.findall(item["text"])
            if not blanks:
                continue
            type_counts["summary"] += len(blanks)
            answer_lines = [parse_answer_tokens(x["text"]) for x in p.get("summary_answer_lines", [])]
            answer_line = {}
            for d in answer_lines:
                answer_line.update(d)
            key_summary = {q: v["answer"] for q, v in key_map.items() if q in blanks}
            candidate = answer_line or key_summary
            if len(candidate) != len(blanks) or any(q not in candidate for q in blanks):
                issues.append(issue(seq, "major", "summary_answer_mismatch", pid, f"{blanks[0]}-{blanks[-1]}",
                                    [item["index"]] + [x["index"] for x in p.get("summary_answer_lines", [])],
                                    "Summary blank count/question numbers do not match answer line.",
                                    {"blank_numbers": blanks, "answer_line": candidate}, confidence=0.7, needs=True))
                seq += 1
            for q in blanks:
                if q in candidate:
                    ans = candidate[q]
                    suggestions[f"P{pid}_Q{q}"] = {"answer": ans, "source": "summary_answer_line", "confidence": 0.65}
                    # Light context mismatch heuristics.
                    left = item["text"][: item["text"].find(f"({q})")].split()[-4:]
                    if left and left[-1].lower() in {"about", "approximately"} and not re.search(r"\d|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty", ans, re.I):
                        issues.append(issue(seq, "minor", "summary_answer_mismatch", pid, q, [item["index"]],
                                            "Summary answer may not fit numeric blank context.",
                                            {"answer": ans, "left_context": " ".join(left)}, confidence=0.45, needs=True))
                        seq += 1

        # Heading checks.
        if p.get("heading_list") or p.get("heading_answers"):
            type_counts["heading"] += len(p.get("heading_answers", {}))
            labels = {x.get("label") for x in p.get("paragraphs", [])}
            if len(p.get("heading_list", [])) < len(p.get("heading_answers", {})):
                issues.append(issue(seq, "blocking", "heading_structure_issue", pid, None, p.get("source_locations", []),
                                    "Heading pool count is smaller than heading target count.", confidence=0.9, needs=True))
                seq += 1
            for lab in p.get("heading_answers", {}):
                if lab not in labels:
                    issues.append(issue(seq, "major", "paragraph_split_issue", pid, None, p.get("source_locations", []),
                                        f"Heading answer references paragraph {lab}, but extracted paragraphs are {sorted(labels)}.",
                                        suggested="Check for merged/split paragraph labels.", confidence=0.8, needs=True))
                    seq += 1
        # Count obvious types.
        texts = [x["text"] for x in q_area]
        type_counts["mcq"] += sum(1 for x in texts if re.match(r"^\d+\.\s+", x) and any(o.get("text", "").startswith("A.") for o in q_area))
        type_counts["tfng"] += sum(1 for x in q_map.values() if x.get("embedded_answer") in {"TRUE", "FALSE", "NOT GIVEN"})
        type_counts["match"] += sum(1 for x in q_map.values() if x.get("embedded_answer") in {"A", "B", "C", "D", "E", "F"})

    severity_counts = Counter(i["severity"] for i in issues)
    verdict = "FAIL" if severity_counts["blocking"] else ("PARTIAL PASS" if severity_counts["major"] else "PASS")
    return {
        "schema_version": "reading_source_audit_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": raw.get("input_file"),
        "overall_verdict": verdict,
        "summary": {
            "passage_count": passage_count,
            "paragraph_count": paragraph_count,
            "question_count_estimate": question_count,
            "answer_count_estimate": answer_count,
            "type_distribution_estimate": dict(type_counts),
            "issue_count": len(issues),
            "blocking_count": severity_counts["blocking"],
            "major_count": severity_counts["major"],
            "minor_count": severity_counts["minor"],
        },
        "issues": issues,
        "suggested_answers": suggestions,
    }


def md_escape(v: Any) -> str:
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")


def write_markdown(audit_data: dict[str, Any], md_path: Path, raw_path: str, clean_path: str | None = None, html_path: str | None = None) -> None:
    issues = audit_data["issues"]
    by_sev = {s: [i for i in issues if i["severity"] == s] for s in ("blocking", "major", "minor")}
    s = audit_data["summary"]
    lines = [
        "# Reading Source Audit Report",
        "",
        "## 1. Overall Verdict",
        "",
        audit_data["overall_verdict"],
        "",
        "## 2. Input Files",
        "",
        f"- DOCX: `{audit_data.get('input_file')}`",
        f"- Raw JSON: `{raw_path}`",
        f"- Clean JSON: `{clean_path or ''}`",
        f"- HTML: `{html_path or ''}`",
        "",
        "## 3. Extraction Summary",
        "",
        f"- passage count: {s['passage_count']}",
        f"- paragraph count: {s['paragraph_count']}",
        f"- question count estimate: {s['question_count_estimate']}",
        f"- type distribution estimate: {s['type_distribution_estimate']}",
        f"- answer count estimate: {s['answer_count_estimate']}",
        f"- warning/issue count: {s['issue_count']}",
        "",
    ]
    for title, sev in [("4. Blocking Issues", "blocking"), ("5. Major Issues", "major"), ("6. Minor Issues", "minor")]:
        lines += [f"## {title}", ""]
        if not by_sev[sev]:
            lines += ["None.", ""]
        else:
            for it in by_sev[sev]:
                lines += [f"- **{it['issue_id']}** `{it['issue_type']}` P{it['passage_id']} Q{it.get('question_number') or ''}: {it['evidence']}"]
            lines.append("")
    lines += [
        "## 7. Question-Level Audit Table",
        "",
        "| Passage | Question | Type | Problem | DOCX question text | DOCX embedded answer | DOCX answer key | Suggested final answer | Evidence | Confidence | Needs human confirmation |",
        "|---|---:|---|---|---|---|---|---|---|---:|---|",
    ]
    for it in issues:
        cv = it.get("conflicting_values", {})
        lines.append("| " + " | ".join([
            md_escape(f"P{it['passage_id']}"), md_escape(it.get("question_number")), md_escape(it["issue_type"]),
            md_escape(it["severity"]), "", md_escape(cv.get("embedded_answer")), md_escape(cv.get("answer_key") or cv.get("answer_line")),
            md_escape(it.get("suggested_resolution")), md_escape(it.get("evidence")), md_escape(it.get("confidence")), md_escape(it.get("needs_human_confirmation")),
        ]) + " |")
    lines += ["", "## 8. Suggested Final Answer Table", "", "| Passage | Question | Final answer | Source | Confidence | Needs human confirmation |", "|---|---:|---|---|---:|---|"]
    for key, val in sorted(audit_data.get("suggested_answers", {}).items()):
        m = re.match(r"P(\d+)_Q(.+)", key)
        lines.append(f"| P{m.group(1) if m else ''} | {m.group(2) if m else key} | {md_escape(val.get('answer'))} | {md_escape(val.get('source'))} | {md_escape(val.get('confidence'))} | false |")
    lines += ["", "## 9. Recommended Next Action", ""]
    if audit_data["overall_verdict"] == "FAIL":
        lines.append("Do not generate final clean JSON without human confirmation for blocking issues.")
    elif audit_data["overall_verdict"] == "PARTIAL PASS":
        lines.append("Clean JSON candidate may be generated with warnings; human confirmation is recommended before replacing production HTML.")
    else:
        lines.append("Source is suitable for clean JSON and HTML generation.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--json-output", required=True)
    ap.add_argument("--md-output", required=True)
    ap.add_argument("--clean-json", default="")
    ap.add_argument("--html", default="")
    args = ap.parse_args()
    raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
    data = audit(raw)
    out = Path(args.json_output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(data, Path(args.md_output), args.raw, args.clean_json, args.html)
    print(f"Wrote audit JSON: {out}")
    print(f"Wrote audit MD: {args.md_output}")
    print(f"Verdict: {data['overall_verdict']} ({data['summary']['issue_count']} issue(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
