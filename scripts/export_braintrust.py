# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Compile an EvalPack into Braintrust export code (PRD §21).

Usage: uv run export_braintrust.py <pack-dir> [--out DIR]

Writes <out>/{eval_pack.py, pack_data.json, requirements.txt} (default
<pack>/exports/braintrust/). The canonical pack is read-only; everything
pack-specific compiles into pack_data.json and eval_pack.py is a verbatim
copy of the static sibling template. Run check_pack.py first as the
structural gate.
"""
import argparse
import json
import pathlib
import sys

import yaml

PINS = ["braintrust==0.32.0", "autoevals==0.0.130", "openai>=1.40,<3"]


def load(pack):
    manifest = yaml.safe_load((pack / "evalgrill.yaml").read_text())
    art = manifest["artifacts"]
    rubric = yaml.safe_load((pack / art["rubric"]).read_text())
    jsonl = lambda name: [json.loads(l) for l in (pack / art[name]).read_text().splitlines() if l]
    return manifest, rubric, jsonl("dataset"), jsonl("calibration")


def criterion_prompt(c):
    lines = ["You are grading one rubric criterion of a candidate research report.",
             "", f"Criterion: {c['id']}", c["description"].strip()]
    if c.get("why_it_matters"):
        lines += ["", "Why it matters: " + c["why_it_matters"].strip()]
    if c["kind"] == "veto":
        lines += ["", "This is a veto rule. Answer 'tripped' if the report violates it; "
                      "otherwise answer 'clear'."]
    else:
        lines += ["", "Scale anchors:"]
        lines += [f"  {k}: {c['scale'][k].strip()}" for k in sorted(c["scale"])]
        # bare-digit choice keys fail to parse with claude judges via the
        # Braintrust proxy (empirical); word keys are reliable
        lines += ["", "Answer with the level ("
                      + ", ".join(f"level_{k}" for k in sorted(c["scale"])) + ") that best matches."]
    lines += ["", "Task and evidence packet:", "{{input}}",
              "", "Candidate report to grade:", "{{output}}"]
    return "\n".join(lines)


def compile_criteria(rubric):
    out = []
    for c in rubric["criteria"]:
        veto = c["kind"] == "veto"
        scale_max = None if veto else max(c["scale"])  # level k -> k/(n-1) in [0,1]
        out.append({"id": c["id"], "kind": c["kind"], "importance": c.get("importance"),
                    "scale_max": scale_max,
                    "choice_scores": {"tripped": 0.0, "clear": 1.0} if veto
                    else {f"level_{k}": k / scale_max for k in c["scale"]},
                    "prompt_template": criterion_prompt(c)})
    return out


def inline_context(pack, paths):
    # Braintrust records must be self-contained: inline full source text.
    return [{"path": p, "text": (pack / p).read_text()} for p in paths]


def compile_dataset(pack, tasks):
    recs = []
    for t in tasks:
        # input = agent-visible only; grading_constraints ride in metadata,
        # which Braintrust passes to scorers but never to the task callable.
        recs.append({"id": t["id"],
                     "input": {"query": t["input"]["query"],
                               "context": inline_context(pack, t["input"].get("context", []))},
                     "expected": t["reference"],
                     "metadata": {**t.get("metadata", {}),
                                  "provenance": t.get("provenance"),
                                  "failure_targets": t.get("failure_targets", []),
                                  "grading_constraints": t.get("grading_constraints", []),
                                  "solvable": t.get("solvable"),
                                  "review": t.get("review")},
                     "tags": [t["metadata"]["difficulty"]]
                             if t.get("metadata", {}).get("difficulty") else []})
    return recs


def compile_calibration(pack, cases, tasks_by_id):
    out = []
    for case in cases:
        t = tasks_by_id[case["task_id"]]
        # Frozen candidate output rides inside input (identity-replay task);
        # candidate id stays in metadata so the judge prompt never sees it.
        out.append({"input": {"query": t["input"]["query"],
                              "context": inline_context(pack, t["input"].get("context", [])),
                              "candidate_output": case["candidate"]["output"]},
                    "expected": case["expected"],
                    "metadata": {"task_id": case["task_id"],
                                 "candidate_id": case["candidate"]["id"],
                                 "grading_constraints": t.get("grading_constraints", [])}})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()
    manifest, rubric, tasks, cases = load(args.pack)
    if manifest.get("status") != "READY_FOR_EXPERIMENT":
        print(f"note: pack status is {manifest.get('status')} — exporting anyway", file=sys.stderr)
    tasks_by_id = {t["id"]: t for t in tasks}
    data = {"schema_version": manifest["schema_version"],
            "project": manifest["name"],
            "status": manifest.get("status"),
            "judge_model": (manifest.get("runner") or {}).get("model") or "gpt-5-mini",
            "criteria": compile_criteria(rubric),
            "dataset": compile_dataset(args.pack, tasks),
            "calibration": compile_calibration(args.pack, cases, tasks_by_id)}
    out = args.out or args.pack / "exports" / "braintrust"
    out.mkdir(parents=True, exist_ok=True)
    (out / "pack_data.json").write_text(json.dumps(data, indent=1) + "\n")
    template = pathlib.Path(__file__).parent / "_braintrust_eval_pack.py"
    (out / "eval_pack.py").write_text(template.read_text())
    (out / "requirements.txt").write_text("\n".join(PINS) + "\n")
    print(f"exported {len(data['dataset'])} tasks, {len(data['calibration'])} calibration cases, "
          f"{len(data['criteria'])} criteria -> {out}")


if __name__ == "__main__":
    main()
