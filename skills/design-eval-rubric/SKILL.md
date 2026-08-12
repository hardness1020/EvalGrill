---
description: Third EvalGrill phase — turns the failure taxonomy + evaluation dimensions into rubric.yaml (criteria with observable anchors, vetoes, deterministic flags), judge-protocol.yaml, and human-review-guide.md. Use after build-eval-dataset, when the user has failure modes to score, or before validate-eval-design.
---

# design-eval-rubric

Convert failure modes into **independently checkable** criteria. Every criterion names the modes it detects, anchors every level in observable behavior, and admits when a script could check it instead of a judge.

Reads `failure-taxonomy.yaml` + `evaluation-dimensions.yaml` (and `dataset.jsonl` for what evidence tasks actually provide) from the EvalPack directory (run **analyze-eval-problem** and **build-eval-dataset** first). Writes:

| File | Contents |
|---|---|
| `rubric.yaml` | Criteria — schema `${CLAUDE_PLUGIN_ROOT}/schemas/rubric.schema.json` |
| `judge-protocol.yaml` | How any judge runs this rubric: anonymization, evidence, rationale, repeats, aggregation, escalation |
| `human-review-guide.md` | What a human checks before trusting the rubric |

## Steps

### 1. Gather inputs

Read the taxonomy, dimensions, and dataset in full, plus the domain rules and expert guidelines the analyze phase inventoried — rules are where vetoes and importance come from. Criteria may only cite evidence a judge will actually hold (`task.input.*`, `candidate.output`, `task.grading_constraints`).

### 2. Plan the criteria list

Decide the mode → criterion map before authoring any single criterion:

- **Traceability** — each criterion lists the taxonomy ids it detects in `failure_modes`; every mode lands in at least one criterion or is left visibly uncovered for the validate phase's coverage audit. A criterion traceable to no mode is a generic-checklist entry and stays out.
- **One judgment per criterion** — merge modes a judge scores as one question (e.g. both directions of miscalibration); split where observability differs (string-matchable vs judgment).
- **Kind selection**:
  - `veto` for zero-tolerance rules — the output is unacceptable regardless of other merits. A scale on a zero-tolerance rule is the **missing-veto** anti-pattern: partial credit lets a disqualifying failure survive aggregation. Vetoes carry no scale or importance; `layer: veto`.
  - `binary` when the question has exactly two observable states.
  - `ordinal` only when the middle levels are genuinely distinct behaviors, not degrees of enthusiasm.
- **Layer** — where the judge looks: `outcome` (result satisfies the objective), `evidence` (valid sources and process), `communication` (conclusions, limitations, uncertainty). The taxonomy's `location` is the hint.

### 3. Author each criterion

- **Observable anchors** — every scale level describes something a reader of the output plus task materials can point at; level 0 is the failure mode firing, the top level its observable absence. Litmus: two judges disagreeing on a level settle it by pointing at text. "Poor / acceptable / excellent" and words like *quality, insightful, thorough, deep, expertise* mark the **vague-criterion** anti-pattern — convert to observable behavior, or drop the criterion and log the drop in the review guide.
- **`deterministic` honesty (FR-8)** — `true` when a script could decide it from pack contents (citations string-matched against the packet, numbers located in sources, word counts). Taxonomy `evaluation_method.primary: deterministic` means the criterion is `deterministic: true`; marking it `false` hides a cheap mechanical check behind a fallible judge (the **hidden-deterministic** anti-pattern). Judgment residue — paraphrase, framing — stays with the judge as the taxonomy's secondary method; say so in a comment.
- **Importance triage** — `essential`: level 0 on this criterion alone makes the output unusable (aggregation fails it); `important`: materially degrades trust; `desirable`: polish. Severity is the hint (critical/high → veto or essential). An all-essential rubric means aggregation can't rank — triage honestly and surface the skew in the review guide.
- **`why_it_matters`** — the downstream consequence, never a restatement of the description.

### 4. Write the judge protocol

`judge-protocol.yaml` is **pure protocol**, portable to any platform. Runner selection (model pin, timeout, replay fixture) lives in `evalgrill.yaml`'s `runner:` block, never here (ADR-0001). Defaults, each overridable with a stated reason:

- `anonymization` — the judge never sees candidate ids or provenance labels.
- `evidence_per_call` — exactly what the judge holds: the task input, the single criterion under evaluation with its anchors. `grading_constraints` go to the judge, never to the agent.
- `rationale` — required, per criterion; one criterion per call, no omnibus scoring.
- `repeats` — ≥2 runs per case; run disagreement is a calibration signal, not noise.
- `pairwise` — order swap on, positions anonymized.
- `aggregation` — the final_result rule, stated: any tripped veto → fail; any essential criterion at level 0 → fail; otherwise pass.
- `escalation` — tripped vetoes, run disagreement, and order-sensitive preferences go to human review.

### 5. Write the review guide

`human-review-guide.md` — what a human does before the rubric is trusted:

- **Criteria table** — id, kind, layer, importance, modes, deterministic flag.
- **Spot-check protocol** — grade 2–3 known outputs (calibration candidates when present, otherwise the inventoried failed outputs) per criterion by hand; where your judgment and an anchor disagree, the anchor is the defect.
- **Veto confirmation** — each veto with the zero-tolerance rule it encodes; each high-severity mode deliberately left weighted, with why.
- **Deterministic ledger** — criteria flagged `deterministic: true`; the validate phase owes these scripts.
- **Drops log** — rules or criteria generated then dropped or narrowed, with why.
- **Status** — the pack stays DRAFT until a human signs off.

### 6. Self-check

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/check_rubric.py" <pack-dir>
```

Fix and re-run until it prints `OK`. It also vets a candidate rubric file: `check_rubric.py <pack-dir> <rubric-file>`.

### 7. Hand off

Report: criteria by kind, the mode → criterion map with uncovered modes, each veto and the rule it encodes, deterministic flags, drops. The rubric awaits human review via the guide. Next phase: **validate-eval-design** audits coverage and runs judge calibration in the same pack directory.
