#!/usr/bin/env python3
"""Smoke test for Module A DOCX/raw extraction → audit → clean JSON pipeline."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_reading_source.py"
NORMALIZE = ROOT / "scripts" / "normalize_reading_json.py"
VALIDATE = ROOT / "scripts" / "validate_reading.py"
GEN = ROOT / "scripts" / "generate_reading.py"
CLEAN_RAW = ROOT / "fixtures" / "docx_extraction" / "mock_raw_extraction_clean.json"
CONFLICT_RAW = ROOT / "fixtures" / "source_audit" / "mock_raw_extraction_conflict.json"


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def main() -> int:
    print("DOCX PIPELINE SMOKE TEST")
    errors = []
    with tempfile.TemporaryDirectory(prefix="reading-docx-pipeline-") as td:
        td = Path(td)
        # Clean fixture should audit and normalize to schema-compatible JSON.
        audit_json = td / "clean_audit.json"
        audit_md = td / "clean_audit.md"
        clean_json = td / "clean_candidate.json"
        html = td / "clean_candidate.html"
        r = run([sys.executable, "-B", str(AUDIT), "--raw", str(CLEAN_RAW), "--json-output", str(audit_json), "--md-output", str(audit_md), "--clean-json", str(clean_json), "--html", str(html)])
        print(r.stdout.strip())
        if r.returncode:
            print(r.stderr); errors.append("clean audit failed")
        else:
            data = json.loads(audit_json.read_text())
            if data.get("overall_verdict") != "PASS":
                errors.append(f"clean fixture expected PASS, got {data.get('overall_verdict')}")
        r = run([sys.executable, "-B", str(NORMALIZE), "--raw", str(CLEAN_RAW), "--audit", str(audit_json), "--output", str(clean_json)])
        print(r.stdout.strip())
        if r.returncode:
            print(r.stderr); errors.append("clean normalize failed")
        r = run([sys.executable, "-B", str(GEN), "--data", str(clean_json), "--output", str(html)])
        print(r.stdout.strip())
        if r.returncode:
            print(r.stderr); errors.append("clean generated HTML failed")
        r = run([sys.executable, "-B", str(VALIDATE), str(html)])
        print(r.stdout.strip())
        if r.returncode:
            print(r.stderr); errors.append("clean generated HTML validation failed")

        # Conflict fixture must detect answer_key_conflict + summary mismatch.
        audit_json2 = td / "conflict_audit.json"
        audit_md2 = td / "conflict_audit.md"
        r = run([sys.executable, "-B", str(AUDIT), "--raw", str(CONFLICT_RAW), "--json-output", str(audit_json2), "--md-output", str(audit_md2)])
        print(r.stdout.strip())
        if r.returncode:
            print(r.stderr); errors.append("conflict audit command failed")
        else:
            data = json.loads(audit_json2.read_text())
            issue_types = {i["issue_type"] for i in data.get("issues", [])}
            if "answer_key_conflict" not in issue_types:
                errors.append("conflict fixture did not detect answer_key_conflict")
            if "summary_answer_mismatch" not in issue_types:
                errors.append("conflict fixture did not detect summary_answer_mismatch")
            if data.get("overall_verdict") == "PASS":
                errors.append("conflict fixture unexpectedly PASS")
    if errors:
        print("DOCX PIPELINE SMOKE TEST FAILED ❌")
        for e in errors:
            print(" -", e)
        return 1
    print("DOCX PIPELINE SMOKE TEST PASSED ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
