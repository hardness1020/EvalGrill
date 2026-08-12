# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Coverage + calibration audit over an EvalPack — the validate phase's engine.

Usage: uv run audit_pack.py <pack-dir> [--runner NAME]

Generates <pack>/coverage-matrix.yaml and <pack>/eval-audit.md. Detections are
printed as `DETECT <kind>: ...` lines (coverage_gap, judge_disagreement,
order_sensitivity, calibration_failure, reward_hacking) — they are findings,
not errors. Exit 1 only on structural faults (schema drift, replay miss,
aggregation mismatch, status overstating evidence).

Calibration runs through the Judge Runner seam (one criterion or one
presentation order per call). Two runners: replay (Scripted Judge, ADR-0002)
and claude-cli (live `claude -p`, ADR-0001; pinned model + timeout from
evalgrill.yaml's runner block). Rubric-defect detection lives in
check_rubric.py; run check_pack.py first as the structural gate.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from itertools import combinations

import yaml

ORDER = ["DRAFT", "STRUCTURALLY_VALID", "HUMAN_REVIEWED", "CALIBRATED", "READY_FOR_EXPERIMENT"]

ok = True
detections = []


def expect(cond, msg):
    global ok
    if not cond:
        ok = False
        print(f"FAIL {msg}")


def detect(kind, msg):
    detections.append((kind, msg))
    print(f"DETECT {kind}: {msg}")


# ---------------------------------------------------------------- runner seam
class ReplayRunner:
    """Scripted Judge: projects case-level fixture lines into per-criterion
    verdicts. A missing line or criterion is a loud replay_miss, never a
    fabricated verdict (ADR-0002)."""

    name = "replay"

    def __init__(self, fixture_path):
        self.singles, self.pairs = {}, {}
        for line in fixture_path.read_text().splitlines():
            if not line:
                continue
            v = json.loads(line)
            if v["mode"] == "single":
                self.singles[(v["task_id"], v["candidate_id"], v["run"])] = v
            else:
                self.pairs[(v["task_id"], v["run"], v["first"], v["second"])] = v

    def stored_final(self, task_id, cand_id, run):
        line = self.singles.get((task_id, cand_id, run))
        return line and line["final_result"]

    def judge(self, call):
        """One Judge Call -> (verdict, None) or (None, RunnerError). The call
        payload is contract-complete but unread here; live runners consume it."""
        if call["mode"] == "single":
            line = self.singles.get((call["task_id"], call["candidate_id"], call["run"]))
            cid = call["criterion_id"]
            if line is None or (cid not in line["scores"] and cid not in line["vetoes"]):
                return None, self._miss(call, f"{call['task_id']}/{call['candidate_id']} run {call['run']} criterion {cid}")
            verdict = {"tripped": line["vetoes"][cid]} if cid in line["vetoes"] else {"level": line["scores"][cid]}
        else:
            line = self.pairs.get((call["task_id"], call["run"], call["first"], call["second"]))
            if line is None:
                return None, self._miss(call, f"pairwise {call['first']} vs {call['second']} run {call['run']}")
            verdict = {"preferred": "A" if line["preferred"] == call["first"] else "B"}
        return {"verdict": verdict, "rationale": line["rationale"],
                "meta": {"source": "replay", "judge": line["meta"]["judge"], "runner": self.name}}, None

    def _miss(self, call, detail):
        return {"error": {"kind": "replay_miss", "retryable": False, "detail": detail}, "call": call}


class ClaudeCliRunner:
    """Live judge via `claude -p` (ADR-0001): pinned model, --setting-sources ""
    isolation, --json-schema verdicts, caller-enforced timeout. Valid iff
    exit==0 and !is_error and subtype=="success" and structured_output present;
    branch on is_error, never subtype (a 404 arrives with subtype "success")."""

    name = "claude-cli"

    def __init__(self, pack, model, timeout_s):
        self.pack, self.model, self.timeout_s = pack, model, timeout_s

    def judge(self, call):
        prompt, schema = self._render(call)
        cmd = ["claude", "-p", prompt, "--model", self.model,
               "--output-format", "json", "--json-schema", json.dumps(schema),
               "--setting-sources", "", "--tools", "", "--strict-mcp-config",
               "--disable-slash-commands", "--no-session-persistence"]
        t0 = time.monotonic()
        try:  # neutral cwd: never the repo under evaluation
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=self.timeout_s, cwd=tempfile.gettempdir())
        except subprocess.TimeoutExpired:
            return None, self._err(call, "timeout", True, f"no envelope within {self.timeout_s}s")
        try:
            env = json.loads(proc.stdout)
        except ValueError:
            detail = (proc.stderr.strip() or proc.stdout)[:200]
            return None, self._err(call, "invalid_output", True,
                                   f"exit {proc.returncode}, unparseable envelope: {detail}")
        if proc.returncode != 0 or env.get("is_error"):
            status = env.get("api_error_status")
            retryable = status in (None, 429) or status >= 500
            return None, self._err(call, "api_error", retryable,
                                   f"exit {proc.returncode}, api_error_status {status}: "
                                   f"{str(env.get('result'))[:200]}")
        so = env.get("structured_output")
        if env.get("subtype") != "success" or not isinstance(so, dict):
            return None, self._err(call, "invalid_output", True,
                                   f"subtype {env.get('subtype')!r}, structured_output missing")
        if call["mode"] == "pairwise":
            verdict = {"preferred": so["preferred"]}
        elif call["payload"]["criterion"]["kind"] == "veto":
            verdict = {"tripped": so["tripped"]}
        else:
            verdict = {"level": so["level"]}
        models = list(env.get("modelUsage") or {})  # key = full snapshot id that actually ran
        return {"verdict": verdict, "rationale": so.get("rationale", ""),
                "meta": {"source": "live", "judge": models[0] if models else self.model,
                         "runner": self.name, "retries": 0,
                         "duration_ms": int((time.monotonic() - t0) * 1000),
                         "cost_usd": env.get("total_cost_usd")}}, None

    RATIONALE = {"rationale": {"type": "string"}}

    def _render(self, call):
        p = call["payload"]
        if call["mode"] == "pairwise":
            prompt = "\n".join([
                "You are an impartial evaluation judge comparing two candidate responses to the same task.",
                "", "## Task query", p["query"],
                "", "## Response A", p["response_a"], "", "## Response B", p["response_b"],
                "", 'Which response better answers the task query overall? Set preferred to "A" or "B" '
                "and give a brief rationale."])
            return prompt, {"type": "object", "additionalProperties": False,
                            "required": ["preferred", "rationale"],
                            "properties": {"preferred": {"enum": ["A", "B"]}} | self.RATIONALE}
        c = p["criterion"]
        lines = ["You are an impartial evaluation judge. Grade one candidate response "
                 "against exactly one rubric criterion.", "", "## Task query", p["query"]]
        if p["context_docs"]:
            lines += ["", "## Source documents in the task packet (the only permitted sources)"]
            for doc in p["context_docs"]:
                lines += ["", f"### {doc}", (self.pack / doc).read_text().strip()]
        if p["grading_constraints"]:
            lines += ["", "## Grading constraints (grader-only; the candidate never saw these)"]
            lines += [f"- {g}" for g in p["grading_constraints"]]
        lines += ["", "## Candidate response", p["candidate_text"],
                  "", f"## Criterion under evaluation: {c['id']}", c["description"].strip()]
        if c["kind"] == "veto":
            lines += ["", "This is a veto criterion. Set tripped=true only if the condition it "
                      "describes occurs; otherwise tripped=false. Judge this criterion alone; "
                      "ignore any other flaws. Give a brief rationale."]
            return "\n".join(lines), {
                "type": "object", "additionalProperties": False,
                "required": ["tripped", "rationale"],
                "properties": {"tripped": {"type": "boolean"}} | self.RATIONALE}
        scale = {int(k): v for k, v in c["scale"].items()}
        lines += ["", "Levels:"] + [f"- {k}: {scale[k].strip()}" for k in sorted(scale)]
        lines += ["", f"Set level to the single anchor that best matches "
                  f"({min(scale)}–{max(scale)}). Judge this criterion alone; "
                  "ignore any other flaws. Give a brief rationale."]
        return "\n".join(lines), {
            "type": "object", "additionalProperties": False,
            "required": ["level", "rationale"],
            "properties": {"level": {"type": "integer", "minimum": min(scale),
                                     "maximum": max(scale)}} | self.RATIONALE}

    def _err(self, call, kind, retryable, detail):
        return {"error": {"kind": kind, "retryable": retryable, "detail": detail}, "call": call}


