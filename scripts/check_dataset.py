# /// script
# requires-python = ">=3.10"
# dependencies = ["jsonschema>=4.21", "pyyaml>=6"]
# ///
"""Validate the dataset-phase artifacts of an EvalPack directory.

Usage: uv run check_dataset.py <pack-dir>

Schema-checks every dataset.jsonl line against task.schema.json, then
cross-checks: unique task ids, failure_targets exist in failure-taxonomy.yaml,
input.context paths resolve inside the pack. Non-fatal notes: absent
dataset-card.md, zero clean cases.
"""
import json
import pathlib
import sys

import yaml
from jsonschema import Draft202012Validator, FormatChecker

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"

ok = True


def expect(cond, msg):
    global ok
    if not cond:
        ok = False
        print(f"FAIL xref: {msg}")


def main():
    global ok
    pack = pathlib.Path(sys.argv[1])
    tasks = [json.loads(l) for l in (pack / "dataset.jsonl").read_text().splitlines() if l]
    taxonomy = yaml.safe_load((pack / "failure-taxonomy.yaml").read_text())
    fm_ids = {f["id"] for f in taxonomy["failure_modes"]}

    schema = json.loads((SCHEMAS / "task.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    ids = []
    for t in tasks:
        label = f"task {t.get('id')}"
        for e in validator.iter_errors(t):
            print(f"FAIL {label}: {'/'.join(map(str, e.absolute_path))}: {e.message}")
            ok = False
        ids.append(t.get("id"))
        for fm in t.get("failure_targets", []):
            expect(fm in fm_ids, f"{label} -> unknown failure mode {fm}")
        for ctx in t.get("input", {}).get("context", []):
            expect((pack / ctx).exists(), f"{label} -> missing context file {ctx}")

    expect(len(ids) == len(set(ids)), f"duplicate task ids: {sorted(i for i in set(ids) if ids.count(i) > 1)}")

    if not (pack / "dataset-card.md").exists():
        print("note: dataset-card.md absent (PRD §30 output — write it before hand-off)")
    if tasks and all(t.get("failure_targets") for t in tasks):
        print("note: no clean cases — every task targets a failure mode")

    print("OK: dataset valid" if ok else "FAILED")
    sys.exit(0 if ok else 1)


main()
