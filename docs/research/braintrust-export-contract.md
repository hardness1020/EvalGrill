# Braintrust export contract (golden path)

Status: research complete
Date: 2026-08-10
Ticket: `.scratch/evalgrill-mvp/issues/02-research-braintrust-export-contract.md`
Canonical EvalPack reference: `docs/prd.md` §11 (task schema), §12 (rubric criteria + vetoes), §14 (calibration cases), §18–21 (EvalPack, canonical schema, platform export, export contract).

Sources are PRIMARY only: official Braintrust docs (`braintrust.dev/docs`), the Braintrust Python SDK source (`github.com/braintrustdata/braintrust-sdk-python`), the autoevals source (`github.com/braintrustdata/autoevals`), PyPI metadata, and `braintrust.dev/pricing`. Facts verified as of 2026-08-10. Note: Braintrust restructured its docs recently; some older URLs (`/docs/guides/...`) now redirect or index into `/docs/evaluate/...`, `/docs/annotate/...`, `/docs/admin/...`, `/docs/api-reference/...`. The doc map is published at https://www.braintrust.dev/docs/llms.txt.

---

## 1. Packages and versions (as of 2026-08-10)

| Package | Latest version | Python requirement | Notes |
|---|---|---|---|
| `braintrust` | 0.32.0 | >=3.10.0 | Core SDK: `Eval()`, `init_dataset()`, `init()`, logging. Extras: `braintrust[cli]`, `braintrust[all]`. Source: https://pypi.org/pypi/braintrust/json |
| `autoevals` | 0.0.130 | >=3.8.0 | Scorer library (LLMClassifier, Factuality, ExactMatch, Levenshtein, JSONDiff, RAG scorers). Deps: chevron, jsonschema, polyleven, pyyaml, openai. Source: https://pypi.org/pypi/autoevals/json |