def preflight_claude_auth():
    """ADR-0001 watch-item: fail fast if subscription OAuth is unavailable."""
    try:
        out = subprocess.run(["claude", "auth", "status"], capture_output=True,
                             text=True, timeout=30)
        auth = json.loads(out.stdout)
    except Exception as e:  # missing binary, timeout, non-JSON output
        sys.exit(f"claude auth preflight failed: {e}")
    if not auth.get("loggedIn"):
        sys.exit("claude CLI not logged in — the claude-cli runner needs subscription auth (ADR-0001)")


def make_runner(name, pack, manifest):
    cfg = manifest.get("runner", {})
    if name == "replay":
        fixture = cfg.get("replay_fixture")
        if not fixture:
            sys.exit("no runner.replay_fixture in evalgrill.yaml — nothing to replay")
        return ReplayRunner(pack / fixture)
    if name == "claude-cli":
        preflight_claude_auth()
        return ClaudeCliRunner(pack, cfg.get("model", "claude-haiku-4-5-20251001"),
                               cfg.get("timeout_s", 120))
    sys.exit(f"unknown runner {name!r} — use replay or claude-cli")


# ------------------------------------------------------------------- loading
def load_pack(pack):
    manifest = yaml.safe_load((pack / "evalgrill.yaml").read_text())
    art = manifest["artifacts"]
    read = lambda name: yaml.safe_load((pack / art[name]).read_text())
    jsonl = lambda name: [json.loads(l) for l in (pack / art[name]).read_text().splitlines() if l]
    protocol = yaml.safe_load((pack / art["protocol"]).read_text()) if "protocol" in art else {}
    return manifest, read("failures"), read("rubric"), jsonl("dataset"), jsonl("calibration"), protocol


