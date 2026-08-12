---
status: accepted
---

# Deterministic acceptance fixtures: golden EvalPack + scripted judge; live LLM paths are dogfood

The §30 acceptance bar (all seven detections, demonstrated on the Demo Corpus) is asserted against hand-authored, committed fixtures — never against what an LLM happens to generate on a given run. The Demo Corpus ships a **golden EvalPack** (taxonomy, dataset, dimensions, calibration set, judge protocol, and a clean canonical `rubric.yaml`; the taxonomy plants a coverage gap via a high-severity failure mode with zero task coverage), a **deliberately flawed draft rubric** in `fixtures/` (planting a vague criterion, a mechanically-checkable criterion scored by LLM, and a veto-worthy failure expressed as a weighted criterion), plus a **scripted JudgeRunner fixture** that replays committed verdicts exhibiting the planted judge disagreement, pairwise order bias, and calibration failure. Every §30 detection therefore fires deterministically in CI. The generative skill path (analyze → dataset → rubric via LLM) and live `claude -p` judge runs execute against the same corpus as dogfood evidence, but no done-bar depends on an LLM reproducing a defect or failing in a particular way, and generation runs are never cherry-picked.

## Consequences

- The Judge Runner interface must treat a scripted/replay runner as a first-class implementation and record verdict source (live vs. replay) in its output envelope.
- The golden pack is hand-maintained: schema changes require updating fixtures by hand, enforced by the same validate script users run.
- Dogfood runs can drift from fixture behavior without breaking CI; drift is signal about generation quality, reviewed manually, not a build failure.
- Judge-behavior metrics from live calibration (agreement, order consistency, veto recall) are reported as evidence, not asserted as thresholds, in v0.1.
