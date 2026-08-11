# LangSmith export contract (golden path)

Research for EvalGrill's LangSmith exporter and live smoke test. All claims cite primary sources: the official LangSmith docs and the `langsmith` / `openevals` SDK sources. Researched 2026-08-10.

**Docs domain note.** `https://docs.smith.langchain.com/` now issues a `308 Permanent Redirect` to `https://docs.langchain.com/langsmith` (verified by direct fetch, 2026-08-10). All doc citations below use the new domain. Every docs page is also served as raw markdown by appending `.md` to the URL, and the full index lives at <https://docs.langchain.com/llms.txt> — useful for keeping this contract fresh programmatically.

---

## 1. Packages and versions (as of 2026-08-10)

| Package | Version | Requires | Source |
|---|---|---|---|
| `langsmith` (Python SDK) | **0.10.17** (released 2026-08-07) | Python `>=3.10`; httpx, pydantic v2, orjson, requests | <https://pypi.org/pypi/langsmith/json> |
| `openevals` (prebuilt/LLM-judge evaluators, by langchain-ai) | **0.2.0** | Python `>=3.10`; `langsmith>=0.3.32`, `langchain>=0.3.18`, `langchain-openai>=0.3.6` | <https://pypi.org/pypi/openevals/json> |

- Install: `pip install langsmith` ([create-account-api-key](https://docs.langchain.com/langsmith/create-account-api-key)); the eval quickstart uses `pip install -U langsmith openevals openai` ([evaluation-quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart)).
- Note `openevals` hard-depends on `langchain` + `langchain-openai`. A judge on a non-OpenAI provider needs the matching `langchain-<provider>` package or a pre-initialized client passed as `judge=` ([openevals README](https://github.com/langchain-ai/openevals#customizing-the-model)).
- Python SDK API reference root: <https://reference.langchain.com/python/langsmith/> (linked from the docs).
- **Version-sensitive**: multi-score list returns require `langsmith>=0.2.0` ([multiple-scores](https://docs.langchain.com/langsmith/multiple-scores)); passing openevals evaluators directly into `evaluate` requires `langsmith>=0.3.11` ([openevals docs page](https://docs.langchain.com/langsmith/openevals)); the new SmithDB-backed query methods require `langsmith>=0.10.15` ([smithdb-sdk-migration](https://docs.langchain.com/langsmith/smithdb-sdk-migration)).

## 2. Auth, workspaces, projects

Source: [create-account-api-key](https://docs.langchain.com/langsmith/create-account-api-key), [administration-overview](https://docs.langchain.com/langsmith/administration-overview).

- **Two API key types**: Personal Access Tokens (PATs, inherit the creating user's permissions — "for personal scripts") and **Service keys** (scoped to specific workspaces or the whole org — "for applications and production services"). For CI, use a workspace-scoped service key. Keys are created at <https://smith.langchain.com/settings> → API Keys, shown once, with optional expiration.
- **Env vars the SDK reads**:
  - `LANGSMITH_API_KEY` (required)
  - `LANGSMITH_TRACING=true` (enables tracing; not strictly required just to run `evaluate`, but the quickstart sets it)
  - `LANGSMITH_ENDPOINT` — defaults to `https://api.smith.langchain.com` (GCP US). Regional SaaS: `https://eu.api.smith.langchain.com`, `https://apac.api.smith.langchain.com`, `https://aws.api.smith.langchain.com`
  - `LANGSMITH_WORKSPACE_ID` — required only if the key is scoped to more than one workspace
- **Hierarchy**: Organization → Workspace (formerly "Tenant"; trust/access boundary; datasets, experiments, API keys, tracing projects all live at workspace scope) → optional Applications (resource-tag grouping) → Resources ([administration-overview](https://docs.langchain.com/langsmith/administration-overview)).
- **"Project" vs "experiment"**: tracing projects and experiments are the same backend structure, called a *session* ([fetch-perf-metrics-experiment](https://docs.langchain.com/langsmith/fetch-perf-metrics-experiment)). That's why experiment stats are read with `client.read_project(...)`.
- `Client()` with no args picks all of this up from env ([evaluation-quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart)).

## 3. Create a dataset with examples — exact SDK calls

Source: [manage-datasets-programmatically](https://docs.langchain.com/langsmith/manage-datasets-programmatically), [evaluation-quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart).

```python
from langsmith import Client

client = Client()
dataset = client.create_dataset(
    dataset_name="my-eval",
    description="...",
)
client.create_examples(
    dataset_id=dataset.id,
    examples=[
        {
            "inputs": {"question": "..."},          # arbitrary JSON dict
            "outputs": {"answer": "..."},           # reference outputs, arbitrary JSON dict
            "metadata": {"source": "Wikipedia"},    # arbitrary per-example metadata dict
        },
        ...
    ],
)
```

- Bulk `create_examples` is recommended for many examples; `create_example` (singular) for one ([manage-datasets-programmatically](https://docs.langchain.com/langsmith/manage-datasets-programmatically)).
- **Splits**: per the SDK source, each example dict passed to `create_examples` may include `"split": str | list[str]` at creation time (`ExampleCreate.split: Optional[Union[str, list[str]]]`, [schemas.py](https://github.com/langchain-ai/langsmith-sdk/blob/main/python/langsmith/schemas.py)); examples can also be (re)assigned later via `client.update_example(example_id=..., split="train")` or `client.update_examples(example_ids=[...], splits=[["training","foo"], "training"])`. Splits are for high-level grouping; metadata is for per-example info like tags and provenance ([manage-datasets-programmatically](https://docs.langchain.com/langsmith/manage-datasets-programmatically), [evaluation-concepts](https://docs.langchain.com/langsmith/evaluation-concepts)). LangSmith explicitly allows one example in multiple splits.
- **Read back / filter**: `client.list_examples(dataset_name=...)`, `client.list_examples(dataset_name=..., metadata={"foo": "bar"})`, or a filter DSL: `client.list_examples(dataset_name=..., filter='and(not(has(metadata, \'{"foo": "bar"}\')), exists(metadata, "tenant_id"))')` ([manage-datasets-programmatically](https://docs.langchain.com/langsmith/manage-datasets-programmatically)).
- Datasets have **indefinite retention** — unlike traces ([usage-and-billing](https://docs.langchain.com/langsmith/usage-and-billing)).
- Cleanup for smoke tests: `client.delete_dataset(dataset_id=...)` or `dataset_name=` ([SDK reference](https://reference.langchain.com/python/langsmith/client/Client/delete_dataset)).

## 4. Evaluators: custom functions, openevals, prebuilts

### 4.1 Custom code evaluator functions (the flexible primitive)

Source: [code-evaluator-sdk](https://docs.langchain.com/langsmith/code-evaluator-sdk).

A plain Python function passed to `evaluate()`. **Argument names are significant** — any subset of: `run: Run`, `example: Example`, `inputs: dict`, `outputs: dict`, `reference_outputs: dict`.

Return types (Python):
- `int | float | bool` → continuous metric, function name becomes the metric name
- `str` → categorical metric
- `dict` of the form `{"key": ..., "score": ...}` (numerical) or `{"key": ..., "value": ...}` (categorical)
- `list[dict]` → **multiple metrics from one function** (requires `langsmith>=0.2.0`), e.g. `[{"key": "precision", "score": 0.8}, {"key": "grade", "value": "B"}]` ([multiple-scores](https://docs.langchain.com/langsmith/multiple-scores))

Each dict may carry any [feedback field](https://docs.langchain.com/langsmith/feedback-data-format), notably `comment` (score justification).

### 4.2 LLM-as-judge

Two doc-sanctioned routes:

1. **Roll your own** inside a custom evaluator function — call any LLM (structured output recommended), return a score ([llm-as-judge-sdk](https://docs.langchain.com/langsmith/llm-as-judge-sdk)).
2. **openevals** `create_llm_as_judge` ([openevals docs page](https://docs.langchain.com/langsmith/openevals), [openevals README](https://github.com/langchain-ai/openevals)):

```python
from openevals.llm import create_llm_as_judge

judge = create_llm_as_judge(
    prompt=RUBRIC_PROMPT,          # f-string with {inputs}, {outputs}, {reference_outputs} (+ extra kwargs)
    feedback_key="contradiction_handling",  # becomes the LangSmith feedback key
    model="openai:o3-mini",        # "provider:model" string, or pass judge=<client>
    choices=[0.0, 0.5, 1.0],       # restrict score to specific floats (mutually exclusive with continuous=True)
    # continuous=True,             # float in [0,1] instead of binary
    # use_reasoning=False,         # disable the judge's justification comment
    # few_shot_examples=[{"inputs":..., "outputs":..., "reasoning":..., "score":...}],
    # system=..., output_schema=...,
)
```

Key facts from the README (primary SDK source, v0.2.0):
- Default output is `{"key": <feedback_key>, "score": bool, "comment": <reasoning>}`.
- `continuous` and `choices` are **mutually exclusive**; `choices` is a **list of floats**. "You should make sure that your prompt is grounded in information on what specific scores mean — the prebuilt ones in this repo do not have this information."
- `output_schema` changes the return shape entirely (useful for one call emitting multiple criteria, but then *you* must adapt it back to LangSmith feedback dicts).
- Prebuilt prompts exist (`CORRECTNESS_PROMPT`, `CONCISENESS_PROMPT`, RAG groundedness, etc.) but are binary-oriented starting points.

3. There are also **platform-managed evaluators** (bound to datasets in the UI/SDK, run server-side: [evaluators](https://docs.langchain.com/langsmith/evaluators), [manage-evaluators-sdk](https://docs.langchain.com/langsmith/manage-evaluators-sdk), [bind-evaluator-to-dataset](https://docs.langchain.com/langsmith/bind-evaluator-to-dataset)). For an exporter whose contract is "generated code in `exports/langsmith/`", client-side evaluator functions are the golden path: fully version-controllable, no UI state.

### 4.3 Feedback: the scoring data model

Source: [feedback-data-format](https://docs.langchain.com/langsmith/feedback-data-format), [evaluation-concepts](https://docs.langchain.com/langsmith/evaluation-concepts#evaluator-outputs).

A feedback record = `{key, score (number), value (string, for categorical), comment, correction, feedback_source, run_id, session_id, ...}`. One record per criterion per run. Experiment-level aggregation is per-key: `feedback_stats: {"<key>": {"n": ..., "avg": ..., "values": {...}}}` ([fetch-perf-metrics-experiment](https://docs.langchain.com/langsmith/fetch-perf-metrics-experiment)).

## 5. Rubric → LangSmith mapping (criteria, ordinal scales, vetoes)

Proposed mapping for EvalPack (`docs/prd.md` §12, §19):

| EvalPack concept | LangSmith construct |
|---|---|
| rubric criterion `id` (e.g. `contradiction_handling`) | feedback `key` (one evaluator function or one `feedback_key` per criterion) |
| ordinal scale 0/1/2 with anchors | `create_llm_as_judge(choices=[0.0, 1.0, 2.0])` with anchor text baked into the prompt; **or** emit both `{"key": k, "score": <ordinal>}` and `{"key": k+"_label", "value": "<anchor name>"}` from a custom evaluator |
| judge rationale requirement | feedback `comment` (openevals emits it by default; `use_reasoning=False` disables) |
| veto criterion (`fabricated_source`, effect: fail) | boolean feedback key (e.g. `veto__fabricated_source`, score 0/1) **plus** a client-side computed `final_result` feedback key; no server-side gating exists |
| overall pass/fail per task | an extra evaluator that returns `{"key": "final_result", "score": 0|1}` after applying veto + weighting logic locally |
| task `metadata` (domain/category/difficulty/risk) | example `metadata` dict (filterable via `list_examples(metadata=...)`) |
| `failure_targets`, `reference.*` (hidden from agent) | example `outputs` (reference outputs) and/or `metadata` — never `inputs`; the target function only receives `inputs` ([evaluation-quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart): "The SDK will automatically send the inputs from the dataset to your target function") |
| difficulty tiers / dataset categories | example metadata, or dataset **splits** for group-wise experiment runs |
| EvalPack name/version provenance | `evaluate(metadata={...})` experiment metadata + `experiment_prefix` |

## 6. Run an experiment over 1–2 cases — `evaluate()`

Source: [evaluation-quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart), [SDK reference for `Client.evaluate`](https://reference.langchain.com/python/langsmith/client/Client/evaluate).

```python
experiment_results = client.evaluate(
    target,                      # callable: (inputs: dict) -> dict
    data="Sample dataset",       # dataset name, Dataset object, or iterable of examples
    evaluators=[criterion_a, criterion_b, veto_check],
    experiment_prefix="evalgrill-smoke",
    max_concurrency=2,
)
```

Full signature (reference.langchain.com, langsmith 0.10.x):

```python
Client.evaluate(target, /, data=None, evaluators=None, summary_evaluators=None,
    metadata=None, experiment_prefix=None, description=None, max_concurrency=0,
    num_repetitions=1, blocking=True, experiment=None, upload_results=True,
    error_handling='log', **kwargs) -> ExperimentResults | ComparativeExperimentResults
```

- A module-level `from langsmith import evaluate` also exists (used throughout [code-evaluator-sdk](https://docs.langchain.com/langsmith/code-evaluator-sdk)); the quickstart's canonical form is `client.evaluate(...)`.
- `upload_results=False` runs everything locally without recording to LangSmith ([local](https://docs.langchain.com/langsmith/local), referenced from [read-local-experiment-results](https://docs.langchain.com/langsmith/read-local-experiment-results)) — useful as a pre-flight tier of the smoke test.
- Pairwise judge protocols map to a different mode: `evaluate((experiment_a, experiment_b), evaluators=[comparative_evaluator])` ([evaluate-pairwise](https://docs.langchain.com/langsmith/evaluate-pairwise)).
- On success it prints a `View the evaluation results for experiment: ... at: https://smith.langchain.com/...` link ([evaluation-quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart)).

## 7. Read feedback/scores back programmatically

Three sanctioned paths:

1. **Locally from the returned `ExperimentResults`** (no extra API calls; the CI-recommended route, [read-local-experiment-results](https://docs.langchain.com/langsmith/read-local-experiment-results)):

```python
results = client.evaluate(target, data=..., evaluators=[...], blocking=True)
for result in results:
    result["run"].inputs / .outputs / .id
    result["example"].inputs / .outputs
    for er in result["evaluation_results"]["results"]:
        er.key, er.score, er.comment, er.source_run_id   # EvaluationResult
```

The docs explicitly frame this for "CI/CD pipelines: Implement quality gates that fail builds if evaluation scores drop below a threshold."

2. **Experiment-level stats from the server**: `client.read_project(project_name=results.experiment_name, include_stats=True)` → payload includes `feedback_stats` per key (`n`, `avg`, `values`), latency percentiles, token counts, cost, `error_rate` ([fetch-perf-metrics-experiment](https://docs.langchain.com/langsmith/fetch-perf-metrics-experiment)).

3. **Raw feedback records**: `client.list_feedback(run_ids=[...], feedback_key=["contradiction_handling"]) -> Iterator[Feedback]` ([SDK reference](https://reference.langchain.com/python/langsmith/client/Client/list_feedback)); run IDs come from `ExperimentResults` or from runs queries.

**Deprecation warning (live now)**: `client.list_runs()` is deprecated in favor of the async `client.runs.query()` — Cloud deprecation "End of July 2026", removal 31 Jan 2027; `runs.query` needs `langsmith>=0.10.15`, does not accept `project_name` (resolve UUID via `read_project` first), defaults `min_start_time` to 1 day ago, and returns only `id` unless `selects=[...]` is passed ([smithdb-sdk-migration](https://docs.langchain.com/langsmith/smithdb-sdk-migration)). The smoke test should avoid `list_runs` entirely and rely on paths 1–3 above (`read_project` and `list_feedback` are not listed as migrated/deprecated in that guide).

## 8. Free-tier limits and CI constraints

Source: [usage-and-billing](https://docs.langchain.com/langsmith/usage-and-billing) (docs), [langchain.com/pricing-langsmith](https://www.langchain.com/pricing-langsmith) (vendor pricing page).

Free tier (**Developer plan, no payment on file**): 1 seat, up to **5,000 base traces/month**, 14-day base retention, $0. Base trace price beyond that: $0.0005/trace (0.05¢); extended-retention (400-day) traces cost 10x.

Rate limits relevant to a smoke test / CI (all return HTTP 429; SDK has built-in retry with backoff):

| Limit | Value | Scope |
|---|---|---|
| `POST/PATCH /runs*` | 5,000 / min | per service key or PAT (load balancer) |
| `POST /feedbacks*` | 5,000 / min | per key |
| **`GET /runs/:id`** | **30 / min** | per key — don't poll individual runs in CI |
| `DELETE /sessions*` | 30 / min | per key |
| any other endpoint | 2,000 / min | per key |
| hourly trace events (create+update each count) | 50,000 / hr (Developer, no CC); 250,000 / hr (with CC) | plan-level |
| hourly ingest size | 500 MB / hr (Developer, no CC) | plan-level |
| monthly unique traces | 5,000 / month (Developer, **no CC only**) | plan-level |

Other CI-relevant facts:
- Every experiment run + evaluator run is traced, so **experiments consume the monthly trace quota**. A 2-example, 2-evaluator smoke run is a handful of traces — negligible; a nightly full-suite run against 5k/month is not.
- Datasets have indefinite retention and don't expire with trace retention ([usage-and-billing](https://docs.langchain.com/langsmith/usage-and-billing)).
- Feedback submitted with `extend_trace_retention=true` silently upgrades traces to the 10x-cost extended tier; the default SDK feedback path in `evaluate()` doesn't require it ([usage-and-billing](https://docs.langchain.com/langsmith/usage-and-billing)).
- Auth for CI: workspace-scoped **service key** + `LANGSMITH_WORKSPACE_ID` (if multi-workspace) + optional `LANGSMITH_ENDPOINT` for EU/APAC/AWS regions ([create-account-api-key](https://docs.langchain.com/langsmith/create-account-api-key)).
- Docs recommend "retry logic with exponential backoff and jitter" for direct API calls; the SDK does this already ([usage-and-billing](https://docs.langchain.com/langsmith/usage-and-billing)).

## 9. Proposed golden-path pseudocode

What `evalgrill export langsmith ./my-eval` should generate into `exports/langsmith/` (PRD §21), and what the live smoke test executes with 1–2 calibration-grade cases:

```python
# exports/langsmith/run_experiment.py  (generated; pseudocode)
# env: LANGSMITH_API_KEY (+ LANGSMITH_WORKSPACE_ID, LANGSMITH_ENDPOINT as needed), judge-provider key
import json, sys, time
from langsmith import Client
from openevals.llm import create_llm_as_judge

client = Client()  # reads env  [create-account-api-key]

# -- 1. Dataset from dataset.jsonl (canonical task schema, PRD §11) --
name = f"evalgrill-smoke-{int(time.time())}"           # unique per run; datasets persist forever
dataset = client.create_dataset(dataset_name=name, description="EvalGrill smoke export")
examples = []
for task in load_jsonl("dataset.jsonl")[:2]:           # 1-2 cases for smoke
    examples.append({
        "inputs": {"query": task["input"]["query"], "context": task["input"]["context"]},
        "outputs": {"reference": task["reference"]},   # hidden reference -> reference outputs
        "metadata": {**task["metadata"],
                     "failure_targets": task["failure_targets"],   # hidden; never in inputs
                     "constraints": task["constraints"],
                     "evalpack_task_id": task["id"]},
    })
client.create_examples(dataset_id=dataset.id, examples=examples)

# -- 2. Evaluators from rubric.yaml (PRD §12) --
evaluators = []
for crit in load_yaml("rubric.yaml")["criteria"]:
    if crit.get("deterministic"):
        evaluators.append(make_code_evaluator(crit))   # def f(inputs, outputs, reference_outputs) -> dict
    else:
        evaluators.append(make_judge(crit))

def make_judge(crit):  # ordinal criterion -> one feedback key
    judge = create_llm_as_judge(
        prompt=render_rubric_prompt(crit),             # anchors 0/1/2 verbatim in prompt text
        feedback_key=crit["id"],
        model=JUDGE_MODEL,                             # "provider:model"
        choices=[float(k) for k in crit["scale"]],     # e.g. [0.0, 1.0, 2.0]
    )
    def evaluator(inputs: dict, outputs: dict, reference_outputs: dict):
        return judge(inputs=inputs, outputs=outputs, reference_outputs=reference_outputs)
    evaluator.__name__ = crit["id"]
    return evaluator

def veto_and_final(inputs: dict, outputs: dict, reference_outputs: dict) -> list[dict]:
    """Vetoes + composite: LangSmith has no gate primitive, so compute it client-side."""
    results, vetoed = [], False
    for v in load_yaml("rubric.yaml")["vetoes"]:       # e.g. fabricated_source
        hit = run_veto_check(v, inputs, outputs, reference_outputs)  # deterministic or judge
        vetoed |= hit
        results.append({"key": f"veto__{v['id']}", "score": 0.0 if hit else 1.0,
                        "comment": v["description"]})
    results.append({"key": "final_result", "score": 0.0 if vetoed else 1.0,
                    "value": "fail" if vetoed else "pass"})
    return results                                     # list[dict] = multi-score  [multiple-scores]
evaluators.append(veto_and_final)

# -- 3. Run experiment --
results = client.evaluate(
    target,                                            # user-supplied agent adapter: inputs -> outputs
    data=dataset,
    evaluators=evaluators,
    experiment_prefix="evalgrill",
    metadata={"evalpack": pack["name"], "schema_version": pack["schema_version"]},
    max_concurrency=2,
    blocking=True,
)                                                      # [Client.evaluate reference]

# -- 4. Read scores back + assert (smoke gate) --
seen_keys = set()
for row in results:                                    # [read-local-experiment-results]
    for er in row["evaluation_results"]["results"]:
        seen_keys.add(er.key)
        assert er.score is not None or er.value is not None
expected = {c["id"] for c in criteria} | {"final_result"}
assert expected <= seen_keys, f"missing feedback keys: {expected - seen_keys}"

proj = client.read_project(project_name=results.experiment_name, include_stats=True)
assert proj.feedback_stats                             # [fetch-perf-metrics-experiment]

fb = list(client.list_feedback(run_ids=[row["run"].id for row in results]))
assert fb                                              # [Client.list_feedback reference]

# -- 5. Cleanup (smoke test only; exporter output keeps the dataset) --
client.delete_dataset(dataset_id=dataset.id)           # [Client.delete_dataset reference]
```

Pre-flight tier: run the same script with `upload_results=False` to validate evaluator wiring without touching quota ([local](https://docs.langchain.com/langsmith/local)).

## 10. Impedance mismatches with EvalPack

Where the canonical schema (PRD §11–12, §14, §18–19) does **not** map cleanly:

1. **Vetoes have no platform semantics.** EvalPack vetoes are zero-tolerance gates ("effect: fail", PRD §12); LangSmith feedback keys are independent metrics with per-key averages ([feedback-data-format](https://docs.langchain.com/langsmith/feedback-data-format), [fetch-perf-metrics-experiment](https://docs.langchain.com/langsmith/fetch-perf-metrics-experiment)). Nothing server-side makes a veto zero out other criteria or fail the experiment. The exporter must synthesize a `final_result` key client-side (and the CI gate must read it); anyone viewing only the LangSmith UI averages can be misled (a run can show 2.0 on every ordinal criterion and still be a veto-fail).
2. **Ordinal scales get averaged as if cardinal.** Feedback `score` is a plain number; `feedback_stats.avg` will happily report "contradiction_handling: 1.37" across runs, which has no anchor meaning. openevals `choices` requires floats and the anchor definitions live only in the prompt text ([openevals README](https://github.com/langchain-ai/openevals#customizing-output-score-values)). Mitigation: export both a numeric key (for sorting/aggregation) and a categorical `value` label per criterion, and document that averages are indicative only. Alternative (normalizing 0/1/2 → 0/0.5/1) trades anchor fidelity for comparability.
3. **Criterion metadata is dropped.** `importance: essential`, `failure_mode` linkage, `evidence` lists, "why it matters" (PRD §12) have no field on a feedback record (only `key/score/value/comment/correction/feedback_source`). Options: key-naming conventions, stuffing into `comment`, or experiment `metadata` — all lossy. The canonical rubric.yaml stays the source of truth; the export is a projection (consistent with PRD §21: "Canonical files must never be rewritten to accommodate a provider").
4. **Set-valued references.** EvalPack references are `required_observations` + `acceptable_outcomes` (multiple valid outcomes, PRD §11); LangSmith reference outputs are a single `outputs` dict per example, and openevals prebuilt prompts assume a single `reference_outputs` ground truth. Fine structurally (a dict can hold lists), but every judge prompt must be custom-rendered to explain the set semantics — prebuilt prompts like `CORRECTNESS_PROMPT` are unusable as-is.
5. **Calibration cases have no native home.** PRD §14–15 requires running the judge against frozen candidate outputs with expected per-criterion scores. LangSmith evaluates a live target over dataset inputs; there is no "evaluate the evaluator" primitive. Workaround: a second dataset where `inputs` = {task + frozen candidate output} and `outputs` = expected scores, with the "target" an identity function and a meta-evaluator comparing judge scores to expected. LangSmith's own offerings here (few-shot examples in judge prompts, [aligning judges via human feedback](https://docs.langchain.com/langsmith/improve-judge-evaluator-feedback)) improve judges but don't measure veto recall / per-criterion agreement — EvalGrill must compute those itself from `ExperimentResults`.
6. **Hidden-information discipline is by convention only.** `failure_targets` and references must not reach the evaluated agent (PRD §11). LangSmith enforces this only structurally: the target receives `inputs`, evaluators can receive `reference_outputs` and the full `example` ([code-evaluator-sdk](https://docs.langchain.com/langsmith/code-evaluator-sdk)). Exporter must never place hidden fields in `inputs`; nothing on the platform checks this.
7. **Judge protocol features are partial.** Pairwise mode exists but as a separate API shape (comparing two experiments, [evaluate-pairwise](https://docs.langchain.com/langsmith/evaluate-pairwise)), not per-criterion pointwise/pairwise choice; candidate anonymization, order swapping, and low-confidence escalation (PRD §12) are all EvalGrill-side prompt/protocol logic.
8. **Weighted composites don't exist server-side.** Any importance-weighted overall score is either a client-computed feedback key or a `summary_evaluators` aggregate; `feedback_stats` only does per-key n/avg/values.

## 11. Open questions

- ~~`create_examples` accepts `split` inline at creation time?~~ Resolved: yes — `ExampleCreate.split: Optional[Union[str, list[str]]]` in [SDK source](https://github.com/langchain-ai/langsmith-sdk/blob/main/python/langsmith/schemas.py).
- Whether server-side "managed evaluators" ([manage-evaluators-sdk](https://docs.langchain.com/langsmith/manage-evaluators-sdk)) are worth a second-tier export target (they'd give in-UI re-runs but reintroduce platform-held config, against PRD §5.7 vendor neutrality).
- openevals 0.2.0 pins `langchain-openai` as a hard dep — confirm an Anthropic-judged export works with `judge=` + `langchain-anthropic` without importing OpenAI creds in CI.

## 12. Source index

- Docs redirect: `https://docs.smith.langchain.com/` → 308 → <https://docs.langchain.com/langsmith>
- <https://docs.langchain.com/langsmith/create-account-api-key> — API keys, env vars, endpoints, SDK install
- <https://docs.langchain.com/langsmith/administration-overview> — orgs, workspaces, PATs vs service keys, resource scoping
- <https://docs.langchain.com/langsmith/evaluation-quickstart> — end-to-end SDK golden path (dataset → judge → evaluate)
- <https://docs.langchain.com/langsmith/manage-datasets-programmatically> — create_dataset/create_examples/list_examples/update_example(s), metadata, splits, filter DSL
- <https://docs.langchain.com/langsmith/code-evaluator-sdk> — custom evaluator arg names and return types
- <https://docs.langchain.com/langsmith/llm-as-judge-sdk> — custom LLM-judge pattern
- <https://docs.langchain.com/langsmith/openevals> — openevals + evaluate() integration, feedback_key
- <https://github.com/langchain-ai/openevals> — create_llm_as_judge options: choices, continuous, use_reasoning, few_shot_examples, output_schema
- <https://docs.langchain.com/langsmith/multiple-scores> — list[dict] multi-metric returns
- <https://docs.langchain.com/langsmith/feedback-data-format> — feedback record schema
- <https://docs.langchain.com/langsmith/evaluation-concepts> — datasets/examples/experiments/splits/feedback concepts
- <https://docs.langchain.com/langsmith/read-local-experiment-results> — ExperimentResults iteration, CI quality gates, blocking
- <https://docs.langchain.com/langsmith/fetch-perf-metrics-experiment> — read_project(include_stats=True), feedback_stats, sessions=projects=experiments
- <https://docs.langchain.com/langsmith/smithdb-sdk-migration> — list_runs → runs.query deprecation timeline and pitfalls
- <https://docs.langchain.com/langsmith/usage-and-billing> — rate limits, plan-level limits, retention tiers, trace pricing
- <https://www.langchain.com/pricing-langsmith> — Developer free plan (1 seat, 5k base traces/mo)
- <https://reference.langchain.com/python/langsmith/client/Client/evaluate> — full evaluate() signature
- <https://reference.langchain.com/python/langsmith/client/Client/list_feedback> — list_feedback signature
- <https://reference.langchain.com/python/langsmith/client/Client/delete_dataset> — delete_dataset signature
- <https://reference.langchain.com/python/langsmith/client/Client/create_examples> — create_examples signature
- <https://github.com/langchain-ai/langsmith-sdk/blob/main/python/langsmith/schemas.py> — `ExampleCreate` fields (inputs, outputs, metadata, split, attachments)
- <https://pypi.org/pypi/langsmith/json>, <https://pypi.org/pypi/openevals/json> — versions and dependencies
