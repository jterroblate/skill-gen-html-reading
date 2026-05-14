#!/usr/bin/env python3
"""One-command smoke test for the JSON -> HTML reading generator.

Runs schema/data validation, generation, and HTML validation against checked-in
fixtures. Good fixtures must pass; the bad fixture must fail schema validation.
Temporary HTML is written only to a system temp directory.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
GEN = ROOT / "scripts" / "generate_reading.py"
VALIDATOR = ROOT / "scripts" / "validate_reading.py"
SCHEMA = ROOT / "schema" / "reading_data.schema.json"
GOOD_FIXTURES = [
    "minimal_1_passage.json",
    "heading_matching_inline_dropboxes.json",
    "escaping_edge_cases.json",
    "full_5_passage_all_types.json",
]
BAD_FIXTURE = "bad_missing_required.json"


def load_generator():
    spec = importlib.util.spec_from_file_location("generate_reading", GEN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run(cmd):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def main() -> int:
    print("READING HTML GENERATOR SMOKE TEST")
    print(f"Root: {ROOT}")
    errors = []

    try:
        json.loads(SCHEMA.read_text(encoding="utf-8"))
        print(f"PASS schema file is valid JSON: {SCHEMA.relative_to(ROOT)}")
    except Exception as exc:
        print(f"FAIL schema file invalid: {exc}")
        return 1

    gen = load_generator()

    with tempfile.TemporaryDirectory(prefix="reading-html-smoke-") as td:
        temp_dir = Path(td)
        for fixture_name in GOOD_FIXTURES:
            fixture = FIXTURES / fixture_name
            print(f"\nGOOD FIXTURE: {fixture_name}")
            try:
                data = json.loads(fixture.read_text(encoding="utf-8"))
                gen.validate_data(data)
                print("PASS schema/data validation")
            except Exception as exc:
                print(f"FAIL schema/data validation: {exc}")
                errors.append(f"{fixture_name}: schema validation failed")
                continue

            out = temp_dir / (fixture.stem + ".html")
            generated = run([sys.executable, "-B", str(GEN), "--data", str(fixture), "--output", str(out)])
            if generated.returncode != 0:
                print("FAIL generator")
                print(generated.stdout)
                print(generated.stderr)
                errors.append(f"{fixture_name}: generator failed")
                continue
            print("PASS generator")

            validated = run([sys.executable, "-B", str(VALIDATOR), str(out)])
            print(validated.stdout.strip())
            if validated.returncode != 0:
                print(validated.stderr)
                errors.append(f"{fixture_name}: validator failed")
            else:
                print("PASS validator")

        print(f"\nBAD FIXTURE: {BAD_FIXTURE}")
        bad = FIXTURES / BAD_FIXTURE
        try:
            data = json.loads(bad.read_text(encoding="utf-8"))
            gen.validate_data(data)
            print("FAIL bad fixture unexpectedly passed schema/data validation")
            errors.append("bad fixture unexpectedly passed")
        except Exception as exc:
            print("PASS bad fixture failed schema/data validation as expected")
            first_line = str(exc).splitlines()[0]
            print(f"  {first_line}")

    if errors:
        print("\nSMOKE TEST FAILED ❌")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("\nSMOKE TEST PASSED ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
