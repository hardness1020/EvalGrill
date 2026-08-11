# /// script
# requires-python = ">=3.10"
# dependencies = ["braintrust==0.32.0", "autoevals==0.0.130", "openai>=1.40,<3"]
# ///
"""Braintrust export of an EvalGrill EvalPack — generated; edit the pack and
re-export, never this file. Everything pack-specific lives in pack_data.json.

Golden path (PRD §21): upsert the dataset by canonical id, run the composite
rubric scorer over calibration cases, read scores back via REST, assert match.

    uv run eval_pack.py [--cases N] [--experiment NAME]

Env: BRAINTRUST_API_KEY (required). Optional: BRAINTRUST_PROJECT,
BRAINTRUST_API_URL, EVALGRILL_JUDGE_MODEL, EVALGRILL_JUDGE_BASE_URL,
EVALGRILL_JUDGE_API_KEY. The judge defaults to the Braintrust AI proxy on the
pack's key (org must have a provider configured in Settings -> AI Providers);
point the JUDGE_* overrides at any OpenAI-compatible endpoint instead, e.g.
https://api.anthropic.com/v1/ with an Anthropic key.

Braintrust has no veto primitive and scorers cannot see each other's outputs,
so vetoes and the essential-at-0 gate compile into ONE scorer returning
per-criterion Scores plus the gated final_result. Protocol repeats
(runs_per_case) are a calibration-side concern; platform runs are one trial.
"""
import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
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


def evidence_block(input, metadata=None):
    """Judge-visible evidence: query + full source texts + grading constraints.
    Candidate ids/provenance stay out (judge-protocol anonymization)."""
    docs = "\n\n".join(f"--- {d['path']} ---\n{d['text']}" for d in input.get("context", []))
    lines = [f"Task query: {input['query']}", "", "Source packet:", docs]
    gc = (metadata or {}).get("grading_constraints")
    if gc:
        lines += ["", "Grading constraints (judge-only): " + "; ".join(gc)]
    return "\n".join(lines)


_judges = {}


def judge_raw(crit, evidence, output):
    """One judge call for one criterion -> (raw_verdict, rationale); verdict is
    bool tripped for vetoes, int level otherwise. Offline contract tests stub
    this seam; live runs route through the Braintrust proxy on the pack's key."""
    from autoevals import LLMClassifier
    import openai
    clf = _judges.get(crit["id"])
    if clf is None:
        client = openai.OpenAI(
            base_url=os.environ.get("EVALGRILL_JUDGE_BASE_URL",
                                    "https://api.braintrust.dev/v1/proxy"),
            api_key=os.environ.get("EVALGRILL_JUDGE_API_KEY")
            or os.environ["BRAINTRUST_API_KEY"])
        clf = _judges[crit["id"]] = LLMClassifier(
            name=crit["id"], prompt_template=crit["prompt_template"],
            choice_scores=crit["choice_scores"], use_cot=True,
            model=os.environ.get("EVALGRILL_JUDGE_MODEL", DATA["judge_model"]),
            temperature=0, max_tokens=4096,  # long CoT truncation drops 'choice'
            client=client)
    try:
        r = clf(output, None, input=evidence)
    except Exception:  # one wrapper retry (runner-contract convention)
        r = clf(output, None, input=evidence)
    if r.score is None:
        raise RuntimeError(f"judge abstained on {crit['id']}: {getattr(r, 'error', None)}")
    rationale = (r.metadata or {}).get("rationale")
    if crit["kind"] == "veto":
        return r.score == 0.0, rationale
    return round(r.score * crit["scale_max"]), rationale


def rubric_scorer(input, output, expected=None, metadata=None, **kwargs):
    """Composite scorer: one Score per criterion and veto, plus the gated
    final_result (tripped veto -> fail; essential criterion at 0 -> fail).
    On calibration cases (expected carries human labels) also emits
    judge_agreement so judge-vs-human match is a first-class column."""
    from braintrust import Score
    evidence = evidence_block(input, metadata)
    scores, raw, tripped = [], {}, {}
    for crit in CRITERIA:
        verdict, rationale = judge_raw(crit, evidence, output)
        if crit["kind"] == "veto":
            tripped[crit["id"]] = verdict
            scores.append(Score(name="veto_" + crit["id"], score=0.0 if verdict else 1.0,
                                metadata={"tripped": verdict, "rationale": rationale}))
        else:
            raw[crit["id"]] = verdict
            scores.append(Score(name=crit["id"], score=verdict / crit["scale_max"],
                                metadata={"ordinal_level": verdict,
                                          "scale_max": crit["scale_max"],
                                          "rationale": rationale}))
    veto_tripped = any(tripped.values())
    essential_zero = [c["id"] for c in CRITERIA if c["kind"] != "veto"
                      and c.get("importance") == "essential" and raw.get(c["id"]) == 0]
    final = 0.0 if veto_tripped or essential_zero else 1.0
    scores.append(Score(name="final_result", score=final,
                        metadata={"veto_tripped": veto_tripped,
                                  "essential_at_zero": essential_zero}))
    if expected and "scores" in expected:
        hits = [raw.get(k) == v for k, v in expected["scores"].items()]
        hits += [tripped.get(k) == v for k, v in expected["vetoes"].items()]
        hits.append((final == 1.0) == (expected["final_result"] == "pass"))
        scores.append(Score(name="judge_agreement", score=sum(hits) / len(hits)))
    return scores


