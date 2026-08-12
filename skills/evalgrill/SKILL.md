---
description: EvalGrill entry point — reports EvalPack status and routes to the right phase skill (analyze, dataset, rubric, validate).
argument-hint: "[analyze|dataset|rubric|validate] [pack-dir]"
disable-model-invocation: true
---

# evalgrill (router)

Thin dispatcher. Methodology lives in the four phase skills; this skill locates the pack, reads its state, and routes — nothing else.

## 1. Locate the pack

Take the pack dir from the arguments when given. Otherwise glob `**/evalgrill.yaml` and `**/failure-taxonomy.yaml` (early packs have no manifest yet) from the working directory:

- one pack → use its directory
- several → ask the user which
- none → new eval; recommend `analyze`, which creates the directory

## 2. Read the state

File presence in the pack dir decides the stage; when `evalgrill.yaml` exists, read `status` and `remaining_requirements` too. Run no scripts — the phase skills own their checks.

| Phase complete | Evidence |
|---|---|
| analyze | `failure-taxonomy.yaml` + `evaluation-dimensions.yaml` |
| dataset | `dataset.jsonl` |
| rubric | `rubric.yaml` + `judge-protocol.yaml` |
| validate | `eval-audit.md` + `coverage-matrix.yaml`, generated after the latest edit to any artifact above |

## 3. Route

Subcommand named → invoke that skill, passing the pack dir as args. When the named phase's inputs are missing (e.g. `rubric` with no `dataset.jsonl`), say so and let the user proceed or redirect — their call.

| Subcommand | Skill |
|---|---|
| `analyze` | `analyze-eval-problem` |
| `dataset` | `build-eval-dataset` |
| `rubric` | `design-eval-rubric` |
| `validate` | `validate-eval-design` |

No subcommand → report and recommend, never auto-run:

```text
EvalGrill: <pack name>    status: <status, or "no manifest yet">

✓ Problem analyzed
✓ Dataset created
✗ Rubric not designed
✗ Eval not validated

Next: /evalgrill rubric
```

The recommendation is the first incomplete phase. All four complete → the next step is status-aware:

- `DRAFT` / `STRUCTURALLY_VALID`, or artifacts edited since the audit → `/evalgrill validate`
- `HUMAN_REVIEWED` / `CALIBRATED` → surface `remaining_requirements`; what remains is human acts (review sign-offs, advancing `status`) — the human edits the manifest, never you
- `READY_FOR_EXPERIMENT` → the pack is done; exporters consume it as-is