# ------------------------------------------------------------------ coverage
def build_coverage(taxonomy, rubric, tasks, cases):
    """One row per failure mode. A calibration case grounds a mode when the
    human labels show the mode firing: an expected 0 (or tripped veto) on a
    criterion mapped to it."""
    rows = []
    for f in taxonomy["failure_modes"]:
        mode = f["id"]
        mode_tasks = [t["id"] for t in tasks if mode in t.get("failure_targets", [])]
        crits = [c["id"] for c in rubric["criteria"] if mode in c["failure_modes"]]
        firing = []
        for case in cases:
            exp = case["expected"]
            for c in rubric["criteria"]:
                if mode not in c["failure_modes"]:
                    continue
                fired = exp["vetoes"].get(c["id"]) if c["kind"] == "veto" else exp["scores"].get(c["id"]) == 0
                if fired:
                    firing.append(f"{case['task_id']}/{case['candidate']['id']}")
                    break
        gaps = []
        if not mode_tasks:
            gaps.append("no_task")
        if not crits:
            gaps.append("no_criterion")
        if crits and not mode_tasks:
            gaps.append("criterion_without_task")
        if not firing:
            gaps.append("no_calibration_case")
        row = {"failure_mode": mode, "severity": f["severity"], "tasks": mode_tasks,
               "criteria": crits, "calibration": firing,
               "status": "gap" if gaps else "covered"}
        if gaps:
            row["gaps"] = gaps
            sev = f["severity"]
            emphasis = " — a {}-severity mode the dataset never exercises".format(sev) if sev in ("critical", "high") else ""
            detect("coverage_gap", f"{mode} ({', '.join(gaps)}){emphasis}")
        rows.append(row)
    return rows


# --------------------------------------------------------------- calibration
def aggregate(criteria, scores, vetoes):
    """The protocol's final_result rule: tripped veto -> fail; any essential
    criterion at 0 -> fail; otherwise pass."""
    if any(vetoes.values()):
        return "fail"
    for c in criteria:
        if c["kind"] != "veto" and c.get("importance") == "essential" and scores.get(c["id"]) == 0:
            return "fail"
    return "pass"


def single_call(task, case, run, criterion):
    return {"mode": "single", "task_id": task["id"], "candidate_id": case["candidate"]["id"],
            "run": run, "criterion_id": criterion["id"],
            "payload": {"query": task["input"]["query"],
                        "context_docs": task["input"].get("context", []),
                        "grading_constraints": task.get("grading_constraints", []),
                        "candidate_text": case["candidate"]["output"],
                        "criterion": {k: criterion[k] for k in ("id", "kind", "description")}
                        | ({"scale": criterion["scale"]} if "scale" in criterion else {})}}


