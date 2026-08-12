# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Compile an EvalPack into LangSmith export code (PRD §21).

Usage: uv run export_langsmith.py <pack-dir> [--out DIR]

Writes <out>/{eval_pack.py, pack_data.json, requirements.txt} (default
<pack>/exports/langsmith/). The canonical pack is read-only; everything
pack-specific compiles into pack_data.json and eval_pack.py is a verbatim
copy of the static sibling template. Run check_pack.py first as the
structural gate.
"""
import argparse
import json
import pathlib
import sys

import yaml

PINS = ["langsmith==0.10.17", "openevals==0.2.0", "langchain-openai>=1.4,<2"]


def load(pack):
    manifest = yaml.safe_load((pack / "evalgrill.yaml").read_text())
    art = manifest["artifacts"]
    rubric = yaml.safe_load((pack / art["rubric"]).read_text())
    jsonl = lambda name: [json.loads(l) for l in (pack / art[name]).read_text().splitlines() if l]
    return manifest, rubric, jsonl("dataset"), jsonl("calibration")


def esc(s):
    # openevals renders prompts with str.format; criterion text must not
    # smuggle in placeholders
    return s.replace("{", "{{").replace("}", "}}")


def criterion_prompt(c):
    lines = ["You are grading one rubric criterion of a candidate research report.",
             "", f"Criterion: {c['id']}", esc(c["description"].strip())]
    if c.get("why_it_matters"):
        lines += ["", "Why it matters: " + esc(c["why_it_matters"].strip())]
    if c["kind"] == "veto":
        lines += ["", "This is a veto rule. Score 0 if the report violates it; "
                      "otherwise score 1."]
    else:
        lines += ["", "Scale anchors:"]
        lines += [f"  {k}: {esc(c['scale'][k].strip())}" for k in sorted(c["scale"])]
        lines += ["", "Score with the anchor number that best matches."]
    lines += ["", "Task and evidence packet:", "{inputs}",
              "", "Candidate report to grade:", "{outputs}"]
    return "\n".join(lines)


def compile_criteria(rubric):
    out = []
    for c in rubric["criteria"]:
        veto = c["kind"] == "veto"
        # choices constrain the judge's structured output; feedback keeps the
        # raw ordinal level (anchor-faithful; UI averages are indicative only)
        out.append({"id": c["id"], "kind": c["kind"], "importance": c.get("importance"),
                    "choices": [0.0, 1.0] if veto else [float(k) for k in sorted(c["scale"])],
                    "prompt_template": criterion_prompt(c)})
    return out


def inline_context(pack, paths):
    # LangSmith examples must be self-contained: inline full source text.
    return [{"path": p, "text": (pack / p).read_text()} for p in paths]


def compile_dataset(pack, tasks):
    recs = []
    for t in tasks:
        # inputs = agent-visible only; hidden fields ride in metadata and
        # reference outputs — the evaluate() target only ever receives inputs.
        recs.append({"inputs": {"query": t["input"]["query"],
                                "context": inline_context(pack, t["input"].get("context", []))},
                     "outputs": t["reference"],
                     "metadata": {**t.get("metadata", {}),
                                  "evalpack_task_id": t["id"],
                                  "provenance": t.get("provenance"),
                                  "failure_targets": t.get("failure_targets", []),
                                  "grading_constraints": t.get("grading_constraints", []),
                                  "solvable": t.get("solvable"),
                                  "review": t.get("review")}})
    return recs


def compile_calibration(pack, cases, tasks_by_id):
    out = []
    for case in cases:
        t = tasks_by_id[case["task_id"]]
        # Frozen candidate output rides inside inputs (identity-replay task);
        # candidate id stays in metadata so the judge prompt never sees it.
        out.append({"inputs": {"query": t["input"]["query"],
                               "context": inline_context(pack, t["input"].get("context", [])),
                               "candidate_output": case["candidate"]["output"]},
                    "outputs": case["expected"],
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
            "judge_model": (manifest.get("runner") or {}).get("model") or "claude-sonnet-5",
            "criteria": compile_criteria(rubric),
            "dataset": compile_dataset(args.pack, tasks),
            "calibration": compile_calibration(args.pack, cases, tasks_by_id)}
    out = args.out or args.pack / "exports" / "langsmith"
    out.mkdir(parents=True, exist_ok=True)
    (out / "pack_data.json").write_text(json.dumps(data, indent=1) + "\n")
    template = pathlib.Path(__file__).parent / "_langsmith_eval_pack.py"
    (out / "eval_pack.py").write_text(template.read_text())
    (out / "requirements.txt").write_text("\n".join(PINS) + "\n")
    print(f"exported {len(data['dataset'])} tasks, {len(data['calibration'])} calibration cases, "
          f"{len(data['criteria'])} criteria -> {out}")


if __name__ == "__main__":
    main()
