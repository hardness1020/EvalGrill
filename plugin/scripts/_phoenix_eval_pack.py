# /// script
# requires-python = ">=3.10"
# dependencies = ["arize-phoenix-client==2.13.0", "arize-phoenix-evals==3.4.0", "openai>=1.40,<3"]
# ///
"""Phoenix export of an EvalGrill EvalPack — generated; edit the pack and
re-export, never this file. Everything pack-specific lives in pack_data.json.

Golden path (PRD §21): recreate the canonical tasks dataset, run the rubric
evaluators over calibration cases in a throwaway experiment, read scores back
in-process and via a get_experiment round trip, assert parity, delete the
throwaway calibration dataset. Server: local Docker self-host by default
(auth off); Cloud works with PHOENIX_API_KEY.

    uv run eval_pack.py [--cases N] [--experiment NAME]

Env: PHOENIX_BASE_URL (default http://localhost:6006), PHOENIX_API_KEY (only
if auth enabled / Cloud). Judge: EVALGRILL_JUDGE_BASE_URL (default Anthropic's
OpenAI-compatible endpoint), EVALGRILL_JUDGE_API_KEY (or ANTHROPIC_API_KEY),
EVALGRILL_JUDGE_MODEL (default: the pack's runner model). Any OpenAI-compatible
endpoint works, e.g. the Braintrust proxy with a Braintrust key.

Phoenix evaluators are independent annotations — no native veto semantics, no
cross-evaluator gating — so each criterion compiles to one
ClassificationEvaluator behind a memoized judge seam, and the veto /
essential-at-0 gate compiles into a final_result CODE evaluator that reads the
same memo (no duplicate judge calls). Per-criterion UI scores are indicative
only — gate on final_result. Protocol repeats (runs_per_case) are a
calibration-side concern; platform runs are one trial.
"""
import argparse
import json
import os
import pathlib
import sys
import time

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


def evidence_block(input, metadata=None):
    """Judge-visible evidence: query + full source texts + grading constraints.
    Candidate ids/provenance stay out (judge-protocol anonymization)."""
    docs = "\n\n".join(f"--- {d['path']} ---\n{d['text']}" for d in input.get("context", []))
    lines = [f"Task query: {input['query']}", "", "Source packet:", docs]
    gc = (metadata or {}).get("grading_constraints")
    if gc:
        lines += ["", "Grading constraints (judge-only): " + "; ".join(gc)]
    return "\n".join(lines)


def out_text(output):
    return output.get("output") if isinstance(output, dict) else output


_llm = None
_judges = {}


def _judge_llm():
    global _llm
    if _llm is None:
        from phoenix.evals.llm import LLM
        _llm = LLM(
            provider="openai",  # any OpenAI-compatible endpoint
            model=os.environ.get("EVALGRILL_JUDGE_MODEL", DATA["judge_model"]),
            base_url=os.environ.get("EVALGRILL_JUDGE_BASE_URL", "https://api.anthropic.com/v1/"),
            api_key=os.environ.get("EVALGRILL_JUDGE_API_KEY") or os.environ["ANTHROPIC_API_KEY"])
    return _llm


def judge_raw(crit, evidence, output):
    """One judge call for one criterion -> (raw_verdict, rationale); verdict is
    bool tripped for vetoes, int level otherwise. Offline contract tests stub
    this seam; live runs hit the configured OpenAI-compatible endpoint."""
    from phoenix.evals import ClassificationEvaluator
    ce = _judges.get(crit["id"])
    if ce is None:
        ce = _judges[crit["id"]] = ClassificationEvaluator(
            name=crit["id"], llm=_judge_llm(),
            prompt_template=crit["prompt_template"],
            choices={k: float(v) for k, v in crit["choices"].items()},
            temperature=0)
    try:
        s = ce.evaluate({"evidence": evidence, "candidate": output})[0]
    except Exception:  # one wrapper retry (runner-contract convention)
        s = ce.evaluate({"evidence": evidence, "candidate": output})[0]
    if s.score is None:
        raise RuntimeError(f"judge abstained on {crit['id']}")
    if crit["kind"] == "veto":
        return s.label == "tripped", s.explanation
    return int(s.score), s.explanation


