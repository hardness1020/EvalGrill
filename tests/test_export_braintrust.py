# /// script
# requires-python = ">=3.10"
# dependencies = ["braintrust==0.32.0", "autoevals==0.0.130", "pyyaml>=6"]
# ///
"""Offline contract tests for the Braintrust exporter (PRD §21). No network:
judge calls are stubbed from the calibration set's human labels; the pinned
SDK versions above ARE the compatibility surface under test.

Usage: uv run tests/test_export_braintrust.py
"""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACK = ROOT / "demo" / "golden-pack"
EXPORTER = ROOT / "plugin" / "scripts" / "export_braintrust.py"

ok = True


def expect(cond, msg):
    global ok
    if not cond:
        ok = False
        print(f"FAIL {msg}")


def pack_digest():
    return {p: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(PACK.rglob("*")) if p.is_file() and "exports" not in p.parts}


def main():
    before = pack_digest()
    out = pathlib.Path(tempfile.mkdtemp()) / "braintrust"
    r = subprocess.run([sys.executable, str(EXPORTER), str(PACK), "--out", str(out)],
                       capture_output=True, text=True)
    expect(r.returncode == 0, f"exporter exited {r.returncode}: {r.stderr}")
    expect(pack_digest() == before, "canonical pack files modified by export")
    for name in ("eval_pack.py", "pack_data.json", "requirements.txt"):
        expect((out / name).exists(), f"missing {name}")
    pins = (out / "requirements.txt").read_text()
    expect("braintrust==0.32.0" in pins and "autoevals==0.0.130" in pins,
           "requirements.txt missing pinned SDK versions")

    # --- compiled data vs canonical pack -----------------------------------
    data = json.loads((out / "pack_data.json").read_text())
    rubric = yaml.safe_load((PACK / "rubric.yaml").read_text())
    tasks = [json.loads(l) for l in (PACK / "dataset.jsonl").read_text().splitlines() if l]
    cal = [json.loads(l) for l in (PACK / "calibration.jsonl").read_text().splitlines() if l]

    expect(data["project"] == "nr7-research-demo", "project != manifest name")
    expect([r["id"] for r in data["dataset"]] == [t["id"] for t in tasks],
           "dataset ids/order do not match canonical dataset.jsonl")
    for rec, t in zip(data["dataset"], tasks):
        expect(rec["input"]["query"] == t["input"]["query"], f"{t['id']}: query mangled")
        expect([d["path"] for d in rec["input"]["context"]] == t["input"].get("context", []),
               f"{t['id']}: context paths mangled")
        for d in rec["input"]["context"]:
            expect(d["text"] == (PACK / d["path"]).read_text(), f"{t['id']}: {d['path']} text drift")
        expect(rec["expected"] == t["reference"], f"{t['id']}: expected != reference")
        expect(set(rec["input"]) == {"query", "context"},
               f"{t['id']}: input carries agent-invisible fields: {set(rec['input'])}")
        for k in ("failure_targets", "grading_constraints", "review", "provenance"):
            expect(k in rec["metadata"], f"{t['id']}: metadata missing {k}")

    crits = data["criteria"]
    expect([c["id"] for c in crits] == [c["id"] for c in rubric["criteria"]],
           "criteria ids/order do not match rubric.yaml")
    for cc, rc in zip(crits, rubric["criteria"]):
        expect(cc["kind"] == rc["kind"] and cc["importance"] == rc.get("importance"),
               f"{cc['id']}: kind/importance drift")
        if rc["kind"] == "veto":
            expect(cc["choice_scores"] == {"tripped": 0.0, "clear": 1.0},
                   f"{cc['id']}: veto choice_scores wrong")
        else:
            n = max(rc["scale"])
            expect(cc["scale_max"] == n, f"{cc['id']}: scale_max != {n}")
            expect(cc["choice_scores"] == {f"level_{k}": k / n for k in rc["scale"]},
                   f"{cc['id']}: normalization != k/(n-1)")
            for k, anchor in rc["scale"].items():
                expect(anchor.strip() in cc["prompt_template"],
                       f"{cc['id']}: anchor {k} missing from prompt")
        expect(rc["description"].strip() in cc["prompt_template"],
               f"{cc['id']}: description missing from prompt")

    expect(len(data["calibration"]) == len(cal), "calibration case count drift")
    for comp, case in zip(data["calibration"], cal):
        expect(comp["input"]["candidate_output"] == case["candidate"]["output"],
               f"{case['candidate']['id']}: candidate output drift")
        expect(comp["expected"] == case["expected"], f"{case['candidate']['id']}: expected drift")
        expect(comp["metadata"]["candidate_id"] == case["candidate"]["id"],
               f"{case['candidate']['id']}: metadata candidate_id drift")

    # --- pinned-SDK construction contract ----------------------------------
    from autoevals import LLMClassifier
    from braintrust import Score
    LLMClassifier(name=crits[1]["id"], prompt_template=crits[1]["prompt_template"],
                  choice_scores=crits[1]["choice_scores"], use_cot=True, model="gpt-5-mini")
    try:
        Score(name="x", score=1.5)
        expect(False, "pinned braintrust no longer validates score range")
    except ValueError:
        pass

    # --- generated scorer semantics, judge stubbed from human labels -------
    spec = importlib.util.spec_from_file_location("eval_pack", out / "eval_pack.py")
    ep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ep)

    def stub_from(expected):
        def stub(crit, evidence, output):
            if crit["kind"] == "veto":
                return expected["vetoes"][crit["id"]], "stub"
            return expected["scores"][crit["id"]], "stub"
        return stub

    veto_case_seen = False
    for comp in data["calibration"]:
        exp = comp["expected"]
        ep.judge_raw = stub_from(exp)
        got = {s.name: s for s in ep.rubric_scorer(
            comp["input"], comp["input"]["candidate_output"], exp, comp["metadata"])}
        ref = comp["metadata"]["candidate_id"]
        for cc in crits:
            if cc["kind"] == "veto":
                want = 0.0 if exp["vetoes"][cc["id"]] else 1.0
                expect(got["veto_" + cc["id"]].score == want, f"{ref}: veto_{cc['id']} != {want}")
            else:
                lvl = exp["scores"][cc["id"]]
                expect(got[cc["id"]].score == lvl / cc["scale_max"],
                       f"{ref}: {cc['id']} not normalized to {lvl}/{cc['scale_max']}")
                expect(got[cc["id"]].metadata["ordinal_level"] == lvl,
                       f"{ref}: raw ordinal level not preserved in metadata")
        want_final = 1.0 if exp["final_result"] == "pass" else 0.0
        expect(got["final_result"].score == want_final,
               f"{ref}: final_result {got['final_result'].score} != {want_final}")
        expect(got["judge_agreement"].score == 1.0, f"{ref}: agreement != 1.0 on exact replay")
        if any(exp["vetoes"].values()):
            veto_case_seen = True
            expect(got["final_result"].metadata["veto_tripped"], f"{ref}: veto not flagged in metadata")
        evidence = ep.evidence_block(comp["input"], comp["metadata"])
        expect(ref not in evidence, f"{ref}: candidate id leaked into judge evidence")
        for gc in comp["metadata"]["grading_constraints"]:
            expect(gc in evidence, f"{ref}: grading constraint missing from judge evidence")
    expect(veto_case_seen, "no veto-tripping calibration case exercised the gate")

    # disagreement drill: a wrong verdict must dent agreement and flip the gate
    comp = next(c for c in data["calibration"] if c["expected"]["final_result"] == "pass")
    wrong = json.loads(json.dumps(comp["expected"]))
    wrong["scores"]["conflict_handling"] = 0  # essential at 0 -> fail
    ep.judge_raw = stub_from(wrong)
    got = {s.name: s for s in ep.rubric_scorer(
        comp["input"], comp["input"]["candidate_output"], comp["expected"], comp["metadata"])}
    expect(got["final_result"].score == 0.0, "essential-at-0 gate did not fail the case")
    expect(got["judge_agreement"].score < 1.0, "agreement blind to a wrong verdict")

    # smoke slice: first passing case then the veto-tripping case
    picked = [c["metadata"]["candidate_id"] for c in ep.smoke_cases(2)]
    expect(picked == ["honest-effect-summary", "phantom-study"],
           f"smoke_cases(2) picked {picked}")

    print("OK: braintrust export contract holds" if ok else "FAILED")
    sys.exit(0 if ok else 1)


main()
