#!/usr/bin/env python3
"""One-command DOCX → raw extraction → audit → clean JSON → optional HTML."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--clean-json", default="")
    ap.add_argument("--html-output", default="")
    ap.add_argument("--confirmed-answers", default="")
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "raw_docx_extraction.json"
    audit_json = out_dir / "source_audit.json"
    audit_md = out_dir / "source_audit.md"
    clean = Path(args.clean_json) if args.clean_json else out_dir / "clean_reading_data_candidate.json"
    warnings = out_dir / "extraction_warnings.json"

    run([sys.executable, "-B", str(SCRIPTS / "extract_docx_to_reading_json.py"), "--docx", args.docx, "--output", str(raw)])
    run([sys.executable, "-B", str(SCRIPTS / "audit_reading_source.py"), "--raw", str(raw), "--json-output", str(audit_json), "--md-output", str(audit_md), "--clean-json", str(clean), "--html", args.html_output])
    norm_cmd = [sys.executable, "-B", str(SCRIPTS / "normalize_reading_json.py"), "--raw", str(raw), "--audit", str(audit_json), "--output", str(clean)]
    if args.confirmed_answers:
        norm_cmd += ["--confirmed-answers", args.confirmed_answers]
    if args.allow_partial:
        norm_cmd.append("--allow-partial")
    run(norm_cmd)

    # Keep warnings easy to find.
    import json
    data = json.loads(clean.read_text(encoding="utf-8"))
    warnings.write_text(json.dumps(data.get("extraction_warnings", []), ensure_ascii=False, indent=2), encoding="utf-8")

    if args.html_output:
        run([sys.executable, "-B", str(SCRIPTS / "generate_reading.py"), "--data", str(clean), "--output", args.html_output])
    print("Outputs:")
    for p in [raw, audit_json, audit_md, clean, warnings]:
        print(" -", p)
    if args.html_output:
        print(" -", args.html_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