_verdicts = {}


def verdict(crit, evidence, output):
    """Memoized judge seam: criterion evaluators, final_result, and
    judge_agreement all read one verdict per (criterion, example) — the gate
    never re-judges and never disagrees with the per-criterion annotations."""
    key = (crit["id"], evidence, output)
    if key not in _verdicts:
        _verdicts[key] = judge_raw(crit, evidence, output)
    return _verdicts[key]


def _gate(input, output, metadata):
    """Shared gate computation: (raw levels, tripped vetoes, essential-at-0)."""
    evidence = evidence_block(input, metadata)
    raw = {c["id"]: verdict(c, evidence, out_text(output))[0]
           for c in CRITERIA if c["kind"] != "veto"}
    tripped = {c["id"]: verdict(c, evidence, out_text(output))[0]
               for c in CRITERIA if c["kind"] == "veto"}
    essential_zero = [c["id"] for c in CRITERIA if c["kind"] != "veto"
                      and c.get("importance") == "essential" and raw.get(c["id"]) == 0]
    return raw, tripped, essential_zero


def build_evaluators():
    """One named evaluator per criterion (LLM kind), plus the gated
    final_result and calibration-only judge_agreement (CODE kind)."""
    from phoenix.client.experiments import create_evaluator
    evs = []
    for crit in CRITERIA:
        def crit_eval(input, output, metadata, crit=crit):
            v, rationale = verdict(crit, evidence_block(input, metadata), out_text(output))
            if crit["kind"] == "veto":
                return {"score": 0.0 if v else 1.0,
                        "label": "tripped" if v else "clear", "explanation": rationale}
            return {"score": float(v), "label": f"level_{v}", "explanation": rationale}
        name = "veto_" + crit["id"] if crit["kind"] == "veto" else crit["id"]
        evs.append(create_evaluator(kind="LLM", name=name)(crit_eval))

    def final_result(input, output, metadata):
        raw, tripped, essential_zero = _gate(input, output, metadata)
        final = 0.0 if any(tripped.values()) or essential_zero else 1.0
        return {"score": final, "label": "fail" if final == 0.0 else "pass",
                "explanation": json.dumps({"veto_tripped": any(tripped.values()),
                                           "essential_at_zero": essential_zero})}

    def judge_agreement(input, output, expected, metadata):
        """Judge-vs-human match on calibration cases (expected carries the
        human labels); first-class column per PRD §15."""
        if not expected or "scores" not in expected:
            return {"score": None, "label": "n/a",
                    "explanation": "no human labels on this example"}
        raw, tripped, _ = _gate(input, output, metadata)
        final = 0.0 if any(tripped.values()) or [
            c["id"] for c in CRITERIA if c["kind"] != "veto"
            and c.get("importance") == "essential" and raw.get(c["id"]) == 0] else 1.0
        hits = [raw.get(k) == v for k, v in expected["scores"].items()]
        hits += [tripped.get(k) == v for k, v in expected["vetoes"].items()]
        hits.append((final == 1.0) == (expected["final_result"] == "pass"))
        return {"score": sum(hits) / len(hits)}

    evs.append(create_evaluator(kind="CODE", name="final_result")(final_result))
    evs.append(create_evaluator(kind="CODE", name="judge_agreement")(judge_agreement))
    return evs


def score_columns():
    return {c["id"] for c in CRITERIA if c["kind"] != "veto"} \
        | {"veto_" + c["id"] for c in CRITERIA if c["kind"] == "veto"} \
        | {"final_result", "judge_agreement"}


def upload_dataset(client, name, records, description):
    """Recreate a dataset by name. It is a derived artifact — the pack is the
    source of truth, re-exported on demand. The client has no datasets.delete,
    so stale same-name datasets go through the REST endpoint directly."""
    for d in client.datasets.list():
        if d["name"] == name:
            client._client.delete(f"v1/datasets/{d['id']}").raise_for_status()
    return client.datasets.create_dataset(
        name=name, dataset_description=description,
        inputs=[r["input"] for r in records],
        outputs=[r["expected"] for r in records],
        metadata=[r["metadata"] for r in records])


