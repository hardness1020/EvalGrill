# /// script
# requires-python = ">=3.10"
# dependencies = ["jsonschema>=4.21", "pyyaml>=6"]
# ///
"""Validate the analyze-phase artifacts of an EvalPack directory.

Usage: uv run check_analysis.py <pack-dir>

Schema-checks failure-taxonomy.yaml + evaluation-dimensions.yaml against the
bundled schemas, then cross-checks: every dimension references known failure
modes, every failure mode is covered by at least one dimension, no duplicate ids.
"""
import json
import pathlib
import sys

import yaml
from jsonschema import Draft202012Validator

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"

ok = True


def check(instance, schema_name, label):
    global ok
    schema = json.loads((SCHEMAS / schema_name).read_text())
    for e in Draft202012Validator(schema).iter_errors(instance):
        print(f"FAIL {label}: {'/'.join(map(str, e.absolute_path))}: {e.message}")
        ok = False


def expect(cond, msg):
    global ok
    if not cond:
        ok = False
        print(f"FAIL xref: {msg}")


def main():
    pack = pathlib.Path(sys.argv[1])
    taxonomy = yaml.safe_load((pack / "failure-taxonomy.yaml").read_text())
    dimensions = yaml.safe_load((pack / "evaluation-dimensions.yaml").read_text())

    check(taxonomy, "failure-taxonomy.schema.json", "failure-taxonomy.yaml")
    check(dimensions, "evaluation-dimensions.schema.json", "evaluation-dimensions.yaml")

    fm_ids = [f["id"] for f in taxonomy["failure_modes"]]
    dim_ids = [d["id"] for d in dimensions["dimensions"]]
    expect(len(fm_ids) == len(set(fm_ids)), f"duplicate failure mode ids: {fm_ids}")
    expect(len(dim_ids) == len(set(dim_ids)), f"duplicate dimension ids: {dim_ids}")

    covered = set()
    for d in dimensions["dimensions"]:
        for fm in d["failure_modes"]:
            expect(fm in fm_ids, f"dimension {d['id']} -> unknown failure mode {fm}")
            covered.add(fm)
    for fm in fm_ids:
        expect(fm in covered, f"failure mode {fm} not covered by any dimension")

    print("OK: analysis artifacts valid" if ok else "FAILED")
    sys.exit(0 if ok else 1)


main()