Quickstart install line is `pip install braintrust openai autoevals` (https://www.braintrust.dev/docs/start/eval-sdk).

Python SDK repo: https://github.com/braintrustdata/braintrust-sdk-python (the old monorepo `braintrustdata/braintrust-sdk` now redirects to the JS-only repo `braintrust-sdk-javascript`).

---

## 2. Auth: API key, env vars, org/project concepts

- **API key**: created in the Braintrust app under Settings > API keys (https://www.braintrust.dev/app/settings?subroute=api-keys). Keys are **user-scoped**: "Braintrust API keys inherit their user's permissions, and essentially are another way to authenticate as a user." Keys are stored as one-way hashes, shown once, cannot be recovered, and may carry an immutable expiration date. Source: https://www.braintrust.dev/docs/admin/authentication
- **Env var**: `BRAINTRUST_API_KEY`. The SDK's `login()` and every `init*` call fall back to it when no `api_key` argument is given ("If the parameter is not specified, will try to use the `BRAINTRUST_API_KEY` environment variable"). Source: SDK source `py/src/braintrust/logger.py` (https://github.com/braintrustdata/braintrust-sdk-python/blob/main/py/src/braintrust/logger.py) and the quickstart (https://www.braintrust.dev/docs/start/eval-sdk).
- **Other env vars** recognized by the SDK (from `logger.py`): `BRAINTRUST_ORG_NAME`, `BRAINTRUST_APP_URL`, `BRAINTRUST_API_URL`.
- **REST auth**: `Authorization: Bearer $BRAINTRUST_API_KEY`; base URL `https://api.braintrust.dev` (US) or `https://api-eu.braintrust.dev` (EU); self-hosted deployments use their own data-plane URL (Settings > Data plane). Source: https://www.braintrust.dev/docs/api-reference
- **Org/project model**: an org contains projects; projects contain datasets, experiments, logs, and prompts. SDK calls reference projects **by name** (`Eval("My project", ...)`, `init_dataset(project="My App", ...)`); the quickstart runs `Eval("Evaluation quickstart", ...)` with no prior project-creation step, i.e. the project is resolved/created on first use (https://www.braintrust.dev/docs/start/eval-sdk). Multi-org users disambiguate with `org_name` (parameter on `init`/`init_dataset`/`login`) or `BRAINTRUST_ORG_NAME` (SDK source `logger.py`).

CI implication: because keys are user-scoped and inherit that user's permissions, a CI smoke test should use a key minted by a dedicated machine account (the authentication page documents no separate service-account object). Source: https://www.braintrust.dev/docs/admin/authentication

---

## 3. Create a dataset programmatically

Exact SDK calls (https://www.braintrust.dev/docs/annotate/datasets/create):

```python
import braintrust

dataset = braintrust.init_dataset(project="My App", name="Customer Support")
dataset.insert(
    input={"question": "How do I reset my password?"},
    expected={"answer": "Click 'Forgot Password' on the login page."},
    metadata={"category": "authentication", "difficulty": "easy"},
)
dataset.flush()  # "Flush to ensure all records are saved."
```

Verified from the SDK reference (https://www.braintrust.dev/docs/reference/libs/python) and source (`logger.py`):

- `init_dataset(project=None, name=None, description=None, version=None, app_url=None, api_key=None, org_name=None, project_id=None, metadata=None, use_output=False, ...) -> Dataset`.
- `Dataset.insert(input=..., expected=..., tags=None, metadata=None, id=None, output=<deprecated>)` — record fields are `input`, `expected`, `metadata`, `tags` (top-level record fields per https://www.braintrust.dev/docs/guides/datasets). `insert` **returns the row id**; passing your own `id` makes re-export idempotent ("If you don't provide one, Braintrust will generate one for you" — `logger.py`). `output` is deprecated: "Use `expected` instead."
- `Dataset.update(id, ...)` and `Dataset.delete(id)` exist for record maintenance; `Dataset.summarize()` returns a `DatasetSummary` with `new_records` / `total_records` (`logger.py`).
- Datasets are versioned; `init_dataset(version=...)` pins a snapshot (SDK reference).

Mapping from EvalPack `dataset.jsonl` (PRD §11): `id -> insert(id=...)`, `input -> input`, `reference -> expected`, `metadata + failure_targets + constraints + review -> metadata`, `difficulty/category -> tags` (optional, for UI filtering). See §8 for the caveats.

---

## 4. Rubric-based LLM-judge scorers: what Braintrust offers

Three scorer types (https://www.braintrust.dev/docs/evaluate/write-scorers): **autoevals** (pre-built), **LLM-as-a-judge** (model-based), **custom code**. Classifiers are a separate construct returning categorical labels, not numeric scores (same page).

### 4.1 Scorer contract (hard constraint)

"A scorer receives the `input`, `output`, `expected`, `metadata`, and `trace` for each result, and returns a number between 0 and 1 (optionally with a `name` and `metadata`)." Source: https://www.braintrust.dev/docs/evaluate/write-scorers

From SDK source (`py/src/braintrust/score.py`): `Score(name: str, score: float | None, metadata: dict)` — "The score is a float between 0 and 1"; `score=None` means the evaluation is **skipped**; `__post_init__` raises `ValueError(f"score ({self.score}) must be between 0 and 1")` otherwise.

From SDK source (`py/src/braintrust/framework.py`, `await_or_run_scorer`): a scorer may return a plain number, a `Score`, a dict shaped like a `Score`, **or a list of `Score` objects** — "When returning an array of scores, each score must be a valid Score object." This is the key affordance for multi-criterion rubrics: **one scorer invocation can emit N named score columns.**

### 4.2 autoevals `LLMClassifier`

Example from https://www.braintrust.dev/docs/evaluate/llm-as-a-judge:

```python
correctness_scorer = LLMClassifier(
    name="Correctness",
    prompt_template="""...{{output}}...{{expected}}...""",
    choice_scores={"correct": 1, "incorrect": 0},
    model="gpt-5-mini",
)
```

Constructor (autoevals source `py/autoevals/llm.py`, https://github.com/braintrustdata/autoevals/blob/main/py/autoevals/llm.py): `LLMClassifier(name, prompt_template, choice_scores, model=DEFAULT_MODEL, use_cot=True, max_tokens=None, temperature=None, client=None, ...)` with `DEFAULT_MODEL = "gpt-5-mini"`. The prompt template is mustache (`{{input}}`, `{{output}}`, `{{expected}}`); the model must answer with exactly one choice key; `score = self.choice_scores[choice]`. `use_cot=True` appends a chain-of-thought suffix.

Judge model auth (autoevals README, https://github.com/braintrustdata/autoevals/blob/main/README.md): by default autoevals calls OpenAI via `OPENAI_API_KEY`; alternatively route any model (e.g. `model="claude-3-5-sonnet-latest"`) through the **Braintrust gateway/proxy** using `BRAINTRUST_API_KEY`, or pass a custom OpenAI-compatible `client=openai.OpenAI(base_url=...)`.

Built-in scorers (https://www.braintrust.dev/docs/reference/autoevals): LLM-based (Battle, ClosedQA, Factuality, Moderation, Security, Summarization, SQL, Translation, Humor), RAG (context precision, faithfulness, answer relevancy), heuristics (Levenshtein, ExactMatch, JSON diff).

### 4.3 Custom code scorers

Any Python callable `def scorer(input, output, expected, metadata=None, ...)` returning a number / `Score` / `list[Score]` (https://www.braintrust.dev/docs/evaluate/custom-code, contract verified in `framework.py`). This is the escape hatch EvalGrill's exporter should use for rubric bundles and veto gating (see §8).

### 4.4 UI prompt scorers and online scorers

- Prompt scorers can be built in the Braintrust UI (prompt + model + choice scores + optional CoT) for rapid iteration (https://www.braintrust.dev/docs/evaluate/llm-as-a-judge).
- **Online scoring** runs scorers server-side, asynchronously, on sampled production logs/spans ("Evaluations run asynchronously in the background without adding latency"), supporting LLM-as-a-judge, custom code, and classifiers (https://www.braintrust.dev/docs/evaluate/score-online). Not needed for the export golden path — it targets production monitoring, not offline eval runs.

### 4.5 How an EvalPack rubric maps on (summary; mismatches in §8)

- One ordinal criterion (PRD §12, scale 0/1/2 with anchors) -> one `LLMClassifier` with `choice_scores={"0": 0.0, "1": 0.5, "2": 1.0}` and the anchor descriptions embedded in `prompt_template`. General rule for an n-point scale: level k -> `k/(n-1)`.
- One veto criterion (PRD §12) -> a binary scorer, `choice_scores={"violation": 0, "no_violation": 1}`.
- The gated `final_result` (veto => fail) has **no platform primitive**; it must be a custom composite scorer generated by the exporter (see §8.2).

---

## 5. Run an eval over 1–2 cases via SDK

`Eval()` signature (https://www.braintrust.dev/docs/reference/libs/python), abbreviated to the golden-path-relevant parameters:

```python
def Eval(
    name: str,                                  # project name
    data,                                       # list of dicts / EvalCase, or init_dataset(...)
    task,                                       # callable: input -> output
    scores=None,                                # sequence of scorers
    experiment_name=None,
    trial_count=1,
    metadata=None,
    tags=None,
    max_concurrency=None,
    timeout=None,
    project_id=None,
    no_send_logs=False,
    ...
) -> EvalResultWithSummary
```

Canonical run-in-code example (https://www.braintrust.dev/docs/evaluate/run-in-code):

```python
from braintrust import Eval, init_dataset
from autoevals import Factuality

Eval(
    "My project",
    experiment_name="My experiment",
    data=init_dataset(project="My project", name="My dataset"),
    task=lambda input: call_model(input),
    scores=[Factuality],
    metadata={"model": "gpt-5-mini"},
)
```

- `data` accepts inline records (`{"input": ..., "expected": ...}` per the quickstart, https://www.braintrust.dev/docs/start/eval-sdk) or a `Dataset` handle — so a 1–2-case smoke test can pass a **slice** of records inline, or the full uploaded dataset.
- The task receives only `input` (not `expected`/`metadata`), which satisfies PRD §11's "hidden reference information must not be exposed to the evaluated Agent" — as long as the exporter does not opt in to hooks that surface metadata.
- CLI runner: `bt eval my_eval.py` (auto `.env` loading; `--watch` for re-runs). Source: https://www.braintrust.dev/docs/evaluate/run-in-code
- `EvalCase` fields (SDK `framework.py`): `input`, `expected`, `metadata`, `tags`, `trial_count`, plus dataset-origin fields `id`, `_xact_id`, `created`, `origin`.

---

## 6. Read scores back programmatically

Three verified paths:

1. **In-process (simplest, use for smoke test).** `Eval()` returns `EvalResultWithSummary` with `summary: ExperimentSummary` and `results: list[EvalResult]` (SDK `framework.py`). Per-case: `EvalResult.scores: Mapping[str, float | None]` plus `input/output/expected/metadata/error`. Aggregate: `ExperimentSummary` has `project_name, project_id, experiment_id, experiment_name, project_url, experiment_url, comparison_experiment_name, scores: dict[str, ScoreSummary], metrics: dict[str, MetricSummary]`; `ScoreSummary` has `name, score` (average across examples), `diff, improvements, regressions` (SDK `logger.py`).
2. **Re-open the experiment read-only.** `braintrust.init(project=..., experiment=..., open=True)` returns a `ReadonlyExperiment` ("A read-only view of an experiment, initialized by passing `open=True` to `init()`" — `logger.py`); it is an `ObjectFetcher`, so records can be iterated/fetched, and `as_dataset()` converts results into dataset-shaped events. Source: SDK reference https://www.braintrust.dev/docs/reference/libs/python and `logger.py`.
3. **REST.**
   - `GET /v1/experiment/{experiment_id}/fetch` returns `events` (each with `scores` — "A dictionary of numeric values (between 0 and 1) to log" — plus `input, output, expected, error, metadata, tags, metrics`, span ids, `created`, `_xact_id`) and a pagination `cursor`. Source: https://www.braintrust.dev/docs/api-reference/experiments/fetch-experiment-get-form
   - `GET /v1/experiment/{experiment_id}/summarize?summarize_scores=true[&comparison_experiment_id=...]` returns `scores` (ScoreSummary entries: name, score in 0–1, diff, improvements, regressions), `metrics`, and experiment/project URLs. Source: https://www.braintrust.dev/docs/api-reference/experiments/summarize-experiment
   - Experiment listing/creation: `GET /v1/experiment`, `POST /v1/experiment` (project_id + name), `POST /v1/experiment/{experiment_id}/insert`. Source: https://www.braintrust.dev/docs/reference/api/Experiments

---

## 7. Free-tier limits, rate limits, CI constraints

From https://www.braintrust.dev/pricing (Starter/free plan, no credit card):

- **$10/month model credits** (relevant if the LLM judge is routed through the Braintrust gateway).
- **1 GB processed data / month** — "total bytes of data ingested across logs, experiments, and datasets. Includes inputs, outputs, prompts, metadata, traces and spans, datasets, attachments" (https://www.braintrust.dev/docs/admin/billing/faq).
- **10k scores / month** — "Each time you record a score, the total number of scores counted toward your monthly usage increases by one" (billing FAQ). A 2-case × 4-criterion smoke run = 8 scores; negligible.
- **14-day retention**; unlimited users, projects, datasets, playgrounds, experiments.
- On exhaustion without on-demand billing, ingestion pauses for the rest of the billing cycle (billing FAQ: "Starter without on-demand usage: ... paused for the rest of the billing cycle") — a CI smoke test on a shared free org can start failing mid-month if other usage burns the quota.

Rate/auth constraints (https://www.braintrust.dev/docs/api-reference):

- "The API uses rate limiting to ensure fair usage. Rate limits are applied per organization and endpoint." Exceeding them returns **429 Too Many Requests**. **No numeric limits are published** — CI code must implement retry-with-backoff on 429.
- Auth is a Bearer token; keys are user-scoped (see §2), so CI needs a dedicated machine-user key stored as a secret (`BRAINTRUST_API_KEY`), plus `OPENAI_API_KEY` (or gateway routing) for the judge model.
- EU orgs must point at `https://api-eu.braintrust.dev` (`BRAINTRUST_API_URL`).

---

## 8. Impedance mismatches with EvalPack

The canonical EvalPack (PRD §18–19) must never be rewritten for a provider (PRD §21). These are the places the Braintrust model does not line up 1:1, and what the generated `exports/braintrust/` code must absorb:

### 8.1 Ordinal scales vs [0,1] floats

EvalPack criteria are ordinal with labeled anchors (0/1/2, PRD §12). Braintrust scores **must** be floats in [0,1] (`score.py`: `ValueError` outside the range; docs: "returns a number between 0 and 1"). The exporter must normalize level k of an n-point scale to `k/(n-1)` and preserve the raw ordinal level in `Score.metadata` (e.g. `{"ordinal_level": 1, "scale_max": 2}`) so results can be round-tripped. Braintrust aggregates by **averaging**, so a mean of 0.5 is ambiguous between "everything mid-anchor" and "half top, half bottom" — the raw levels in metadata (or the per-event `scores` fetched via REST) are the source of truth, not the summary average.

### 8.2 Vetoes have no platform primitive

PRD §5.4/§12: a veto is not a weighted metric; one tripped veto fails the case. Braintrust has no gating/veto concept — every score is an independent 0–1 column, summarized independently (`ExperimentSummary.scores`). Two consequences:

- A veto exported as a plain scorer (`fabricated_source: 0/1`) shows up as just another averaged column; nothing in Braintrust makes it fail the case.
- Scorers run independently and cannot see each other's outputs (`framework.py` launches them as parallel tasks), so a separate "final_result" scorer cannot read the veto scorer's result.

Mapping that works: the exporter generates **one composite rubric scorer** (custom code) that internally runs all criteria judges + veto checks and returns a `list[Score]` — one `Score` per criterion, one per veto, plus a computed `final_result` score with the gate applied (`final = 0.0 if any veto tripped else aggregate(criteria)`). Returning multiple `Score`s from one scorer is supported (`framework.py`: "When returning an array of scores, each score must be a valid Score object."). This keeps per-criterion columns in the UI while making the veto semantics real.

### 8.3 Importance/weights are not representable

Rubric criteria carry `importance` (essential/...; PRD §12). Braintrust has no weighted composite across score columns — each is averaged separately. Weighting must live inside the exporter-generated `final_result` computation; the weights themselves should be echoed into experiment `metadata` for traceability.

### 8.4 One `LLMClassifier` = one criterion = one judge call

`LLMClassifier` maps one model call to one choice and one score (`llm.py`: `score = self.choice_scores[choice]`). An N-criterion rubric therefore costs N judge calls per case, or the exporter writes one custom scorer that makes a single structured-output judge call and fans it out into N `Score`s. The single-call variant is cheaper and keeps criteria correlated to one reading of the transcript, but leaves autoevals' maintained prompt/CoT machinery behind — it must implement its own JSON parsing and refusal handling.

### 8.5 Judge protocol features are DIY

PRD §12's judge protocol (candidate anonymization, pairwise mode with order swapping, low-confidence behavior, disagreement escalation) has no Braintrust primitive. autoevals `Battle` gives basic pairwise-vs-expected, but order swapping, escalation, and confidence thresholds must be implemented in custom scorer code. `Score(score=None)` ("the evaluation is considered to be skipped", `score.py`) is a usable mapping for low-confidence abstention.

### 8.6 Task-schema fields beyond input/expected/metadata

`failure_targets`, `constraints`, `review.solvable/human_verified` (PRD §11) have no first-class dataset fields; they fold into record `metadata` (arbitrary JSON, filterable — https://www.braintrust.dev/docs/guides/datasets). That is workable, but note metadata **is** passed to scorers and is visible in the UI to anyone with project access. It is not passed to the `task` callable by default, which is what PRD §11's hiding requirement actually demands — the exporter must simply never wire metadata/expected into the task.

### 8.7 Calibration cases are a convention, not a feature

PRD §14 calibration cases pin expected judge outputs (`expected: {contradiction_handling: 0, final_result: fail}`) for known candidate outputs. Braintrust has no "judge calibration" object. Mapping: a second dataset (`<name>-judge-calibration`) where `input = {task input, frozen candidate output}`, `expected = expected criterion scores`, `task = identity` (returns the frozen candidate), and `scores` = the same judge scorers plus a comparison scorer that checks judge-vs-expected agreement per criterion. Veto recall / per-criterion agreement (PRD §15) then falls out of the experiment's score columns. Entirely buildable, but it is EvalGrill convention layered on Braintrust, and nothing stops the judge scorers and the calibration comparison from drifting apart.

### 8.8 Retention vs regression tracking

Free-tier 14-day retention (https://www.braintrust.dev/pricing) means smoke-test experiments and their score history evaporate; any longitudinal comparison (`base_experiment_name`, improvements/regressions) is only meaningful within the window unless the org is on Pro+.

---

## 9. Proposed golden-path pseudocode

What `evalgrill export braintrust ./my-eval` should generate under `exports/braintrust/` (PRD §21), and what the live smoke test runs end-to-end. Env: `BRAINTRUST_API_KEY` (+ `OPENAI_API_KEY` or gateway routing for the judge).

```python
# exports/braintrust/eval_pack.py  (generated; illustrative)
import braintrust
from braintrust import Eval, Score
from autoevals import LLMClassifier

PROJECT = "multi-source-research-eval"          # evalgrill.yaml: name

# -- 1. Upload dataset (idempotent via canonical ids) ------------------------
def upload_dataset(records):                     # records = parsed dataset.jsonl
    ds = braintrust.init_dataset(project=PROJECT, name="dataset")
    for r in records:
        ds.insert(
            id=r["id"],                          # research-conflict-014 -> upsert key
            input=r["input"],                    # {query, context}
            expected=r["reference"],             # required_observations, acceptable_outcomes
            metadata={**r["metadata"],           # domain/category/difficulty/risk
                      "failure_targets": r["failure_targets"],
                      "constraints": r["constraints"],
                      "review": r["review"]},
            tags=[r["metadata"]["difficulty"]],
        )
    ds.flush()
    return ds

# -- 2. Rubric -> judges (one LLMClassifier per ordinal criterion) -----------
def make_criterion_judge(criterion):             # criterion = rubric.yaml entry
    n = max(int(k) for k in criterion["scale"]) # e.g. 2
    return LLMClassifier(
        name=criterion["id"],                    # "contradiction_handling"
        prompt_template=render_anchors(criterion),  # embeds scale anchor text,
                                                    # {{input}} {{output}} {{expected}}
        choice_scores={str(k): int(k) / n for k in criterion["scale"]},  # 0/0.5/1
        use_cot=True,
        model=JUDGE_MODEL,
    )

# -- 3. Composite scorer: criteria + vetoes + gated final_result -------------
# (custom code because Braintrust has no veto primitive; scorers cannot see
#  each other's outputs, so gating must happen inside ONE scorer)
def rubric_scorer(input, output, expected, metadata=None, **kwargs):
    scores = []
    for criterion in ORDINAL_CRITERIA:
        r = make_criterion_judge(criterion)(output, expected, input=input)
        scores.append(Score(name=criterion["id"], score=r.score,
                            metadata={"ordinal_level": denormalize(r.score, criterion),
                                      "rationale": r.metadata.get("rationale")}))
    veto_tripped = False
    for veto in VETO_CRITERIA:                   # e.g. fabricated_source
        v = run_veto_check(veto, input, output, expected)   # binary judge or code
        veto_tripped |= (v == 0)
        scores.append(Score(name=f"veto_{veto['id']}", score=v))
    final = 0.0 if veto_tripped else weighted_mean(scores, WEIGHTS)  # importance
    scores.append(Score(name="final_result", score=final,
                        metadata={"veto_tripped": veto_tripped}))
    return scores                                # list[Score] -> N columns

# -- 4. Run the eval (smoke test: slice to 1-2 cases inline) -----------------
result = Eval(
    PROJECT,
    experiment_name="smoke-2026-08-10",
    data=smoke_slice(records, n=2),              # or data=braintrust.init_dataset(...)
    task=lambda input: candidate_under_test(input),   # never sees expected/metadata
    scores=[rubric_scorer],
    metadata={"evalgrill_schema_version": 1},
    max_concurrency=2,
)

# -- 5. Read scores back ------------------------------------------------------
summary = result.summary                          # ExperimentSummary
assert summary.experiment_id is not None
for name, s in summary.scores.items():            # ScoreSummary: name, avg score
    print(name, s.score)
for case in result.results:                       # per-case EvalResult
    print(case.input, case.scores["final_result"])

# Independent verification via REST (what the smoke test asserts against):
#   GET https://api.braintrust.dev/v1/experiment/{summary.experiment_id}/fetch
#   GET https://api.braintrust.dev/v1/experiment/{summary.experiment_id}/summarize?summarize_scores=true
#   Authorization: Bearer $BRAINTRUST_API_KEY     (retry on 429)

# -- 6. Judge calibration (separate experiment; EvalGrill convention) ---------
Eval(
    PROJECT,
    experiment_name="judge-calibration",
    data=[{"input": c["task_ref"], "expected": c["expected"],   # calibration.jsonl
           "metadata": {"candidate_id": c["candidate_id"]}}
          for c in calibration_cases],
    task=lambda input: frozen_candidate_output(input),          # identity replay
    scores=[rubric_scorer, judge_agreement_scorer],             # judge vs expected
)
```

Smoke-test acceptance: dataset upserted (row ids echo canonical ids), experiment created, `summary.scores` contains every criterion id + each `veto_*` + `final_result`, REST `fetch` returns per-event `scores` matching in-process `result.results`, and a deliberately-veto-tripping calibration case yields `final_result == 0.0`.

---

## 10. Open questions / risks

1. **Rate limits are unpublished** — per-org, per-endpoint, 429 on excess (https://www.braintrust.dev/docs/api-reference). CI must assume backoff; burst behavior under parallel scorer traffic is unknown.
2. **No service accounts documented** — keys inherit a human user's permissions (https://www.braintrust.dev/docs/admin/authentication); CI hygiene depends on a machine-user convention.
3. **`autoevals` is pre-1.0 (0.0.130)** and the docs IA was recently reshuffled; URL and API churn risk for generated export code. Pin versions in `exports/braintrust/requirements.txt`.
4. **Free-tier 14-day retention** limits any longitudinal smoke-test assertions; monthly quota exhaustion pauses ingestion silently for the rest of the cycle (https://www.braintrust.dev/pricing, https://www.braintrust.dev/docs/admin/billing/faq).
5. **Judge-model dependency**: autoevals defaults to `gpt-5-mini` via `OPENAI_API_KEY`; routing through the Braintrust gateway consumes the $10 free credit. Which judge the smoke test standardizes on is an EvalGrill decision (PRD §15 calibration should gate it).
