---
description: Second EvalGrill phase — turns the analyzed failure taxonomy plus task material (briefs, real tasks, sources) into dataset.jsonl + dataset-card.md, tasks engineered to expose the failure modes. Use after analyze-eval-problem, when the user has tasks or briefs to formalize, or before design-eval-rubric.
---

# build-eval-dataset

Build tasks that **expose** the taxonomy's failure modes, not plausible prompts. Every field is either agent-visible or judge-side; keeping that line sharp is most of this skill's job.

Reads `failure-taxonomy.yaml` + `evaluation-dimensions.yaml` from the EvalPack directory (run **analyze-eval-problem** first). Writes:

| File | Contents |
|---|---|
| `dataset.jsonl` | One task per line — schema `${CLAUDE_PLUGIN_ROOT}/schemas/task.schema.json` |
| `dataset-card.md` | What the dataset contains: counts, coverage map, audit, review status |

## Steps

### 1. Gather task material

Collect what exists: real user tasks, informal briefs, production traces, benchmark examples, source documents, domain docs. Real material beats invention — read all of it in full. Copy any documents tasks will reference **into the pack** (e.g. `sources/`): a pack is self-contained, and `input.context` paths are pack-root-relative and must resolve inside it.

### 2. Plan the slate

Decide the task list before authoring any single task:

- **Regression first** — each known failed output becomes a task recreating its conditions.
- **Failure coverage** — every high-severity mode gets at least one task engineered to tempt it. A task *targets* a mode only if its materials actually create the conditions for that mode to fire — a conflict to miss, a correction to ignore, bait to cite. Listing a mode the task merely *could* exhibit is noise.
- **Boundary cases and counterexamples** — tasks where superficially similar outputs have different correct behavior; cases built to break naive heuristics.
- **Clean cases** — ordinary tasks with no planted trap (`failure_targets` empty) so the eval doesn't over-optimize for failure scenarios.
- **Difficulty tiers** — spread across easy / medium / hard.

Leave uncoverable modes visible — the validate phase audits severity-vs-coverage; don't force weak tasks into existence.

### 3. Author each task

Field discipline, per the schema:

- **`input` is the only agent-visible field.** The payload given to the system under test equals `input` exactly (contract-tested). Anything the agent must be told — the question, the documents, real constraints like word limits — lives inside `input`; everything else is judge-side. Litmus: would telling the agent change its behavior or give away the trap? Then it's judge-side.
- **`failure_targets`** — taxonomy ids this task is engineered to expose, at step 2's bar. Empty or absent for clean cases.
- **`grading_constraints`** — judge-side expectations as short snake_case phrases (`correction_notice_must_be_applied`). State what grading hinges on; never restate the task.
- **`reference`** — `required_observations`: facts in the materials a competent answer must engage; `acceptable_outcomes`: **every** defensible conclusion, not one golden path. Judge outcomes, never a reference trajectory — several valid answers means several entries.
- **`metadata`** — `category`: scenario type, snake_case (`conflicting_sources`, `claim_verification`, `missing_evidence`, …); `difficulty`: easy = single-source reading, medium = cross-source reasoning, hard = judgment under conflict or uncertainty (calibrate to the domain); `risk`: blast radius of a wrong answer for whoever consumes it downstream.
- **`provenance` honesty** — `REAL`: an actual production task, verbatim. `DERIVED`: adapted from real material. `SYNTHETIC`: invented. `ADVERSARIAL`: invented specifically to bait a failure. Never upgrade; in doubt, take the humbler label.
- **`solvable`** — assert only after answering the task yourself from `input` alone. Required info missing, or ambiguity you didn't intend → fix the task, or mark `solvable: false` deliberately (unanswerable-by-design is a legitimate category).
- **`review`** — authored output ships `verified: false`. Only a human flips it (adding `reviewer` + `reviewed_at`) after reviewing the task. Never self-verify.

### 4. Write the dataset card

`dataset-card.md` — the human-readable account of the dataset:

- **Counts** — tasks by difficulty, category, provenance; clean vs failure-targeted.
- **Coverage map** — failure mode → targeting task ids, with **uncovered modes listed explicitly**.
- **Audit** — answer each: all tasks solvable? required info present in `input`? accidental ambiguity? tiers balanced? high-severity modes covered? redundant tasks? easy-case overrepresentation? could any task reward a shortcut? does any `reference` demand one path where several are valid?
- **Review status** — how many tasks human-verified.

An audit answer that indicts a task: fix the task now, then re-answer.

### 5. Self-check

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/check_dataset.py" <pack-dir>
```

Fix and re-run until it prints `OK`.

### 6. Hand off

Report: the slate shape, the coverage map with its gaps, audit flags, and that tasks await human review (`verified: false` until the user flips them). Next phase: **design-eval-rubric** turns the taxonomy + dataset into criteria in the same pack directory.
