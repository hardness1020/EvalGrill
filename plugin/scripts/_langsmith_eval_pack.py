# /// script
# requires-python = ">=3.10"
# dependencies = ["langsmith==0.10.17", "openevals==0.2.0", "langchain-openai>=1.4,<2"]
# ///
"""LangSmith export of an EvalGrill EvalPack — generated; edit the pack and
re-export, never this file. Everything pack-specific lives in pack_data.json.

Golden path (PRD §21): recreate the canonical tasks dataset, run the composite
rubric evaluator over calibration cases in a throwaway experiment, read scores
back three ways (local ExperimentResults, read_project stats, list_feedback),
assert parity, delete the throwaway calibration dataset. No runs-listing APIs
(list_runs is deprecated; per-run GETs are rate-limited to 30/min).

    uv run eval_pack.py [--cases N] [--experiment NAME]

Env: LANGSMITH_API_KEY (required; plus LANGSMITH_WORKSPACE_ID /
LANGSMITH_ENDPOINT as needed). Judge: EVALGRILL_JUDGE_BASE_URL (default
Anthropic's OpenAI-compatible endpoint), EVALGRILL_JUDGE_API_KEY (or
ANTHROPIC_API_KEY), EVALGRILL_JUDGE_MODEL (default: the pack's runner model).
Any OpenAI-compatible endpoint works, e.g. the Braintrust proxy with a
Braintrust key.

LangSmith has no veto primitive and feedback keys are independent metrics, so
vetoes and the essential-at-0 gate compile into ONE evaluator returning
multi-score feedback: one key per criterion (raw ordinal level), veto_<id>
keys, and the gated final_result. Per-key UI averages are indicative only — a
run can average high on every criterion and still be a veto fail; gate on
final_result. Protocol repeats (runs_per_case) are a calibration-side concern;
platform runs are one trial.
"""
import argparse
import json
import os
import pathlib
import sys
import time
from collections import defaultdict

HERE = pathlib.Path(__file__).parent
DATA = json.loads((HERE / "pack_data.json").read_text())
CRITERIA = DATA["criteria"]

_ok = True


def check(cond, msg):
    global _ok
    if cond:
        print(f"PASS {msg}")
    else:
        _ok = False
        print(f"FAIL {msg}")


def evidence_block(inputs, metadata=None):
    """Judge-visible evidence: query + full source texts + grading constraints.
    Candidate ids/provenance stay out (judge-protocol anonymization)."""
    docs = "\n\n".join(f"--- {d['path']} ---\n{d['text']}" for d in inputs.get("context", []))
    lines = [f"Task query: {inputs['query']}", "", "Source packet:", docs]
    gc = (metadata or {}).get("grading_constraints")
    if gc:
        lines += ["", "Grading constraints (judge-only): " + "; ".join(gc)]
    return "\n".join(lines)


_client = None
_judges = {}


def _judge_client():
    global _client
    if _client is None:
        from langchain_openai import ChatOpenAI

        class FnCallJudge(ChatOpenAI):
            # ChatOpenAI defaults structured output to response_format
            # json_schema, which OpenAI-compatible Anthropic endpoints may not
            # support; tool calling is the one method they all do.
            def with_structured_output(self, schema, **kw):
                kw.setdefault("method", "function_calling")
                return super().with_structured_output(schema, **kw)

        _client = FnCallJudge(
            model=os.environ.get("EVALGRILL_JUDGE_MODEL", DATA["judge_model"]),
            base_url=os.environ.get("EVALGRILL_JUDGE_BASE_URL", "https://api.anthropic.com/v1/"),
            api_key=os.environ.get("EVALGRILL_JUDGE_API_KEY") or os.environ["ANTHROPIC_API_KEY"],
            temperature=0, max_tokens=16384)  # long CoT truncation drops the score
    return _client


def judge_raw(crit, evidence, output):
    """One judge call for one criterion -> (raw_verdict, rationale); verdict is
    bool tripped for vetoes, int level otherwise. Offline contract tests stub
    this seam; live runs hit the configured OpenAI-compatible endpoint."""
    from openevals.llm import create_llm_as_judge
    ev = _judges.get(crit["id"])
    if ev is None:
        ev = _judges[crit["id"]] = create_llm_as_judge(
            prompt=crit["prompt_template"], feedback_key=crit["id"],
            judge=_judge_client(), choices=crit["choices"])
    try:
        r = ev(inputs=evidence, outputs=output)
    except Exception:  # one wrapper retry (runner-contract convention)
        r = ev(inputs=evidence, outputs=output)
    if r["score"] is None:
        raise RuntimeError(f"judge abstained on {crit['id']}")
    if crit["kind"] == "veto":
        return r["score"] == 0.0, r.get("comment")
    return int(r["score"]), r.get("comment")


