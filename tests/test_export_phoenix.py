# /// script
# requires-python = ">=3.10"
# dependencies = ["arize-phoenix-client==2.13.0", "arize-phoenix-evals==3.4.0", "openai>=1.40,<3", "pyyaml>=6"]
# ///
"""Offline contract tests for the Phoenix exporter (PRD §21). No network:
judge calls are stubbed from the calibration set's human labels; the pinned
SDK versions above ARE the compatibility surface under test.

Usage: uv run tests/test_export_phoenix.py
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
EXPORTER = ROOT / "scripts" / "export_phoenix.py"

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
    out = pathlib.Path(tempfile.mkdtemp()) / "phoenix"
    r = subprocess.run([sys.executable, str(EXPORTER), str(PACK), "--out", str(out)],
                       capture_output=True, text=True)
    expect(r.returncode == 0, f"exporter exited {r.returncode}: {r.stderr}")
    expect(pack_digest() == before, "canonical pack files modified by export")
    for name in ("eval_pack.py", "pack_data.json", "requirements.txt"):
        expect((out / name).exists(), f"missing {name}")
    pins = (out / "requirements.txt").read_text()
    expect("arize-phoenix-client==2.13.0" in pins and "arize-phoenix-evals==3.4.0" in pins,
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
    from phoenix.evals.llm.prompts import PromptTemplate
    for cc, rc in zip(crits, rubric["criteria"]):
        expect(cc["kind"] == rc["kind"] and cc["importance"] == rc.get("importance"),
               f"{cc['id']}: kind/importance drift")
        if rc["kind"] == "veto":
            expect(cc["choices"] == {"tripped": 0.0, "clear": 1.0},
                   f"{cc['id']}: veto choices wrong")
        else:
            expect(cc["choices"] == {f"level_{k}": float(k) for k in sorted(rc["scale"])},
                   f"{cc['id']}: choices != raw scale levels")
            for k, anchor in rc["scale"].items():
                expect(anchor.strip() in cc["prompt_template"],
                       f"{cc['id']}: anchor {k} missing from prompt")
        expect(rc["description"].strip() in cc["prompt_template"],
               f"{cc['id']}: description missing from prompt")
        # phoenix renders mustache — evidence/candidate must be the ONLY
        # template variables (rubric prose must not inject {{...}} tags)
        got_vars = set(PromptTemplate(template=cc["prompt_template"]).variables)
        expect(got_vars == {"evidence", "candidate"},
               f"{cc['id']}: template variables {got_vars} != {{evidence, candidate}}")

    expect(len(data["calibration"]) == len(cal), "calibration case count drift")
    for comp, case in zip(data["calibration"], cal):
        expect(comp["input"]["candidate_output"] == case["candidate"]["output"],
               f"{case['candidate']['id']}: candidate output drift")
        expect(comp["expected"] == case["expected"], f"{case['candidate']['id']}: expected drift")
        expect(comp["metadata"]["candidate_id"] == case["candidate"]["id"],
               f"{case['candidate']['id']}: metadata candidate_id drift")

    # --- pinned-SDK construction contract ----------------------------------
    from phoenix.client import Client
    Client(base_url="http://localhost:9")  # no network on init
    spec = importlib.util.spec_from_file_location("eval_pack", out / "eval_pack.py")
    ep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ep)
    from phoenix.evals import ClassificationEvaluator
    from phoenix.evals.llm import LLM
    llm = LLM(provider="openai", model="fake-judge",
              base_url="http://localhost:9/v1", api_key="fake")
    ce = ClassificationEvaluator(name=crits[1]["id"], llm=llm,
                                 prompt_template=crits[1]["prompt_template"],
                                 choices={k: float(v) for k, v in crits[1]["choices"].items()},
                                 temperature=0)
    expect(set(ce.input_schema.model_fields) == {"evidence", "candidate"},
           "ClassificationEvaluator inferred wrong input schema")

    # --- generated evaluator semantics, judge stubbed from human labels ----
    def stub_from(expected):
        def stub(crit, evidence, output):
            if crit["kind"] == "veto":
                return expected["vetoes"][crit["id"]], "stub"
            return expected["scores"][crit["id"]], "stub"
        return stub

    def run_gate(comp):
        ep._verdicts.clear()  # memo is per-stub: never reuse across swaps
        return ep._gate(comp["input"], comp["input"]["candidate_output"], comp["metadata"])

    veto_case_seen = False
    for comp in data["calibration"]:
        exp = comp["expected"]
        ep.judge_raw = stub_from(exp)
        raw, tripped, essential_zero = run_gate(comp)
        ref = comp["metadata"]["candidate_id"]
        expect(raw == exp["scores"], f"{ref}: raw levels != human labels")
        expect(tripped == exp["vetoes"], f"{ref}: veto verdicts != human labels")
        final = 0.0 if any(tripped.values()) or essential_zero else 1.0
        want_final = 1.0 if exp["final_result"] == "pass" else 0.0
        expect(final == want_final, f"{ref}: gate {final} != {want_final}")
        if any(exp["vetoes"].values()):
            veto_case_seen = True
        evidence = ep.evidence_block(comp["input"], comp["metadata"])
        expect(ref not in evidence, f"{ref}: candidate id leaked into judge evidence")
        for gc in comp["metadata"]["grading_constraints"]:
            expect(gc in evidence, f"{ref}: grading constraint missing from judge evidence")
    expect(veto_case_seen, "no veto-tripping calibration case exercised the gate")

    # smoke slice: first passing case then the veto-tripping case
    picked = [c["metadata"]["candidate_id"] for c in ep.smoke_cases(2)]
    expect(picked == ["honest-effect-summary", "phantom-study"],
           f"smoke_cases(2) picked {picked}")

    # --- run_experiment wiring, fully local (dry_run + mock transport) -----
    # The real pinned harness: locally-built Dataset, identity task sees input
    # only, evaluator signatures are introspected, dry_run never records to
    # the server — its two dataset re-fetch GETs are served by a mock
    # transport so any other network call fails loudly. Both smoke cases run
    # (dry_run=2 samples min(len, 2) of 2).
    cases = ep.smoke_cases(2)
    by_output = {c["input"]["candidate_output"]: c["expected"] for c in cases}

    def live_stub(crit, evidence, output):
        exp = by_output[output]
        if crit["kind"] == "veto":
            return exp["vetoes"][crit["id"]], "stub"
        return exp["scores"][crit["id"]], "stub"
    ep.judge_raw = live_stub
    ep._verdicts.clear()

    from phoenix.client.resources.datasets import Dataset
    now = "2026-08-11T00:00:00+00:00"
    examples = [{"id": f"ex-{i}", "node_id": f"nx-{i}", "input": c["input"],
                 "output": c["expected"], "metadata": c["metadata"], "updated_at": now}
                for i, c in enumerate(cases)]
    ds_info = {"id": "ds-local", "name": "local-smoke", "description": None,
               "metadata": {}, "created_at": now, "updated_at": now,
               "example_count": len(examples)}
    examples_data = {"dataset_id": "ds-local", "version_id": "v-local", "examples": examples}
    ds = Dataset(ds_info, examples_data)

    import httpx

    def offline(request):
        if request.url.path == "/v1/datasets/ds-local":
            return httpx.Response(200, json={"data": ds_info})
        if request.url.path == "/v1/datasets/ds-local/examples":
            return httpx.Response(200, json={"data": examples_data})
        return httpx.Response(404, text=f"unexpected offline call: {request.url}")

    off = Client(http_client=httpx.Client(base_url="http://offline",
                                          transport=httpx.MockTransport(offline)))
    ran = off.experiments.run_experiment(
        dataset=ds,
        task=lambda input: input["candidate_output"],
        evaluators=ep.build_evaluators(),
        experiment_name="offline-contract",
        dry_run=2, print_summary=False)

    cand_of_example = ep.candidates_by_example(examples)
    got = ep.scores_by_candidate(ran, cand_of_example)
    cols = ep.score_columns()
    expect(len(got) == 2, f"dry-run evaluated {len(got)} cases, not 2")
    errors = [ev.error for ev in ran["evaluation_runs"] if ev.error]
    expect(not errors, f"evaluation errors in dry run: {errors}")
    for c in cases:
        cand = c["metadata"]["candidate_id"]
        exp = c["expected"]
        er = got.get(cand, {})
        expect(cols <= set(er), f"{cand}: dry run missing columns {cols - set(er)}")
        for cc in crits:
            if cc["kind"] == "veto":
                want = 0.0 if exp["vetoes"][cc["id"]] else 1.0
                expect(er.get("veto_" + cc["id"]) == want, f"{cand}: veto_{cc['id']} != {want}")
            else:
                expect(er.get(cc["id"]) == exp["scores"][cc["id"]],
                       f"{cand}: {cc['id']} != raw level {exp['scores'][cc['id']]}")
        expect(er.get("final_result") == (1.0 if exp["final_result"] == "pass" else 0.0),
               f"{cand}: final_result via run_experiment != expected")
        expect(er.get("judge_agreement") == 1.0, f"{cand}: agreement != 1.0 on exact replay")
    fr = {cand_of_example[r["dataset_example_id"]]:
          next(ev for ev in ran["evaluation_runs"]
               if ev.experiment_run_id == r["id"] and ev.name == "final_result")
          for r in ran["task_runs"]}
    veto_cand = next(c["metadata"]["candidate_id"] for c in cases
                     if any(c["expected"]["vetoes"].values()))
    res = fr[veto_cand].result
    res = res[0] if isinstance(res, list) else res
    expect(res.get("label") == "fail", f"{veto_cand}: final_result label != fail")
    expect(json.loads(res.get("explanation"))["veto_tripped"],
           f"{veto_cand}: veto not flagged in final_result explanation")

    # disagreement drill: a wrong verdict must dent agreement and flip the gate
    comp = next(c for c in data["calibration"] if c["expected"]["final_result"] == "pass")
    wrong = json.loads(json.dumps(comp["expected"]))
    wrong["scores"]["conflict_handling"] = 0  # essential at 0 -> fail
    ep.judge_raw = stub_from(wrong)
    raw, tripped, essential_zero = run_gate(comp)
    expect(essential_zero == ["conflict_handling"], "essential-at-0 gate did not fire")
    evs = {e.name: e for e in ep.build_evaluators()}
    fr_res = evs["final_result"].evaluate(input=comp["input"],
                                          output=comp["input"]["candidate_output"],
                                          metadata=comp["metadata"])
    agree = evs["judge_agreement"].evaluate(input=comp["input"],
                                            output=comp["input"]["candidate_output"],
                                            expected=comp["expected"],
                                            metadata=comp["metadata"])
    fr_res = fr_res[0] if isinstance(fr_res, list) else fr_res
    agree = agree[0] if isinstance(agree, list) else agree
    expect(fr_res["score"] == 0.0, "essential-at-0 gate did not fail the case")
    expect(agree["score"] < 1.0, "agreement blind to a wrong verdict")

    print("OK: phoenix export contract holds" if ok else "FAILED")
    sys.exit(0 if ok else 1)


main()