def upload_dataset(project):
    import braintrust
    ds = braintrust.init_dataset(project=project, name="dataset")
    for r in DATA["dataset"]:
        ds.insert(id=r["id"], input=r["input"], expected=r["expected"],
                  metadata=r["metadata"], tags=r["tags"])
    ds.flush()
    return ds


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


def rest_get(url, tries=4):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["BRAINTRUST_API_KEY"]})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < tries - 1:
                time.sleep(2 ** i)
                continue
            raise


def _event_candidate(e):
    # root events carry record metadata; scorer spans (which hold the scores)
    # carry it nested under their input payload
    cand = (e.get("metadata") or {}).get("candidate_id")
    if not cand and isinstance(e.get("input"), dict):
        cand = (e["input"].get("metadata") or {}).get("candidate_id") \
            if isinstance(e["input"].get("metadata"), dict) else None
    return cand


def fetch_rest_scores(api, experiment_id, want_cands, tries=5):
    """Poll /fetch until every smoke candidate's scores have landed."""
    for i in range(tries):
        merged = defaultdict(dict)
        for e in rest_get(f"{api}/v1/experiment/{experiment_id}/fetch")["events"]:
            cand = _event_candidate(e)
            if cand and e.get("scores"):
                merged[cand].update(e["scores"])
        if want_cands <= set(merged):
            return merged
        time.sleep(2)
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=2)
    ap.add_argument("--experiment", default=None)
    args = ap.parse_args()
    from braintrust import Eval

    project = os.environ.get("BRAINTRUST_PROJECT", DATA["project"])
    ds = upload_dataset(project)
    print(f"dataset: {ds.summarize()}")

    cases = smoke_cases(args.cases)
    result = Eval(
        project,
        experiment_name=args.experiment,
        data=[{"input": c["input"], "expected": c["expected"], "metadata": c["metadata"]}
              for c in cases],
        task=lambda input: input["candidate_output"],  # identity replay; never sees expected
        scores=[rubric_scorer],
        metadata={"evalgrill_schema_version": DATA["schema_version"],
                  "pack": DATA["project"], "pack_status": DATA["status"],
                  "judge_model": os.environ.get("EVALGRILL_JUDGE_MODEL", DATA["judge_model"])},
        max_concurrency=2)
    summary = result.summary

    cols = {c["id"] for c in CRITERIA if c["kind"] != "veto"} \
        | {"veto_" + c["id"] for c in CRITERIA if c["kind"] == "veto"} \
        | {"final_result", "judge_agreement"}
    check(cols <= set(summary.scores), f"summary has all score columns {sorted(cols)}")

    by_cand = {r.metadata["candidate_id"]: r for r in result.results if not r.error}
    for c in cases:
        cand = c["metadata"]["candidate_id"]
        if any(c["expected"]["vetoes"].values()):
            got = by_cand[cand].scores.get("final_result") if cand in by_cand else None
            check(got == 0.0, f"veto-tripping case {cand}: final_result == 0.0 (got {got})")

    api = os.environ.get("BRAINTRUST_API_URL", "https://api.braintrust.dev")
    rest = fetch_rest_scores(api, summary.experiment_id, set(by_cand))
    for cand, r in by_cand.items():
        for name, val in r.scores.items():
            ok = name in rest.get(cand, {}) and abs(rest[cand][name] - val) < 1e-9
            check(ok, f"REST score {cand}/{name} matches in-process ({val})")
    rsum = rest_get(f"{api}/v1/experiment/{summary.experiment_id}/summarize?summarize_scores=true")
    names = set(rsum["scores"]) if isinstance(rsum["scores"], dict) \
        else {s["name"] for s in rsum["scores"]}
    check(cols <= names, "REST summarize reports all score columns")

    print(f"experiment: {summary.experiment_url or summary.experiment_name}")
    sys.exit(0 if _ok else 1)


if __name__ == "__main__":
    main()
