# /// script
# requires-python = ">=3.10"
# dependencies = ["langsmith==0.10.17", "openevals==0.2.0", "langchain-openai>=1.4,<2", "pyyaml>=6"]
# ///
"""Offline contract tests for the LangSmith exporter (PRD §21). No network:
judge calls are stubbed from the calibration set's human labels; the pinned
SDK versions above ARE the compatibility surface under test.

Usage: uv run tests/test_export_langsmith.py
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACK = ROOT / "demo" / "golden-pack"
EXPORTER = ROOT / "scripts" / "export_langsmith.py"

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
    out = pathlib.Path(tempfile.mkdtemp()) / "langsmith"
    r = subprocess.run([sys.executable, str(EXPORTER), str(PACK), "--out", str(out)],
                       capture_output=True, text=True)
    expect(r.returncode == 0, f"exporter exited {r.returncode}: {r.stderr}")
    expect(pack_digest() == before, "canonical pack files modified by export")
    for name in ("eval_pack.py", "pack_data.json", "requirements.txt"):
        expect((out / name).exists(), f"missing {name}")
    pins = (out / "requirements.txt").read_text()
    expect("langsmith==0.10.17" in pins and "openevals==0.2.0" in pins,
           "requirements.txt missing pinned SDK versions")

    # --- compiled data vs canonical pack -----------------------------------
    data = json.loads((out / "pack_data.json").read_text())
    rubric = yaml.safe_load((PACK / "rubric.yaml").read_text())
    tasks = [json.loads(l) for l in (PACK / "dataset.jsonl").read_text().splitlines() if l]
    cal = [json.loads(l) for l in (PACK / "calibration.jsonl").read_text().splitlines() if l]

    expect(data["project"] == "nr7-research-demo", "project != manifest name")
    expect([r["metadata"]["evalpack_task_id"] for r in data["dataset"]] == [t["id"] for t in tasks],
           "dataset ids/order do not match canonical dataset.jsonl")
    for rec, t in zip(data["dataset"], tasks):
        expect(rec["inputs"]["query"] == t["input"]["query"], f"{t['id']}: query mangled")
        expect([d["path"] for d in rec["inputs"]["context"]] == t["input"].get("context", []),
               f"{t['id']}: context paths mangled")
        for d in rec["inputs"]["context"]:
            expect(d["text"] == (PACK / d["path"]).read_text(), f"{t['id']}: {d['path']} text drift")
        expect(rec["outputs"] == t["reference"], f"{t['id']}: outputs != reference")
        expect(set(rec["inputs"]) == {"query", "context"},
               f"{t['id']}: inputs carry agent-invisible fields: {set(rec['inputs'])}")
        for k in ("failure_targets", "grading_constraints", "review", "provenance"):
            expect(k in rec["metadata"], f"{t['id']}: metadata missing {k}")

    crits = data["criteria"]
    expect([c["id"] for c in crits] == [c["id"] for c in rubric["criteria"]],
           "criteria ids/order do not match rubric.yaml")
    for cc, rc in zip(crits, rubric["criteria"]):
        expect(cc["kind"] == rc["kind"] and cc["importance"] == rc.get("importance"),
               f"{cc['id']}: kind/importance drift")
        if rc["kind"] == "veto":
            expect(cc["choices"] == [0.0, 1.0], f"{cc['id']}: veto choices wrong")
        else:
            expect(cc["choices"] == [float(k) for k in sorted(rc["scale"])],
                   f"{cc['id']}: choices != raw scale levels")
            for k, anchor in rc["scale"].items():
                expect(anchor.strip() in cc["prompt_template"],
                       f"{cc['id']}: anchor {k} missing from prompt")
        expect(rc["description"].strip() in cc["prompt_template"],
               f"{cc['id']}: description missing from prompt")
        # openevals renders with str.format — must survive it with only
        # {inputs}/{outputs} as live placeholders
        try:
            p = cc["prompt_template"].format(inputs="<<EV>>", outputs="<<OUT>>")
            expect("<<EV>>" in p and "<<OUT>>" in p, f"{cc['id']}: placeholders not rendered")
        except (KeyError, IndexError, ValueError) as e:
            expect(False, f"{cc['id']}: prompt template breaks str.format: {e}")

    expect(len(data["calibration"]) == len(cal), "calibration case count drift")
    for comp, case in zip(data["calibration"], cal):
        expect(comp["inputs"]["candidate_output"] == case["candidate"]["output"],
               f"{case['candidate']['id']}: candidate output drift")
        expect(comp["outputs"] == case["expected"], f"{case['candidate']['id']}: expected drift")
        expect(comp["metadata"]["candidate_id"] == case["candidate"]["id"],
               f"{case['candidate']['id']}: metadata candidate_id drift")

    # --- pinned-SDK construction contract ----------------------------------
    from langsmith import Client
    Client(api_key="lsv2_pt_fake")  # no network on init
    spec = importlib.util.spec_from_file_location("eval_pack", out / "eval_pack.py")
    ep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ep)
    os.environ.setdefault("EVALGRILL_JUDGE_API_KEY", "fake")
    os.environ.setdefault("EVALGRILL_JUDGE_BASE_URL", "http://localhost:9")
    from openevals.llm import create_llm_as_judge
    create_llm_as_judge(prompt=crits[1]["prompt_template"], feedback_key=crits[1]["id"],
                        judge=ep._judge_client(), choices=crits[1]["choices"])

    # --- generated evaluator semantics, judge stubbed from human labels ----
    def stub_from(expected):
        def stub(crit, evidence, output):
            if crit["kind"] == "veto":
                return expected["vetoes"][crit["id"]], "stub"
            return expected["scores"][crit["id"]], "stub"
        return stub

    def run_evaluator(comp, expected):
        return {d["key"]: d for d in ep.rubric_evaluator(
            comp["inputs"], {"output": comp["inputs"]["candidate_output"]},
            expected, SimpleNamespace(metadata=comp["metadata"]))}

    veto_case_seen = False
    for comp in data["calibration"]:
        exp = comp["outputs"]
        ep.judge_raw = stub_from(exp)
        got = run_evaluator(comp, exp)
        ref = comp["metadata"]["candidate_id"]
        for cc in crits:
            if cc["kind"] == "veto":
                want = 0.0 if exp["vetoes"][cc["id"]] else 1.0
                expect(got["veto_" + cc["id"]]["score"] == want,
                       f"{ref}: veto_{cc['id']} != {want}")
            else:
                expect(got[cc["id"]]["score"] == exp["scores"][cc["id"]],
                       f"{ref}: {cc['id']} != raw level {exp['scores'][cc['id']]}")
        want_final = 1.0 if exp["final_result"] == "pass" else 0.0
        expect(got["final_result"]["score"] == want_final,
               f"{ref}: final_result {got['final_result']['score']} != {want_final}")
        expect(got["final_result"]["value"] == exp["final_result"],
               f"{ref}: final_result value != {exp['final_result']}")
        expect(got["judge_agreement"]["score"] == 1.0, f"{ref}: agreement != 1.0 on exact replay")
        if any(exp["vetoes"].values()):
            veto_case_seen = True
            expect(json.loads(got["final_result"]["comment"])["veto_tripped"],
                   f"{ref}: veto not flagged in final_result comment")
        evidence = ep.evidence_block(comp["inputs"], comp["metadata"])
        expect(ref not in evidence, f"{ref}: candidate id leaked into judge evidence")
        for gc in comp["metadata"]["grading_constraints"]:
            expect(gc in evidence, f"{ref}: grading constraint missing from judge evidence")
    expect(veto_case_seen, "no veto-tripping calibration case exercised the gate")

    # disagreement drill: a wrong verdict must dent agreement and flip the gate
    comp = next(c for c in data["calibration"] if c["outputs"]["final_result"] == "pass")
    wrong = json.loads(json.dumps(comp["outputs"]))
    wrong["scores"]["conflict_handling"] = 0  # essential at 0 -> fail
    ep.judge_raw = stub_from(wrong)
    got = run_evaluator(comp, comp["outputs"])
    expect(got["final_result"]["score"] == 0.0, "essential-at-0 gate did not fail the case")
    expect(got["judge_agreement"]["score"] < 1.0, "agreement blind to a wrong verdict")

    # smoke slice: first passing case then the veto-tripping case
    picked = [c["metadata"]["candidate_id"] for c in ep.smoke_cases(2)]
    expect(picked == ["honest-effect-summary", "phantom-study"],
           f"smoke_cases(2) picked {picked}")

    # --- evaluate() wiring, fully local (upload_results=False) -------------
    # The real pinned harness: target receives inputs only, evaluator signature
    # is introspected, list[dict] multi-score returns parse into feedback keys.
    import datetime
    import uuid
    import warnings
    from langsmith.schemas import Example
    by_output = {c["inputs"]["candidate_output"]: c["outputs"] for c in data["calibration"]}

    def live_stub(crit, evidence, output):
        exp = by_output[output]
        if crit["kind"] == "veto":
            return exp["vetoes"][crit["id"]], "stub"
        return exp["scores"][crit["id"]], "stub"
    ep.judge_raw = live_stub

    ds_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)
    examples = [Example(id=uuid.uuid4(), dataset_id=ds_id, created_at=now,
                        inputs=c["inputs"], outputs=c["outputs"], metadata=c["metadata"])
                for c in ep.smoke_cases(2)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # upload_results is flagged beta
        res = Client(api_key="lsv2_pt_fake").evaluate(
            lambda inputs: {"output": inputs["candidate_output"]},
            data=examples, evaluators=[ep.rubric_evaluator],
            upload_results=False, blocking=True)
    cols = {c["id"] for c in crits if c["kind"] != "veto"} \
        | {"veto_" + c["id"] for c in crits if c["kind"] == "veto"} \
        | {"final_result", "judge_agreement"}
    rows = list(res)
    expect(len(rows) == 2, f"local evaluate ran {len(rows)} rows, not 2")
    for row in rows:
        cand = row["example"].metadata["candidate_id"]
        exp = row["example"].outputs
        expect(row["run"].outputs == {"output": row["example"].inputs["candidate_output"]},
               f"{cand}: identity target output drift")
        er = {e.key: e.score for e in row["evaluation_results"]["results"]}
        expect(cols <= set(er), f"{cand}: local evaluate missing keys {cols - set(er)}")
        expect(er["final_result"] == (1.0 if exp["final_result"] == "pass" else 0.0),
               f"{cand}: final_result via evaluate() != expected")
        expect(er["judge_agreement"] == 1.0, f"{cand}: agreement != 1.0 via evaluate()")

    print("OK: langsmith export contract holds" if ok else "FAILED")
    sys.exit(0 if ok else 1)


main()
