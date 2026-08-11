# /// script
# requires-python = ">=3.10"
# dependencies = ["jsonschema>=4.21", "pyyaml>=6"]
# ///
"""Validate an EvalPack directory against the canonical schemas + cross-artifact rules.

Usage: uv run scripts/check_pack.py <pack-dir>

ponytail: minimal checker grown from the ticket-07 prototype; the full validate
skill (lifecycle enforcement, coverage generation) is a later ticket.
"""
import json
import pathlib
import sys

import yaml
from jsonschema import Draft202012Validator, FormatChecker

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "plugin" / "schemas"


def load_schema(name):
    return json.loads((SCHEMAS / name).read_text())


ok = True


def check(instance, schema_name, label):
    global ok
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = list(validator.iter_errors(instance))
    for e in errors:
        print(f"FAIL {label}: {'/'.join(map(str, e.absolute_path))}: {e.message}")
    ok &= not errors


def expect(cond, msg):
    global ok
    if not cond:
        ok = False
        print(f"FAIL xref: {msg}")


def main():
    pack = pathlib.Path(sys.argv[1])
    manifest = yaml.safe_load((pack / "evalgrill.yaml").read_text())
    check(manifest, "evalgrill.schema.json", "evalgrill.yaml")

    art = manifest["artifacts"]
    taxonomy = yaml.safe_load((pack / art["failures"]).read_text())
    dimensions = yaml.safe_load((pack / art["dimensions"]).read_text())
    rubric = yaml.safe_load((pack / art["rubric"]).read_text())
    tasks = [json.loads(l) for l in (pack / art["dataset"]).read_text().splitlines() if l]
    cases = [json.loads(l) for l in (pack / art["calibration"]).read_text().splitlines() if l]

    check(taxonomy, "failure-taxonomy.schema.json", art["failures"])
    check(dimensions, "evaluation-dimensions.schema.json", art["dimensions"])
    check(rubric, "rubric.schema.json", art["rubric"])
    for t in tasks:
        check(t, "task.schema.json", f"task {t.get('id')}")
    for c in cases:
        check(c, "calibration-case.schema.json", f"case {c.get('task_id')}/{c['candidate']['id']}")

    coverage_path = pack / art["coverage"]
    if coverage_path.exists():
        coverage = yaml.safe_load(coverage_path.read_text())
        check(coverage, "coverage-matrix.schema.json", art["coverage"])
    else:
        coverage = None
        print(f"note: {art['coverage']} absent (generated artifact) — skipped")

    # Cross-artifact referential integrity (the validate script's job, not JSON Schema's)
    fm_ids = {f["id"] for f in taxonomy["failure_modes"]}
    crit = {c["id"]: c for c in rubric["criteria"]}
    task_ids = {t["id"] for t in tasks}
    scale_keys = lambda c: sorted(int(k) for k in c.get("scale", {}))

    for d in dimensions["dimensions"]:
        for fm in d["failure_modes"]:
            expect(fm in fm_ids, f"dimension {d['id']} -> unknown failure mode {fm}")
    for c in crit.values():
        for fm in c["failure_modes"]:
            expect(fm in fm_ids, f"criterion {c['id']} -> unknown failure mode {fm}")
        if "scale" in c:
            ks = scale_keys(c)
            expect(ks == list(range(len(ks))), f"criterion {c['id']} scale keys not contiguous from 0: {ks}")
    for t in tasks:
        for fm in t.get("failure_targets", []):
            expect(fm in fm_ids, f"task {t['id']} -> unknown failure mode {fm}")
        for ctx in t["input"].get("context", []):
            expect((pack / ctx).exists(), f"task {t['id']} -> missing context file {ctx}")

    def check_scores(scores, vetoes, ref):
        for k, level in scores.items():
            expect(k in crit and crit[k]["kind"] != "veto", f"{ref} score key {k} must be a non-veto criterion")
            if k in crit and crit[k]["kind"] != "veto":
                expect(level in scale_keys(crit[k]), f"{ref} {k}={level} outside scale")
        for k in vetoes:
            expect(k in crit and crit[k]["kind"] == "veto", f"{ref} veto key {k} must be a kind: veto criterion")

    case_refs = set()
    for case in cases:
        ref = f"{case['task_id']}/{case['candidate']['id']}"
        case_refs.add(ref)
        expect(case["task_id"] in task_ids, f"case {ref} -> unknown task")
        check_scores(case["expected"]["scores"], case["expected"]["vetoes"], f"case {ref}")

    if coverage:
        for row in coverage["rows"]:
            expect(row["failure_mode"] in fm_ids, f"coverage row -> unknown failure mode {row['failure_mode']}")

    runner = manifest.get("runner", {})
    if "replay_fixture" in runner:
        expect((pack / runner["replay_fixture"]).exists(), f"runner.replay_fixture missing: {runner['replay_fixture']}")

    # Demo fixtures, when present. Case-level lines are the Scripted Judge's
    # storage format; the replay runner projects them per-criterion, and the
    # orchestrator recomputes final_result against the stored value (ADR-0002).
    draft = pack / "fixtures" / "draft-rubric.yaml"
    if draft.exists():
        check(yaml.safe_load(draft.read_text()), "rubric.schema.json", "fixtures/draft-rubric.yaml")
    verdicts_path = pack / "fixtures" / "scripted-verdicts.jsonl"
    if verdicts_path.exists():
        for v in (json.loads(l) for l in verdicts_path.read_text().splitlines() if l):
            if v["mode"] == "single":
                ref = f"verdict {v['task_id']}/{v['candidate_id']} run {v['run']}"
                expect(f"{v['task_id']}/{v['candidate_id']}" in case_refs, f"{ref} -> no such calibration case")
                check_scores(v["scores"], v["vetoes"], ref)
                expect(v["final_result"] in ("pass", "fail"), f"{ref} bad final_result")
            else:
                ref = f"pairwise {v['first']} vs {v['second']}"
                expect(v["mode"] == "pairwise", f"unknown verdict mode {v['mode']}")
                for cid in (v["first"], v["second"]):
                    expect(f"{v['task_id']}/{cid}" in case_refs, f"{ref} -> no case {v['task_id']}/{cid}")
                expect(v["preferred"] in (v["first"], v["second"]), f"{ref} preferred not among pair")

    print("OK: pack valid" if ok else "FAILED")
    sys.exit(0 if ok else 1)


main()
