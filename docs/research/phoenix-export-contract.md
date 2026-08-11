# Phoenix export contract (golden path)

Research ticket: `.scratch/evalgrill-mvp/issues/04-research-phoenix-export-contract.md`
Date: 2026-08-10
Sources: primary only — official Arize Phoenix docs (`arize.com/docs/phoenix`), Phoenix ReadTheDocs client/evals references, PyPI package pages, and the `Arize-ai/phoenix` GitHub source. No third-party blogs.

Caveat on doc quality: several pages under `arize.com/docs/phoenix/datasets-and-experiments/how-to-experiments/*` currently serve **Arize AX** content (`from arize import ArizeClient`) instead of Phoenix content — Arize AX is a different product with a different SDK. Everything below was cross-checked against the Phoenix client ReadTheDocs reference and the `phoenix-client` source on GitHub, which are unambiguous. Exporter codegen must target the `phoenix.client` / `phoenix.evals` APIs, never `arize.*`.

---

## 1. Current packages and versions (as of 2026-08-10)

| Package | Version | Released | Role | Source |
|---|---|---|---|---|
| `arize-phoenix` | 19.21.0 | 2026-08-10 | Full server + app (Elastic License 2.0; Python >=3.10,<3.15) | https://pypi.org/project/arize-phoenix/ |
| `arize-phoenix-client` | 2.13.0 | 2026-07-12 | Lightweight REST client: datasets, experiments, prompts, spans, annotations | https://pypi.org/project/arize-phoenix-client/ |
| `arize-phoenix-evals` | 3.4.0 | 2026-08-08 | Evaluator building blocks: `LLM`, `ClassificationEvaluator`, `create_classifier`, `create_evaluator` | https://pypi.org/project/arize-phoenix-evals/ |

