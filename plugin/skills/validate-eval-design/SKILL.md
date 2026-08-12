---
description: Fourth EvalGrill phase — audits an EvalPack before anything trusts its scores. Coverage gaps, rubric defects, judge calibration with EvalGen metrics, reward-hacking probes, lifecycle status. Use after design-eval-rubric, when the user asks to validate/calibrate/audit an eval, or before export.
---

# validate-eval-design

The detection engine: proves the eval catches what it claims. Every detection is deterministic script output; this skill's judgment work is reading the findings and driving the human decisions they demand — it never softens a finding to make the pack look done.

Writes `coverage-matrix.yaml` and `eval-audit.md` (both generated — regenerate, never hand-edit), refreshes the escalation section of `human-review-guide.md`, and leaves `evalgrill.yaml`'s `status` defensible.

## Steps

### 1. Structural gate

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/check_pack.py" <pack-dir>
```

Schemas, cross-references, grounding (a `known failed output: task/candidate` provenance pointer must resolve to a committed calibration case). Fix and re-run until `OK` — the audit assumes a sound pack.

### 2. Rubric audit

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/check_rubric.py" <pack-dir> [rubric-file]
```

Run it on `rubric.yaml` and on any earlier draft the user kept — defects caught on a draft the human already fixed are still evidence the eval process works. Three defect tags:

| Tag | Defect | Fix |
|---|---|---|
| `[vague_criterion]` | anchors grade enthusiasm, not behavior | rewrite each level as behavior a reader can point at, or drop the criterion and log the drop |
| `[hidden_deterministic]` | mechanically checkable criterion routed to a fallible judge (FR-8) | set `deterministic: true`; judgment residue stays the secondary method |
| `[missing_veto]` | calibration expects a veto the rubric weights or lacks | restore the veto — partial credit on a zero-tolerance rule lets disqualifying failures survive aggregation |

### 3. Coverage + calibration

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/audit_pack.py" <pack-dir> [--runner NAME]
```

One command generates both artifacts. Coverage: one row per failure mode — the tasks that target it, the criteria that detect it, the calibration cases whose human labels show it firing. Calibration: every case × every run × every criterion through the Judge Runner seam (one criterion, or one presentation order of a pair, per Judge Call), then EvalGen metrics — **Coverage** (human-flagged failures the judge catches), **FFR** (human passes wrongly failed), **Alignment** (harmonic mean of Coverage and 1−FFR) — plus per-criterion agreement and veto recall.

Runner comes from `evalgrill.yaml`'s `runner:` block; `--runner` overrides. Two runners: `replay` (the Scripted Judge replaying `runner.replay_fixture`; a missing line is a loud `replay_miss`, never a fabricated verdict) and `claude-cli` (live `claude -p` per ADR-0001 — pinned `runner.model`, caller-enforced `runner.timeout_s`, subscription auth preflight; a live sweep costs one judge call per case × run × criterion, so quote the count before running). `FAIL` lines are structural faults in the pack or fixture — fix them; `DETECT` lines are the product working.

### 4. Read the findings

Each `DETECT` kind demands a human decision — surface them, don't dispatch them yourself:

| Kind | Meaning | Decision it demands |
|---|---|---|
| `coverage_gap` | a mode no task exercises, no criterion detects, or no case grounds | add tasks/criteria targeting it, or record why it stays uncovered |
| `judge_disagreement` | repeat runs flip final_result on one case | tighten the deciding criterion's anchors, or accept the case as judge-hard and keep it escalated |
| `order_sensitivity` | pairwise preference follows presentation order | keep order swap mandatory; treat single-order rankings from this judge as unreliable |
| `calibration_failure` | judge contradicts a human label | fix the rubric wording the judge misread — or the label, if the human was wrong; then re-run |
| `reward_hacking` | an adversarial candidate games the judge | harden the criterion against surface compliance (the audit names which candidate's trick worked) |

Metrics are reported as evidence, never asserted as thresholds, in v0.1 (ADR-0002). When Alignment is low, say which side: missed failures (low Coverage) or good outputs punished (high FFR).

### 5. Settle the lifecycle

| Status | Evidence required |
|---|---|
| STRUCTURALLY_VALID | step 1 green |
| HUMAN_REVIEWED | every task and calibration case `review.verified` |
| CALIBRATED | calibration complete (no INCOMPLETE cases), every veto criterion exercised by an expected trip |
| READY_FOR_EXPERIMENT | no coverage gaps, `minimum_failure_coverage` met, audit findings dispatched by a human |

The audit FAILs a declared status that overstates the evidence and says what the evidence supports; it never edits the manifest. Advancing `status` is the human's act, recorded after they review the audit.

### 6. Refresh the review guide

Replace the review guide's calibration-escalation section with the audit's **Human review queue** (veto trips, run disagreements, order-sensitive pairs — per the protocol's escalation rules), so the guide stays the single place a reviewer works from.

### 7. Hand off

Report: detections by kind, EvalGen metrics per run, lifecycle verdict with blockers. The pack is now what the exporters consume — canonical artifacts unchanged, audit riding alongside.