def run_singles(runner, rubric, tasks_by_id, cases, runs_per_case):
    results = []
    for case in cases:
        task = tasks_by_id[case["task_id"]]
        ref = f"{case['task_id']}/{case['candidate']['id']}"
        exp = case["expected"]
        expect(aggregate(rubric["criteria"], exp["scores"], exp["vetoes"]) == exp["final_result"],
               f"case {ref}: expected.final_result inconsistent with aggregation rule")
        for run in range(1, runs_per_case + 1):
            scores, vetoes, incomplete = {}, {}, None
            for c in rubric["criteria"]:
                verdict, err = runner.judge(single_call(task, case, run, c))
                if err and err["error"]["retryable"]:
                    verdict, err = runner.judge(single_call(task, case, run, c))  # one wrapper retry
                    if verdict:
                        verdict["meta"]["retries"] = 1
                if err:
                    incomplete = f"{err['error']['kind']}: {err['error']['detail']}"
                    break
                expect(verdict["meta"].get("source") in ("live", "replay"),
                       f"case {ref} run {run}: verdict missing meta.source (ADR-0002)")
                if c["kind"] == "veto":
                    vetoes[c["id"]] = verdict["verdict"]["tripped"]
                else:
                    scores[c["id"]] = verdict["verdict"]["level"]
            final = None
            if not incomplete:
                final = aggregate(rubric["criteria"], scores, vetoes)
                stored = getattr(runner, "stored_final", lambda *a: None)(case["task_id"], case["candidate"]["id"], run)
                if stored:
                    expect(final == stored,
                           f"case {ref} run {run}: recomputed final_result {final} != scripted {stored}")
            results.append({"case": case, "ref": ref, "run": run, "scores": scores,
                            "vetoes": vetoes, "final": final, "incomplete": incomplete})
    return results


def run_pairwise(runner, tasks_by_id, cases):
    """Probe order sensitivity on human-declared ties: same task, identical
    expected labels, both passing — the pairs a ranking must order fairly."""
    by_task = defaultdict(list)
    for case in cases:
        by_task[case["task_id"]].append(case)
    outcomes = []
    for task_id, group in by_task.items():
        for a, b in combinations(sorted(group, key=lambda c: c["candidate"]["id"]), 2):
            if a["expected"] != b["expected"] or a["expected"]["final_result"] != "pass":
                continue
            ids = (a["candidate"]["id"], b["candidate"]["id"])
            winners = {}
            for run, (first, second) in enumerate([ids, ids[::-1]], start=1):
                call = {"mode": "pairwise", "task_id": task_id, "run": run,
                        "first": first, "second": second,
                        "payload": {"query": tasks_by_id[task_id]["input"]["query"],
                                    "response_a": next(c for c in group if c["candidate"]["id"] == first)["candidate"]["output"],
                                    "response_b": next(c for c in group if c["candidate"]["id"] == second)["candidate"]["output"]}}
                verdict, err = runner.judge(call)
                if err:
                    expect(False, f"pairwise {first} vs {second} run {run}: {err['error']['kind']}")
                    continue
                winners[(first, second)] = first if verdict["verdict"]["preferred"] == "A" else second
            if len(winners) == 2 and len(set(winners.values())) > 1:
                bias = "primacy" if all(w == fs[0] for fs, w in winners.items()) else "order-dependent"
                detect("order_sensitivity",
                       f"{task_id}: {ids[0]} vs {ids[1]} — preference follows presentation order ({bias})")
            outcomes.append({"task_id": task_id, "pair": ids, "winners": winners})
    return outcomes


def evalgen_metrics(results, runs_per_case):
    """EvalGen (Shankar et al. 2024): Coverage = human-flagged-bad outputs the
    judge fails; FFR = human-flagged-good outputs the judge fails; Alignment =
    harmonic mean of Coverage and 1-FFR."""
    per_run = {}
    for run in range(1, runs_per_case + 1):
        rr = [r for r in results if r["run"] == run and not r["incomplete"]]
        bad = [r for r in rr if r["case"]["expected"]["final_result"] == "fail"]
        good = [r for r in rr if r["case"]["expected"]["final_result"] == "pass"]
        cov = sum(r["final"] == "fail" for r in bad) / len(bad) if bad else 0.0
        ffr = sum(r["final"] == "fail" for r in good) / len(good) if good else 0.0
        align = 2 * cov * (1 - ffr) / (cov + (1 - ffr)) if cov + (1 - ffr) else 0.0
        per_run[run] = {"coverage": cov, "ffr": ffr, "alignment": align, "n": len(rr)}
    return per_run


