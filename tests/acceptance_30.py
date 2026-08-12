# /// script
# requires-python = ">=3.10"
# ///
"""The PRD §30 acceptance run (ADR-0002): the v0.1 done-bar, asserted.

Usage: uv run tests/acceptance_30.py

Everything asserted here is deterministic: committed golden pack, committed
fixtures, scripted (replay) judge. It asserts, in order:

1. structural gate: check_pack.py green on demo/golden-pack
2. golden rubric clean: check_rubric.py green
3. the three planted rubric defects fire on fixtures/draft-rubric.yaml
   (FAIL [vague_criterion] / [hidden_deterministic] / [missing_veto])
4. the four audit detections fire under the replay runner
   (DETECT coverage_gap / judge_disagreement / order_sensitivity /
   calibration_failure), each on its planted target
5. the full §30 artifact list exists after the run
6. all three exporters produce their export trees
7. exporting did not modify the canonical dataset or rubric

Live claude-cli calibration and generative skill runs are dogfood evidence,
reported in the map tickets and never asserted here (ADR-0002).
"""
import hashlib
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PACK = ROOT / "demo" / "golden-pack"
SCRIPTS = ROOT / "scripts"

ARTIFACTS = [  # PRD §30 "EvalGrill must produce"
    "failure-taxonomy.yaml", "evaluation-dimensions.yaml", "dataset.jsonl",
    "dataset-card.md", "rubric.yaml", "judge-protocol.yaml",
    "coverage-matrix.yaml", "calibration.jsonl", "human-review-guide.md",
    "eval-audit.md",
]

# §30 detection -> (pattern over the relevant command's output, plant id)
RUBRIC_DEFECTS = [
    r"FAIL \[vague_criterion\].*report_quality",
    r"FAIL \[hidden_deterministic\].*quantitative_claims_sourced",
    r"FAIL \[missing_veto\].*cites_only_provided_sources",
]
AUDIT_DETECTIONS = [
    r"DETECT coverage_gap: misattributed_quote",
    r"DETECT judge_disagreement: .*fluent-conflict-gloss",
    r"DETECT order_sensitivity: .*near-tie",
    r"DETECT calibration_failure: .*citation-stuffing",
]

failed = []


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        failed.append(what)


def run(script, *args):
    p = subprocess.run(["uv", "run", str(SCRIPTS / script), *args],
                       capture_output=True, text=True, cwd=ROOT)
    return p.returncode, p.stdout + p.stderr


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


canonical = {f: sha(PACK / f) for f in ("dataset.jsonl", "rubric.yaml")}

code, _ = run("check_pack.py", str(PACK))
check(code == 0, "structural gate: check_pack green")

code, _ = run("check_rubric.py", str(PACK))
check(code == 0, "golden rubric: check_rubric green")

code, out = run("check_rubric.py", str(PACK), "fixtures/draft-rubric.yaml")
check(code == 1, "draft rubric: check_rubric fails as planted")
for pat in RUBRIC_DEFECTS:
    check(re.search(pat, out) is not None, f"detection: {pat}")

code, out = run("audit_pack.py", str(PACK), "--runner", "replay")
check(code == 0, "replay audit: no structural faults")
for pat in AUDIT_DETECTIONS:
    check(re.search(pat, out) is not None, f"detection: {pat}")

for f in ARTIFACTS:
    check((PACK / f).exists(), f"artifact: {f}")

for platform in ("braintrust", "langsmith", "phoenix"):
    code, _ = run(f"export_{platform}.py", str(PACK))
    check(code == 0, f"export: {platform} exporter green")
    for f in ("eval_pack.py", "pack_data.json", "requirements.txt"):
        check((PACK / "exports" / platform / f).exists(),
              f"export: {platform}/{f}")

for f, digest in canonical.items():
    check(sha(PACK / f) == digest, f"canonical pack untouched: {f}")

print()
print("dogfood evidence (reported, never asserted; ADR-0002): live claude-cli")
print("calibration sweep in map ticket #23; generative analyze/dataset/rubric")
print("runs in map tickets #15-#17.")
print()
if failed:
    print(f"FAILED: {len(failed)} assertion(s) above")
    sys.exit(1)
print("OK: PRD §30 acceptance run green (7/7 detections, "
      f"{len(ARTIFACTS)} artifacts, 3 exports)")
