---
description: First EvalGrill phase — turns evidence about an AI agent (description, failed outputs, complaints, domain rules, traces) into a grounded failure taxonomy and evaluation dimensions. Use when starting an eval design, when the user has agent failures to formalize, or before build-eval-dataset / design-eval-rubric.
---

# analyze-eval-problem

Convert vague notions of quality into observable failure modes and evaluation dimensions. Work **failure-first**: every mode starts from evidence of something actually going wrong — never from a generic quality checklist.

Writes three files into the EvalPack directory (ask the user where the pack lives; create the directory for a new eval):

| File | Contents |
|---|---|
| `eval-problem.md` | Analysis narrative: evidence inventory, user outcome, observable success, suspected-but-ungrounded failures |
| `failure-taxonomy.yaml` | Failure modes — schema `${CLAUDE_PLUGIN_ROOT}/schemas/failure-taxonomy.schema.json` |
| `evaluation-dimensions.yaml` | Dimensions grouping the modes — schema `${CLAUDE_PLUGIN_ROOT}/schemas/evaluation-dimensions.schema.json` |

## Steps

### 1. Inventory the evidence

Collect whatever the user can provide — no single input is required: product/agent description, agent instructions, real user tasks, failed outputs, production traces, user complaints, expert guidelines, domain rules, existing metrics, known good/bad examples.

Read every provided material in full, including files they reference. List each piece in `eval-problem.md` with a short stable label — `failed output: <task>/<candidate>`, `domain rule 3`, `complaint 2026-03-04`, `expert guideline: <who>`. This inventory is the complete provenance vocabulary for step 3: a failure mode may cite only labels that appear here.

### 2. Pin outcome and success

In `eval-problem.md`:

- **User outcome** — what the user is actually trying to accomplish (the job the output does for them, not the agent's mechanics).
- **Observable success** — what evidence *in the output* would show the task succeeded.

### 3. Extract failure modes

Walk the inventory piece by piece: for each failed output, complaint, rule, or guideline, name the specific observable way the system goes wrong. Then merge across evidence into distinct modes — two modes a judge could not tell apart by their observable signals are one mode.

Each mode in `failure-taxonomy.yaml` carries:

- `id` — bare snake_case.
- `description` — the observable way it goes wrong: what a reader of the output plus the task materials can see, never a mental state.
- `severity` — `critical`: causes harm, blocks deployment; `high`: output unacceptable on its own (typically a violated zero-tolerance rule); `medium`: materially degrades trust or usefulness; `low`: polish.
- `frequency` — only what the evidence supports (`common`/`occasional`/`rare`); otherwise `unknown` or omit.
- `location` — where it occurs: `final_output`, `evidence`, `reasoning`, `tool_usage`, `communication`, `environment`, `safety`.
- `observable_signals` — concrete things a judge or script can look for in the candidate and task materials.
- `evaluation_method` — deterministic before rubric before human_review: if a script could check it, `primary: deterministic` even when a rubric backstops it as `secondary`.
- `provenance` — one or more pointers quoting step-1 inventory labels, each naming what that evidence showed.

**Grounding gate** (the anti-generic rule): a mode enters the taxonomy only with provenance from the inventory. Any inventoried evidence qualifies — an observed failure is the strongest grounding; rules, guidelines, and requirements also count, and the provenance pointer shows which kind backs the mode. A mode you cannot ground stays out — record it in `eval-problem.md` under *Suspected, ungrounded* instead, so a later phase with more evidence can promote it. Fewer grounded modes beat a plausible checklist.

### 4. Derive dimensions

Group the modes into `evaluation-dimensions.yaml` — the measurable quality aspects a rubric will later score. Each dimension: `id`, `description` (what *good* looks like, judge-facing), `failure_modes` (the modes it detects). Every failure mode belongs to at least one dimension; aim for a handful of dimensions, not one per mode.

### 5. Self-check

```bash
uv run "${CLAUDE_PLUGIN_ROOT}/scripts/check_analysis.py" <pack-dir>
```

Fix and re-run until it prints `OK`.

### 6. Hand off

Report to the user: the modes found, which are highest-severity, and anything left in *Suspected, ungrounded*. Next phase: **build-eval-dataset** writes tasks targeting these failure modes into the same pack directory. Leave coverage gaps visible — the validate phase audits severity-vs-coverage; tasks are not forced now.