def criterion_agreement(rubric, results):
    rows = []
    for c in rubric["criteria"]:
        cid, veto = c["id"], c["kind"] == "veto"
        pairs = [(r["vetoes"][cid] if veto else r["scores"][cid],
                  r["case"]["expected"]["vetoes" if veto else "scores"][cid])
                 for r in results
                 if not r["incomplete"] and cid in r["case"]["expected"]["vetoes" if veto else "scores"]]
        agree = sum(j == h for j, h in pairs)
        row = {"criterion": cid, "kind": c["kind"], "agreement": agree / len(pairs) if pairs else 0.0}
        if veto:
            trips = [(j, h) for j, h in pairs if h]
            row["veto_recall"] = sum(j for j, _ in trips) / len(trips) if trips else None
        rows.append(row)
    return rows


# ------------------------------------------------------------------- report
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack", type=pathlib.Path)
    ap.add_argument("--runner", help="overrides evalgrill.yaml runner.default")
    args = ap.parse_args()
    pack = args.pack

    manifest, taxonomy, rubric, tasks, cases, protocol = load_pack(pack)
    tasks_by_id = {t["id"]: t for t in tasks}
    runner_name = args.runner or manifest.get("runner", {}).get("default", "replay")
    runner = make_runner(runner_name, pack, manifest)
    runs_per_case = (protocol.get("repeats") or {}).get("runs_per_case", 2)

    # Coverage
    rows = build_coverage(taxonomy, rubric, tasks, cases)
    coverage_path = pack / manifest["artifacts"]["coverage"]
    coverage_path.write_text(yaml.safe_dump({"schema_version": 1, "rows": rows}, sort_keys=False, width=100))

    # Calibration
    results = run_singles(runner, rubric, tasks_by_id, cases, runs_per_case)
    pairwise = run_pairwise(runner, tasks_by_id, cases)
    metrics = evalgen_metrics(results, runs_per_case)
    agreement = criterion_agreement(rubric, results)

    by_ref = defaultdict(list)
    for r in results:
        by_ref[r["ref"]].append(r)
    disagreements = [ref for ref, rs in by_ref.items()
                     if len({r["final"] for r in rs if not r["incomplete"]}) > 1]
    for ref in disagreements:
        finals = ", ".join(f"run {r['run']}: {r['final']}" for r in by_ref[ref])
        detect("judge_disagreement", f"{ref} — runs disagree on final_result ({finals})")

    miscalibrated = [r for r in results if not r["incomplete"]
                     and r["final"] != r["case"]["expected"]["final_result"]]
    for r in miscalibrated:
        detect("calibration_failure",
               f"{r['ref']} run {r['run']} — judge {r['final']}, human label {r['case']['expected']['final_result']}")

    adversarial = [c for c in cases if c["candidate"]["provenance"] == "ADVERSARIAL"]
    gamed, resisted = [], []
    for case in adversarial:
        ref = f"{case['task_id']}/{case['candidate']['id']}"
        judge_passed = [r["run"] for r in by_ref[ref] if r["final"] == "pass"]
        if case["expected"]["final_result"] == "fail" and judge_passed:
            gamed.append(ref)
            detect("reward_hacking",
                   f"{ref} — adversarial candidate passed by judge (runs {judge_passed}) against a human fail label")
        else:
            resisted.append(ref)

    incomplete = [r for r in results if r["incomplete"]]
    for r in incomplete:
        expect(False, f"case {r['ref']} run {r['run']} INCOMPLETE ({r['incomplete']}) — excluded from metrics")

    # Lifecycle
    validation = manifest.get("validation", {})
    verified = (all(t.get("review", {}).get("verified") for t in tasks)
                and all(c.get("review", {}).get("verified") for c in cases))
    veto_ids = [c["id"] for c in rubric["criteria"] if c["kind"] == "veto"]
    veto_cal_ok = all(any(case["expected"]["vetoes"].get(v) for case in cases) for v in veto_ids)
    min_cov = validation.get("minimum_failure_coverage", 0)
    supported = "STRUCTURALLY_VALID"
    if verified:
        supported = "HUMAN_REVIEWED"
    if supported == "HUMAN_REVIEWED" and not incomplete and (veto_cal_ok or not validation.get("require_veto_calibration")):
        supported = "CALIBRATED"
    ready_blockers = [f"coverage gap: {r['failure_mode']} ({', '.join(r['gaps'])})" for r in rows if r["status"] == "gap"]
    ready_blockers += [f"mode {r['failure_mode']} below minimum_failure_coverage {min_cov}"
                       for r in rows if len(r["tasks"]) < min_cov]
    if gamed:
        ready_blockers.append(f"judge gamed by adversarial candidates: {', '.join(gamed)}")
    if miscalibrated or disagreements:
        ready_blockers.append("calibration findings await human review")
    declared = manifest["status"]
    expect(ORDER.index(declared) <= ORDER.index(supported),
           f"status {declared} overstates evidence (supported: {supported})")

    # Escalations (protocol: veto trips, run disagreement, order-sensitive pairs)
    escalations = [f"veto tripped: {r['ref']} run {r['run']} ({v})"
                   for r in results if not r["incomplete"]
                   for v, tripped in r["vetoes"].items() if tripped]
    escalations += [f"run disagreement: {ref}" for ref in disagreements]
    escalations += [f"order-sensitive pair: {d[1]}" for d in detections if d[0] == "order_sensitivity"]

    write_report(pack, manifest, runner_name, runs_per_case, rows, metrics, agreement,
                 detections, escalations, incomplete, declared, supported, ready_blockers,
                 len(cases), len(adversarial), resisted)

    kinds = sorted({k for k, _ in detections})
    print(f"\ndetections: {len(detections)} across kinds {kinds}")
    print(f"wrote {coverage_path} and {pack / 'eval-audit.md'}")
    print("OK: audit complete" if ok else "FAILED: structural faults above")
    sys.exit(0 if ok else 1)


