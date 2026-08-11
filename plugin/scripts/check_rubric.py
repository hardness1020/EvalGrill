# /// script
# requires-python = ">=3.10"
# dependencies = ["jsonschema>=4.21", "pyyaml>=6"]
# ///
"""Validate the rubric-phase artifacts of an EvalPack directory.

Usage: uv run check_rubric.py <pack-dir> [rubric-file]

Schema-checks rubric.yaml (or the given pack-relative rubric-file) against
rubric.schema.json, then cross-checks: unique criterion ids, failure_modes
exist in failure-taxonomy.yaml, contiguous scale keys, anchors that name no
observable behavior ([vague_criterion]), deterministic honesty against the
taxonomy ([hidden_deterministic], FR-8), vetoes the calibration set expects
([missing_veto]), and judge-protocol.yaml completeness. Non-fatal notes:
uncovered modes, unvetoed high-severity modes, absent human-review-guide.md.
"""
import json
import pathlib
import sys

import yaml
from jsonschema import Draft202012Validator, FormatChecker

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"

# Anchor words that grade enthusiasm, not behavior. An anchor built only from
# these (plus glue) gives two disagreeing judges nothing to point at.
VAGUE = {"quality", "good", "poor", "acceptable", "excellent", "great", "bad",
         "fine", "strong", "weak", "high", "low", "clear", "unclear", "clarity",
         "insightful", "thorough", "deep", "shallow", "well-organized",
         "well-written", "overall", "mediocre", "adequate", "inadequate"}
GLUE = {"the", "a", "an", "is", "are", "of", "and", "or", "very", "quite",
        "somewhat", "report", "output", "response", "answer"}

ok = True


def expect(cond, msg):
    global ok
    if not cond:
        ok = False
        print(f"FAIL {msg}")


def main():
    pack = pathlib.Path(sys.argv[1])
    rubric_file = sys.argv[2] if len(sys.argv) > 2 else "rubric.yaml"
    rubric = yaml.safe_load((pack / rubric_file).read_text())
    taxonomy = yaml.safe_load((pack / "failure-taxonomy.yaml").read_text())
    modes = {f["id"]: f for f in taxonomy["failure_modes"]}

    schema = json.loads((SCHEMAS / "rubric.schema.json").read_text())
    for e in Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(rubric):
        expect(False, f"{rubric_file}: {'/'.join(map(str, e.absolute_path))}: {e.message}")

    crits = rubric["criteria"]
    ids = [c["id"] for c in crits]
    expect(len(ids) == len(set(ids)),
           f"duplicate criterion ids: {sorted(i for i in set(ids) if ids.count(i) > 1)}")

    covered = set()
    for c in crits:
        label = f"criterion {c['id']}"
        primaries = []
        for fm in c["failure_modes"]:
            expect(fm in modes, f"{label} -> unknown failure mode {fm}")
            covered.add(fm)
            if fm in modes:
                primaries.append((modes[fm].get("evaluation_method") or {}).get("primary"))
        if "scale" in c:
            ks = sorted(int(k) for k in c["scale"])
            expect(ks == list(range(len(ks))), f"{label} scale keys not contiguous from 0: {ks}")
            for k, anchor in c["scale"].items():
                words = [w.strip(".,;:()").lower() for w in str(anchor).split()]
                vague = len(words) < 3 or all(w in VAGUE or w in GLUE for w in words)
                expect(not vague,
                       f"[vague_criterion] {label} scale[{k}] names no observable behavior: {anchor!r}")
        if primaries and all(p == "deterministic" for p in primaries):
            expect(c["deterministic"],
                   f"[hidden_deterministic] {label} deterministic: false but every mapped mode is primary: deterministic (FR-8)")

    uncovered = sorted(set(modes) - covered)
    if uncovered:
        print(f"note: modes with no criterion (coverage audit will flag): {uncovered}")

    # Missing-veto, hardened: the calibration set records which criteria humans
    # made zero-tolerance. A veto expected there but weighted (or absent) in
    # this rubric lets a disqualifying failure survive aggregation.
    cal_path = pack / "calibration.jsonl"
    if cal_path.exists():
        kinds = {c["id"]: c["kind"] for c in crits}
        expected_vetoes = {k for l in cal_path.read_text().splitlines() if l
                           for k in json.loads(l)["expected"]["vetoes"]}
        for k in sorted(expected_vetoes):
            expect(kinds.get(k) == "veto",
                   f"[missing_veto] calibration expects veto {k}; rubric has "
                   f"{'kind: ' + kinds[k] if k in kinds else 'no such criterion'}")

    veto_covered = {fm for c in crits if c["kind"] == "veto" for fm in c["failure_modes"]}
    if not any(c["kind"] == "veto" for c in crits):
        highs = sorted(m for m, f in modes.items() if f["severity"] in ("critical", "high"))
        if highs:
            print(f"note: no veto criteria — confirm none of these high/critical modes is zero-tolerance: {highs}")
    else:
        unvetoed = sorted(m for m, f in modes.items() if f["severity"] == "critical" and m not in veto_covered)
        if unvetoed:
            print(f"note: critical modes with no veto — confirm deliberately weighted: {unvetoed}")

    proto_path = pack / "judge-protocol.yaml"
    if proto_path.exists():
        proto = yaml.safe_load(proto_path.read_text())
        expect(proto.get("schema_version") == 1, "judge-protocol.yaml schema_version must be 1")
        for key in ("anonymization", "evidence_per_call", "rationale", "aggregation", "escalation"):
            expect(key in proto, f"judge-protocol.yaml missing {key}")
        if "repeats" not in proto:
            print("note: judge-protocol.yaml has no repeats — single-run verdicts hide judge variance")
    else:
        print("note: judge-protocol.yaml absent — write it before hand-off")

    if not (pack / "human-review-guide.md").exists():
        print("note: human-review-guide.md absent (PRD §30 output — write it before hand-off)")

    print("OK: rubric valid" if ok else "FAILED")
    sys.exit(0 if ok else 1)


main()