def smoke_cases(n):
    """Deterministic smoke slice: first passing case, then the first
    veto-tripping case (exercises both branches of the gate), then the rest."""
    cal = DATA["calibration"]
    picked = []
    for probe in (lambda c: c["expected"]["final_result"] == "pass",
                  lambda c: any(c["expected"]["vetoes"].values())):
        hit = next((c for c in cal if probe(c) and c not in picked), None)
        if hit:
            picked.append(hit)
    picked += [c for c in cal if c not in picked]
    return picked[:n]


def candidates_by_example(examples):
    """Runs record dataset_example_id as the example's node GlobalID —
    node_id, or id on servers that predate the field."""
    return {ex.get("node_id") or ex["id"]: ex["metadata"]["candidate_id"]
            for ex in examples}


def scores_by_candidate(ran, cand_of_example):
    """Join evaluation_runs back into one {candidate: {column: score}} record
    per example (Phoenix stores one annotation per evaluator per run)."""
    cand_of_run = {r["id"]: cand_of_example[r["dataset_example_id"]]
                   for r in ran["task_runs"]}
    out = {}
    for ev in ran["evaluation_runs"]:
        res = ev.result
        if res is None:
            continue
        for r in res if isinstance(res, list) else [res]:
            out.setdefault(cand_of_run[ev.experiment_run_id], {})[ev.name] = r.get("score")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=2)
    ap.add_argument("--experiment", default=None)
    args = ap.parse_args()
    from phoenix.client import Client
    client = Client()  # PHOENIX_BASE_URL / PHOENIX_API_KEY from env

    upload_dataset(client, DATA["project"], DATA["dataset"],
                   f"EvalGrill export of {DATA['project']} "
                   f"(schema v{DATA['schema_version']}, status {DATA['status']})")
    print(f"dataset: {DATA['project']} ({len(DATA['dataset'])} examples)")

    cases = smoke_cases(args.cases)
    cal_name = f"{DATA['project']}-calibration-{int(time.time())}"
    cal_ds = upload_dataset(client, cal_name, cases,
                            "EvalGrill calibration smoke (throwaway)")
    cand_of_example = candidates_by_example(cal_ds.examples)

    ran = client.experiments.run_experiment(
        dataset=cal_ds,
        task=lambda input: input["candidate_output"],  # identity replay; never sees expected
        evaluators=build_evaluators(),
        experiment_name=args.experiment or "evalgrill-smoke",
        experiment_metadata={"evalgrill_schema_version": DATA["schema_version"],
                             "pack": DATA["project"], "pack_status": DATA["status"],
                             "judge_model": os.environ.get("EVALGRILL_JUDGE_MODEL",
                                                           DATA["judge_model"])},
        print_summary=False)

    cols = score_columns()
    local = scores_by_candidate(ran, cand_of_example)
    for c in cases:
        cand = c["metadata"]["candidate_id"]
        check(cols <= set(local.get(cand, {})),
              f"{cand}: all evaluator annotations present in-process")
        if any(c["expected"]["vetoes"].values()):
            got = local.get(cand, {}).get("final_result")
            check(got == 0.0, f"veto-tripping case {cand}: final_result == 0.0 (got {got})")

    # round trip: reconstruct from the server — proves persistence
    persisted = client.experiments.get_experiment(experiment_id=ran["experiment_id"])
    remote = scores_by_candidate(persisted, cand_of_example)
    for cand, scores in local.items():
        for key, val in scores.items():
            got = remote.get(cand, {}).get(key)
            check(got == val, f"round-trip score {cand}/{key} matches in-process ({val}, got {got})")

    # throwaway cleanup; the canonical dataset stays
    client._client.delete(f"v1/datasets/{cal_ds.id}").raise_for_status()
    print(f"experiment: {ran['experiment_id']}")
    sys.exit(0 if _ok else 1)


if __name__ == "__main__":
    main()