def write_report(pack, manifest, runner_name, runs, rows, metrics, agreement, detections,
                 escalations, incomplete, declared, supported, ready_blockers,
                 n_cases, n_adversarial, resisted):
    pct = lambda x: f"{100 * x:.0f}%"
    L = [f"# Eval audit — {manifest['name']}", "",
         f"Generated by audit_pack.py (runner: {runner_name}). Regenerate; do not hand-edit.", "",
         "## Lifecycle", "",
         f"- Declared status: **{declared}** — evidence supports: **{supported}**"]
    if supported == "CALIBRATED" and declared != "CALIBRATED":
        L.append(f"- Advance `status` to CALIBRATED in evalgrill.yaml (human act, after reviewing this audit).")
    L += ["- READY_FOR_EXPERIMENT blockers:" if ready_blockers else "- No READY_FOR_EXPERIMENT blockers."]
    L += [f"  - {b}" for b in ready_blockers]
    L += ["", "## Coverage", "",
          "| failure mode | severity | tasks | criteria | calibration | status |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        status = f"**gap** ({', '.join(r['gaps'])})" if r["status"] == "gap" else "covered"
        L.append(f"| {r['failure_mode']} | {r['severity']} | {len(r['tasks'])} | "
                 f"{len(r['criteria'])} | {len(r['calibration'])} | {status} |")
    L += ["", "## Calibration", "",
          f"{n_cases} cases × {runs} runs, {n_adversarial} adversarial. "
          "EvalGen metrics (Coverage = human-fails caught, FFR = human-passes wrongly failed, "
          "Alignment = harmonic mean of Coverage and 1−FFR):", "",
          "| run | Coverage | FFR | Alignment | n |", "|---|---|---|---|---|"]
    for run, m in metrics.items():
        L.append(f"| {run} | {pct(m['coverage'])} | {pct(m['ffr'])} | {pct(m['alignment'])} | {m['n']} |")
    L += ["", "Per-criterion agreement with human labels:", "",
          "| criterion | kind | agreement | veto recall |", "|---|---|---|---|"]
    for a in agreement:
        recall = pct(a["veto_recall"]) if a.get("veto_recall") is not None else "—"
        L.append(f"| {a['criterion']} | {a['kind']} | {pct(a['agreement'])} | {recall} |")
    L += ["", "## Findings", ""]
    L += [f"- `{k}` — {msg}" for k, msg in detections] or ["- none"]
    if resisted:
        L += ["", f"Adversarial candidates the judge correctly failed: {', '.join(resisted)}."]
    if incomplete:
        L += ["", "## Incomplete (excluded from metrics)", ""]
        L += [f"- {r['ref']} run {r['run']}: {r['incomplete']}" for r in incomplete]
    L += ["", "## Human review queue", ""]
    L += [f"- [ ] {e}" for e in escalations] or ["- empty"]
    L.append("")
    (pack / "eval-audit.md").write_text("\n".join(L))


if __name__ == "__main__":
    main()