def rubric_evaluator(inputs, outputs, reference_outputs, example):
    """Composite evaluator: one feedback key per criterion and veto, plus the
    gated final_result (tripped veto -> fail; essential criterion at 0 ->
    fail). On calibration cases (reference outputs carry human labels) also
    emits judge_agreement so judge-vs-human match is a first-class key."""
    meta = getattr(example, "metadata", None) or {}
    evidence = evidence_block(inputs, meta)
    out_text = outputs.get("output") if isinstance(outputs, dict) else outputs
    feedback, raw, tripped = [], {}, {}
    for crit in CRITERIA:
        verdict, rationale = judge_raw(crit, evidence, out_text)
        if crit["kind"] == "veto":
            tripped[crit["id"]] = verdict
            feedback.append({"key": "veto_" + crit["id"],
                             "score": 0.0 if verdict else 1.0, "comment": rationale})
        else:
            raw[crit["id"]] = verdict
            feedback.append({"key": crit["id"], "score": verdict, "comment": rationale})
    veto_tripped = any(tripped.values())
    essential_zero = [c["id"] for c in CRITERIA if c["kind"] != "veto"
                      and c.get("importance") == "essential" and raw.get(c["id"]) == 0]
    final = 0.0 if veto_tripped or essential_zero else 1.0
    feedback.append({"key": "final_result", "score": final,
                     "value": "fail" if final == 0.0 else "pass",
                     "comment": json.dumps({"veto_tripped": veto_tripped,
                                            "essential_at_zero": essential_zero})})
    if reference_outputs and "scores" in reference_outputs:
        hits = [raw.get(k) == v for k, v in reference_outputs["scores"].items()]
        hits += [tripped.get(k) == v for k, v in reference_outputs["vetoes"].items()]
        hits.append((final == 1.0) == (reference_outputs["final_result"] == "pass"))
        feedback.append({"key": "judge_agreement", "score": sum(hits) / len(hits)})
    return feedback


def upload_dataset(client, name):
    """Recreate the canonical tasks dataset. It is a derived artifact — the
    pack is the source of truth, re-exported on demand."""
    if client.has_dataset(dataset_name=name):
        client.delete_dataset(dataset_name=name)
    ds = client.create_dataset(
        dataset_name=name,
        description=f"EvalGrill export of {DATA['project']} "
                    f"(schema v{DATA['schema_version']}, status {DATA['status']})")
    client.create_examples(dataset_id=ds.id, examples=DATA["dataset"])
    return ds


def smoke_cases(n):
    """Deterministic smoke slice: first passing case, then the first
    veto-tripping case (exercises both branches of the gate), then the rest."""
    cal = DATA["calibration"]
    picked = []
    for probe in (lambda c: c["outputs"]["final_result"] == "pass",
                  lambda c: any(c["outputs"]["vetoes"].values())):
        hit = next((c for c in cal if probe(c) and c not in picked), None)
        if hit:
            picked.append(hit)
    picked += [c for c in cal if c not in picked]
    return picked[:n]


def settle(fn, ready, tries=5):
    """Feedback lands server-side asynchronously; poll briefly."""
    for _ in range(tries):
        v = fn()
        if ready(v):
            return v
        time.sleep(2)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=2)
    ap.add_argument("--experiment", default=None)
    args = ap.parse_args()
    from langsmith import Client
    client = Client()

    ds = upload_dataset(client, DATA["project"])
    print(f"dataset: {DATA['project']} ({len(DATA['dataset'])} examples)")

    cases = smoke_cases(args.cases)
    cal_name = f"{DATA['project']}-calibration-{int(time.time())}"
    cal_ds = client.create_dataset(dataset_name=cal_name,
                                   description="EvalGrill calibration smoke (throwaway)")
    client.create_examples(dataset_id=cal_ds.id, examples=cases)
    ex_cand = {str(e.id): (e.metadata or {}).get("candidate_id")
               for e in client.list_examples(dataset_id=cal_ds.id)}

    results = client.evaluate(
        lambda inputs: {"output": inputs["candidate_output"]},  # identity replay
        data=cal_name,
        evaluators=[rubric_evaluator],
        experiment_prefix=args.experiment or "evalgrill-smoke",
        metadata={"evalgrill_schema_version": DATA["schema_version"],
                  "pack": DATA["project"], "pack_status": DATA["status"],
                  "judge_model": os.environ.get("EVALGRILL_JUDGE_MODEL", DATA["judge_model"])},
        max_concurrency=2, blocking=True)
    rows = list(results)

    cols = {c["id"] for c in CRITERIA if c["kind"] != "veto"} \
        | {"veto_" + c["id"] for c in CRITERIA if c["kind"] == "veto"} \
        | {"final_result", "judge_agreement"}
    local, run_of = {}, {}
    for row in rows:
        cand = ex_cand[str(row["example"].id)]
        run_of[cand] = row["run"].id
        local[cand] = {er.key: er.score for er in row["evaluation_results"]["results"]}
    for c in cases:
        cand = c["metadata"]["candidate_id"]
        check(cols <= set(local.get(cand, {})),
              f"{cand}: all feedback keys present in local results")
        if any(c["outputs"]["vetoes"].values()):
            got = local.get(cand, {}).get("final_result")
            check(got == 0.0, f"veto-tripping case {cand}: final_result == 0.0 (got {got})")

    proj = settle(lambda: client.read_project(project_name=results.experiment_name,
                                              include_stats=True),
                  lambda p: cols <= set(p.feedback_stats or {}))
    check(cols <= set(proj.feedback_stats or {}),
          "read_project feedback_stats reports all keys")

    def fetch_feedback():
        got = defaultdict(dict)
        for fb in client.list_feedback(run_ids=list(run_of.values())):
            got[str(fb.run_id)][fb.key] = fb.score
        return got
    rest = settle(fetch_feedback,
                  lambda g: all(cols <= set(g.get(str(r), {})) for r in run_of.values()))
    for cand, scores in local.items():
        for key, val in scores.items():
            got = rest.get(str(run_of[cand]), {}).get(key)
            # the server rounds feedback scores to 4 decimal places
            # (empirical: 5/7 came back as 0.7143), so compare at that grain
            check(got is not None and abs(float(got) - float(val)) <= 5e-5,
                  f"REST feedback {cand}/{key} matches local ({val}, got {got})")

    # throwaway cleanup; cascades to the smoke experiment too (verified above),
    # keeping trace quota clean. The canonical dataset stays.
    client.delete_dataset(dataset_id=cal_ds.id)
    print(f"experiment: {results.experiment_name}")
    sys.exit(0 if _ok else 1)


if __name__ == "__main__":
    main()