Key packaging fact for the exporter and smoke test: **the full `arize-phoenix` package is not needed on the client side.** The generated export code and the CI smoke test only need `arize-phoenix-client` + `arize-phoenix-evals`; the server runs separately (Docker or Cloud). (Client purpose: "an interface for interacting with the Phoenix platform via its REST API, enabling you to manage datasets, run experiments, analyze traces, and collect feedback programmatically" — https://pypi.org/project/arize-phoenix-client/.)

Legacy evals API status: `phoenix.evals` 2.0.0 (2025-09-17) moved the old API (`llm_classify`, `run_evals`, old `LLMEvaluator`) to `phoenix.evals.legacy`; 3.0.0 (2026-04-07) "deprecate[d] evals 1.0 and remove[d] legacy experiments module". The current `main` source tree of `packages/phoenix-evals/src/phoenix/evals` has **no `legacy` directory and no `llm_classify`** (https://raw.githubusercontent.com/Arize-ai/phoenix/main/packages/phoenix-evals/CHANGELOG.md, https://github.com/Arize-ai/phoenix/tree/main/packages/phoenix-evals/src/phoenix/evals). **Do not generate `llm_classify` code; target the 3.x API.**

---

## 2. Deployment / auth story

### Self-host (recommended for release-CI smoke test)

- Docker: `docker pull arizephoenix/phoenix` then `docker run -p 6006:6006 -p 4317:4317 arizephoenix/phoenix:latest` (pin a version tag in CI). Port 6006 = UI + OTLP HTTP + REST API; 4317 = OTLP gRPC. Default storage is SQLite inside the container (persist via `PHOENIX_WORKING_DIR` volume); Postgres >= 14 supported via `PHOENIX_SQL_DATABASE_URL`. https://arize.com/docs/phoenix/self-hosting/deployment-options/docker
- Terminal alternative: `phoenix serve` via CLI (requires the full `arize-phoenix` pip package). https://arize.com/docs/phoenix/environments, https://arize.com/docs/phoenix/self-hosting/deployment-options/terminal
- **Auth is disabled by default**: "By default Phoenix deploys with authentication disabled as you may be just trying Phoenix for the very first time or have Phoenix deployed in a VPC." Enable with `PHOENIX_ENABLE_AUTH=True` + `PHOENIX_SECRET` (long random string, >=32 chars). With auth on, a default admin `admin@localhost` / `admin` is created (presettable via `PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD`); API keys come in **System keys** (admin-created, survive user deletion — right choice for CI) and **User keys**. Clients authenticate via `PHOENIX_API_KEY`, sent as `Authorization: Bearer <token>`. https://arize.com/docs/phoenix/self-hosting/features/authentication

### Phoenix Cloud

- Managed instances at `https://app.phoenix.arize.com` with per-space base URLs of the form `https://app.phoenix.arize.com/s/<space-name>`; API keys are created in Settings → API Keys (System vs User keys, same semantics as self-host). https://arize.com/docs/phoenix/phoenix-cloud, https://pypi.org/project/arize-phoenix-client/
- Free tier: free Phoenix Cloud instances preconfigured with 10 GiB of storage. https://arize.com/docs/phoenix/phoenix-cloud
- Rate limits for Cloud are **not publicly documented** on the docs pages reviewed — treat as unknown (risk noted in §8).

### Client configuration (both deployments)

```bash
export PHOENIX_BASE_URL="http://localhost:6006"        # or https://app.phoenix.arize.com/s/<space>
export PHOENIX_API_KEY="..."                            # only if auth enabled / Cloud
```
`phoenix.client.Client()` picks these up; explicit `Client(base_url=..., api_key=...)` also works. https://pypi.org/project/arize-phoenix-client/. Related env vars for other surfaces: `PHOENIX_COLLECTOR_ENDPOINT` (trace export), `PHOENIX_CLIENT_HEADERS` (custom headers). https://arize.com/docs/phoenix/environments

### CI recommendation

**Local Docker self-host, pinned image tag, auth disabled, SQLite, no volume.** Rationale: zero external secrets (only the judge-LLM key), no rate limits, hermetic and free, and the container is discarded after the run. Optionally run a second CI leg with `PHOENIX_ENABLE_AUTH=True` + a System key to exercise the Bearer-auth code path that Cloud users will hit. Phoenix Cloud is better exercised as an occasional manual/nightly check, since it needs a long-lived account, a space, a stored API key, and has undocumented rate limits.

---

## 3. Upload a dataset programmatically

Current API is `phoenix.client.Client().datasets.create_dataset` (the old `px.Client().upload_dataset` belongs to the legacy full-package client; the docs' programmatic examples now use `phoenix.client`). Two shapes, both verified against https://arize.com/docs/phoenix/datasets-and-experiments/how-to-datasets/creating-datasets and https://arize-phoenix.readthedocs.io/projects/client/:

```python
from phoenix.client import Client
client = Client()  # PHOENIX_BASE_URL / PHOENIX_API_KEY from env

# (a) from parallel lists of dicts — inputs / outputs / metadata are per-example
dataset = client.datasets.create_dataset(
    name="customer-support-qa",
    dataset_description="Q&A dataset for customer support evaluation",
    inputs=[{"question": "How do I reset my password?"}],
    outputs=[{"answer": "Click the 'Forgot Password' link on login."}],
    metadata=[{"category": "account", "difficulty": "easy"}],
)

# (b) from a pandas DataFrame with key selection
dataset = client.datasets.create_dataset(
    dataframe=dataset_df,
    name="physics-questions",
    input_keys=["query"],
    output_keys=["responses"],
)
```

Retrieval / update: `client.datasets.get_dataset(dataset="name-or-id")`, `client.datasets.list()`, plus dataset-append operations documented at https://arize.com/docs/phoenix/datasets-and-experiments/how-to-datasets/updating-datasets. A raw REST path also exists: `POST /v1/datasets/upload` (JSON/CSV/pyarrow) — https://arize.com/docs/phoenix/sdk-api-reference/rest-api/api-reference/datasets/upload-dataset-from-json-csv-or-pyarrow.

Mapping from EvalPack `dataset.jsonl` (PRD §11 canonical task schema):
- `input.*` (query + context) → `inputs` dict
- `reference.*` (required_observations, acceptable_outcomes) → `outputs` dict (Phoenix calls this the reference/expected output)
- `metadata`, `failure_targets`, `constraints`, `review` → `metadata` dict (free-form; Phoenix does not validate)

---

## 4. Rubric-based LLM evaluators (phoenix.evals 3.x)

Building blocks (all from https://arize.com/docs/phoenix/evaluation/how-to-evals/custom-llm-evaluators, https://arize-phoenix.readthedocs.io/projects/evals/, https://pypi.org/project/arize-phoenix-evals/):

- `LLM(provider="openai" | "anthropic" | "google" | "litellm", model=...)` — unified judge-model wrapper.
- `ClassificationEvaluator(name, prompt_template, llm, choices, direction=...)` — LLM-as-judge with a **label → score mapping**. This is the natural target for one EvalPack rubric criterion:

```python
from phoenix.evals import ClassificationEvaluator
from phoenix.evals.llm import LLM

# Ordinal scale (PRD §12 example: contradiction_handling 0/1/2)
contradiction_handling = ClassificationEvaluator(
    name="contradiction_handling",
    prompt_template=RUBRIC_TEMPLATE,   # anchors 0/1/2 written out in prose, vars like {{input}} {{output}}
    llm=LLM(provider="anthropic", model="claude-sonnet-4-5"),
    choices={"0": 0, "1": 1, "2": 2},  # numeric/Likert scales are supported this way
)
```
  (Numeric-rating `choices = {str(i): i for i in range(1, 11)}` and `direction="minimize"` shown verbatim in the custom-LLM-evaluators doc.)
- `create_classifier(name, prompt_template, llm, choices)` — functional shorthand for the same thing (PyPI quickstart).
- `create_evaluator(name, kind="code")` decorator — deterministic/code evaluators (regex checks, exact match, citation presence). https://arize.com/docs/phoenix/datasets-and-experiments/how-to-experiments/using-evaluators
- `LLMEvaluator` subclass with a JSON `TOOL_SCHEMA` and `llm.generate_object(...)` returning `Score(score=..., name=..., explanation=..., metadata=..., direction=...)` — for judges that must return structured output (rating + rationale) instead of a single label. https://arize.com/docs/phoenix/evaluation/how-to-evals/custom-llm-evaluators
- `bind_evaluator(evaluator, input_mapping)` / `evaluator.bind({...})` — remap experiment/dataset fields onto template variables (needed when rubric evidence is `task.context` rather than plain input/output). https://arize-phoenix.readthedocs.io/projects/evals/, https://arize.com/docs/phoenix/datasets-and-experiments/quickstart-datasets
- Batch/offline mode outside experiments: `evaluate_dataframe(dataframe, evaluators)` / `async_evaluate_dataframe(...)`. https://arize-phoenix.readthedocs.io/projects/evals/

How EvalPack concepts map:
- **One rubric criterion → one named evaluator.** A multi-criterion rubric becomes a list of evaluators attached to the experiment; each produces an independent score/label/explanation annotation per example.
- **Ordinal scales** → `choices` label→score maps; anchor descriptions live in the prompt template text.
- **Zero-tolerance vetoes** (PRD §12 `fabricated_source`, `effect: fail`) → a `ClassificationEvaluator` (or code evaluator when checkable deterministically) with `choices={"veto": 0, "pass": 1}`. The score is recorded — but see §7: Phoenix will **not** enforce `effect: fail` on the overall result.
- **Deterministic-first principle (PRD §5.3)** → `@create_evaluator(kind="code")` functions, which run without a judge model.

Evaluator function signature contract (for code evaluators in experiments): parameters may be any combination of `input`, `output`, `expected` (alias `reference`), `metadata`, `trace_id`; returns `bool | float | str | tuple[float, str] | EvaluationResult{score, label, explanation, metadata}`. https://arize.com/docs/phoenix/datasets-and-experiments/how-to-experiments/using-evaluators, https://raw.githubusercontent.com/Arize-ai/phoenix/main/packages/phoenix-client/src/phoenix/client/resources/experiments/__init__.py

---

## 5. Run an experiment over 1–2 cases

Entry point: `client.experiments.run_experiment(...)` (also importable as `from phoenix.client.experiments import run_experiment`). Verified signature from the client source (https://raw.githubusercontent.com/Arize-ai/phoenix/main/packages/phoenix-client/src/phoenix/client/resources/experiments/__init__.py) and ReadTheDocs (https://arize-phoenix.readthedocs.io/projects/client/api/experiments.html):

```python
run_experiment(
    *, dataset, task, evaluators=None,
    experiment_name=None, experiment_description=None, experiment_metadata=None,
    rate_limit_errors=None, dry_run=False, print_summary=True,
    timeout=DEFAULT_TIMEOUT_IN_SECONDS, repetitions=1, retries=3,
) -> RanExperiment
```

- `task` is a plain function; like evaluators it can declare parameters by name (e.g. `def my_task(input): ...` or `def my_task(example): ...`). https://arize.com/docs/phoenix/datasets-and-experiments/quickstart-datasets
- `dry_run=True` (or an int sample size) executes task + evaluators **without writing to the server** — useful as a fast pre-flight in the smoke test before the recorded run. https://arize-phoenix.readthedocs.io/projects/client/api/experiments.html
- A 1–2 case run is just a 1–2 example dataset; there is no minimum size.
- Post-hoc evaluation: `client.experiments.evaluate_experiment(experiment=..., evaluators=[...], ...)` adds evaluators to an already-ran experiment. https://arize-phoenix.readthedocs.io/projects/client/api/experiments.html

Server-side REST calls made under the hood (useful for a language-agnostic exporter later): `POST /v1/datasets/{dataset_id}/experiments`, `POST /v1/experiments/{experiment_id}/runs`, `POST /v1/experiment_evaluations`. (Client source, URL above.)

---

## 6. Read evaluation scores back programmatically

Two verified paths (client source + ReadTheDocs, URLs above):

1. **In-process, from the return value.** `run_experiment` returns a `RanExperiment` TypedDict:
   ```python
   {
     "experiment_id": str,
     "dataset_id": str,
     "dataset_version_id": str,
     "task_runs": list[ExperimentRun],
     "evaluation_runs": list[ExperimentEvaluationRun],   # scores/labels/explanations per evaluator per example
     "experiment_metadata": Mapping[str, Any],
     "project_name": Optional[str],
   }
   ```
   The smoke test asserts directly on `evaluation_runs` (each carries the evaluator's `EvaluationResult`: `score`, `label`, `explanation`, `metadata`).

2. **Round-trip from the server** (proves persistence — the stronger smoke-test assertion):
   ```python
   experiment = client.experiments.get_experiment(experiment_id=exp_id)
   ```
   `get_experiment` reconstructs a `RanExperiment` from `GET /v1/experiments/{id}`, `GET /v1/experiments/{id}/runs`, and `GET /v1/experiments/{id}/json` (evaluation annotations). Raw REST is also available for non-Python consumers: https://arize.com/docs/phoenix/sdk-api-reference/rest-api/api-reference/experiments (get experiment by id, list runs, JSON/CSV downloads of runs + evaluations).

---

## 7. Proposed golden-path pseudocode

Target for `evalgrill export phoenix ./my-eval` codegen (`exports/phoenix/`) and the release-CI smoke test. Only APIs verified in §§3–6 are used.

```python
# exports/phoenix/run_experiment.py  (generated; requires arize-phoenix-client>=2, arize-phoenix-evals>=3)
# Env: PHOENIX_BASE_URL (default http://localhost:6006), PHOENIX_API_KEY (only if auth), judge key e.g. ANTHROPIC_API_KEY
import json, pathlib
from phoenix.client import Client
from phoenix.evals import ClassificationEvaluator, create_evaluator
from phoenix.evals.llm import LLM

client = Client()

# 1) dataset.jsonl -> Phoenix dataset (input / reference-output / metadata split)
records = [json.loads(l) for l in pathlib.Path("dataset.jsonl").read_text().splitlines()]
dataset = client.datasets.create_dataset(
    name="multi-source-research-eval",                       # evalgrill.yaml: name
    dataset_description="Evaluates evidence-grounded multi-source research tasks.",
    inputs=[r["input"] for r in records],                     # query + context (visible to agent)
    outputs=[r["reference"] for r in records],                # required_observations, acceptable_outcomes
    metadata=[{**r["metadata"],                               # domain/category/difficulty/risk
               "failure_targets": r["failure_targets"],       # judge-only by CONVENTION (see §8.3)
               "constraints": r["constraints"],
               "review": r["review"]} for r in records],
)

# 2) rubric.yaml -> one evaluator per criterion
judge = LLM(provider="anthropic", model="<judge-model>")

contradiction_handling = ClassificationEvaluator(             # ordinal criterion (type: ordinal, scale 0..2)
    name="contradiction_handling",
    prompt_template=render_rubric_prompt(criterion),          # anchors + evidence fields inlined as prose
    llm=judge,
    choices={"0": 0, "1": 1, "2": 2},
)

fabricated_source = ClassificationEvaluator(                  # veto criterion (type: veto, effect: fail)
    name="veto__fabricated_source",                           # name prefix marks veto semantics for aggregation
    prompt_template=render_veto_prompt(veto),
    llm=judge,
    choices={"veto": 0.0, "pass": 1.0},
)

@create_evaluator(name="final_result", kind="code")           # EvalGrill-owned aggregation (Phoenix has none)
def final_result(output, expected, metadata):
    ...                                                       # recompute deterministic checks; veto -> 0.0
    return 0.0 if any_veto_triggered else weighted_score

# 3) task under test (agent adapter; sees ONLY input)
def task(input):
    return run_agent_under_test(input)

# 4) run over the 1-2 smoke cases
experiment = client.experiments.run_experiment(
    dataset=dataset,
    task=task,
    evaluators=[contradiction_handling, fabricated_source, final_result],
    experiment_name="evalgrill-smoke",
    experiment_metadata={"evalgrill_schema_version": 1},
)

# 5) read scores back and assert (smoke test)
persisted = client.experiments.get_experiment(experiment_id=experiment["experiment_id"])
evals = persisted["evaluation_runs"]
assert {e.name for e in evals} >= {"contradiction_handling", "veto__fabricated_source", "final_result"}
assert all(e.result["score"] is not None for e in evals)      # score/label/explanation present
```

CI harness around it:

```yaml
# release-ci sketch
services:
  phoenix:
    image: arizephoenix/phoenix:<pinned-tag>    # never :latest in CI
    ports: ["6006:6006"]
steps:
  - pip install "arize-phoenix-client>=2.13" "arize-phoenix-evals>=3.4"
  - export PHOENIX_BASE_URL=http://localhost:6006          # auth off by default
  - python exports/phoenix/run_experiment.py               # optional first pass with dry_run=True
```

---

## 8. Impedance mismatches with EvalPack

1. **No native veto semantics (biggest gap).** PRD §5.4/§12: a veto (`fabricated_source`, `effect: fail`) must force overall failure regardless of other scores. Phoenix evaluators are *independent* annotations — there is no built-in cross-evaluator aggregation, gating, or "overall pass/fail" concept in `run_experiment` (RanExperiment has only per-evaluator `evaluation_runs`; https://raw.githubusercontent.com/Arize-ai/phoenix/main/packages/phoenix-client/src/phoenix/client/resources/experiments/__init__.py). **Mitigation:** the exporter must emit an EvalGrill-owned `final_result` code evaluator (or post-hoc aggregation in the smoke test) that applies veto → fail; the veto rule lives in generated code, not in the platform.

2. **Ordinal scales flatten into prompt prose + a label→score map.** `ClassificationEvaluator(choices={...})` carries labels and numeric scores, but the per-anchor descriptions (PRD §12 scale 0/1/2 descriptions), `importance: essential`, and `failure_mode` linkage have no structured home — they must be serialized into the prompt template and/or `Score.metadata`. Round-tripping a rubric back out of Phoenix is lossy; the canonical `rubric.yaml` stays authoritative (consistent with PRD §21: "Canonical files must never be rewritten to accommodate a provider"). https://arize.com/docs/phoenix/evaluation/how-to-evals/custom-llm-evaluators

3. **"Hidden from the evaluated Agent" is convention, not enforcement.** PRD §11 requires `failure_targets`/reference hidden from the agent. In Phoenix experiments the task function receives whatever parameters it declares — and `expected`/`metadata` are *available* to it on request (https://arize.com/docs/phoenix/datasets-and-experiments/how-to-experiments/using-evaluators). Isolation exists only because generated task adapters declare `def task(input)`. A hand-edited export could leak reference data; the exporter should emit a lint/comment guard.

4. **No importance weighting across criteria.** `essential` vs. lesser importance (PRD §12) has no Phoenix construct; every evaluator is co-equal in the UI. Weighting again lands in the generated `final_result` aggregator.

5. **Judge protocol features are out of scope for phoenix.evals.** Pairwise mode, order swapping, candidate anonymization, low-confidence behavior, disagreement escalation (PRD §12 judge protocol) have no counterpart in `ClassificationEvaluator`/`create_classifier`, which are pointwise (https://arize-phoenix.readthedocs.io/projects/evals/). Pairwise/anonymized judging would have to be custom `LLMEvaluator` subclasses — i.e., EvalGrill code, not platform features.

6. **Calibration cases (PRD §14) have no native construct.** Phoenix has no "expected judge score" concept. Model calibration as a *second* dataset whose inputs are (task, candidate output) and whose reference outputs are expected per-criterion scores, with the judge itself as the experiment task; agreement/veto-recall metrics (PRD §15) are then code evaluators. Workable, but entirely hand-rolled.

7. **Multi-criterion output is N annotations, not one structured record.** EvalPack thinks in one scored rubric per candidate; Phoenix stores one `ExperimentEvaluationRun` per evaluator per example. Reading back a "rubric result" means joining `evaluation_runs` by example — the exporter's read-back helper should do this join.

8. **Docs drift / product confusion risk.** Official Phoenix how-to URLs currently serving Arize AX content (see header) is itself a hazard for codegen based on scraped docs; the export contract should pin to `phoenix.client`/`phoenix.evals` APIs and the ReadTheDocs references.

Where it fits well: dataset upload (input/reference/metadata triples map 1:1), per-criterion ordinal scoring via `choices`, deterministic checks via `create_evaluator(kind="code")`, judge-model choice via `LLM(provider="anthropic", ...)` (Anthropic supported: https://pypi.org/project/arize-phoenix-evals/), 1–2-case experiments, `dry_run` pre-flight, and full programmatic read-back including a persistence-proving `get_experiment` round trip.

---

## 9. CI / free-tier / auth constraints summary

- **Self-host CI cost: zero.** Docker image, SQLite default, auth off by default, no external account. License is Elastic License 2.0 — fine for running as an internal CI service, not for offering Phoenix itself as a managed service (https://pypi.org/project/arize-phoenix/).
- **Auth matrix:** local default = none; auth-enabled self-host and Cloud = `PHOENIX_API_KEY` → `Authorization: Bearer` (System key recommended for CI durability) (https://arize.com/docs/phoenix/self-hosting/features/authentication).
- **Phoenix Cloud free tier:** free instance(s) with 10 GiB storage; space-scoped base URL `https://app.phoenix.arize.com/s/<space>`; API keys minted in Settings (https://arize.com/docs/phoenix/phoenix-cloud). Cloud **rate limits are not publicly documented** — do not put Cloud on the release-blocking path.
- **Version pinning:** pin `arizephoenix/phoenix:<tag>` and `arize-phoenix-client`/`arize-phoenix-evals` minor versions; the evals package has had two breaking majors in ~18 months (2.0.0 on 2025-09-17, 3.0.0 on 2026-04-07 per its CHANGELOG).

---

## Sources

- PyPI: https://pypi.org/project/arize-phoenix/ , https://pypi.org/project/arize-phoenix-client/ , https://pypi.org/project/arize-phoenix-evals/
- Docs index: https://arize.com/docs/phoenix , https://arize.com/docs/phoenix/llms.txt
- Datasets: https://arize.com/docs/phoenix/datasets-and-experiments/how-to-datasets/creating-datasets , https://arize.com/docs/phoenix/datasets-and-experiments/quickstart-datasets , https://arize.com/docs/phoenix/sdk-api-reference/rest-api/api-reference/datasets/upload-dataset-from-json-csv-or-pyarrow
- Experiments: https://arize-phoenix.readthedocs.io/projects/client/ , https://arize-phoenix.readthedocs.io/projects/client/api/experiments.html , https://raw.githubusercontent.com/Arize-ai/phoenix/main/packages/phoenix-client/src/phoenix/client/resources/experiments/__init__.py , https://arize.com/docs/phoenix/sdk-api-reference/rest-api/api-reference/experiments
- Evals: https://arize.com/docs/phoenix/evaluation/how-to-evals/custom-llm-evaluators , https://arize.com/docs/phoenix/datasets-and-experiments/how-to-experiments/using-evaluators , https://arize-phoenix.readthedocs.io/projects/evals/ , https://raw.githubusercontent.com/Arize-ai/phoenix/main/packages/phoenix-evals/CHANGELOG.md , https://github.com/Arize-ai/phoenix/tree/main/packages/phoenix-evals/src/phoenix/evals
- Deployment/auth: https://arize.com/docs/phoenix/self-hosting , https://arize.com/docs/phoenix/self-hosting/deployment-options/docker , https://arize.com/docs/phoenix/self-hosting/features/authentication , https://arize.com/docs/phoenix/environments , https://arize.com/docs/phoenix/phoenix-cloud
