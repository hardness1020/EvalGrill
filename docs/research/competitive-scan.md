# Competitive Scan: Who Else Does Eval Design/Validation?

**Ticket:** `.scratch/evalgrill-mvp/issues/06-research-competitive-scan.md`
**Date:** 2026-08-10
**Method:** Every tool surveyed against primary sources only — official docs, official GitHub repos, arXiv papers, official changelogs/blogs. No third-party roundups. Each tool is assessed on: (a) does it help **design** evaluations, (b) does it **validate** evaluations, (c) does it mainly **execute** them, (d) overlap with EvalGrill's layer (PRD §34–35), (e) what's worth stealing.

---

## 0. Summary Table

| Tool | Design (taxonomy, dataset guidance) | Validate (judge calibration, coverage, reward-hacking) | Execute | Status (Aug 2026) |
|---|---|---|---|---|
| EvalGen (Shankar et al.) | Partial — LLM criteria elicitation | **Yes (core)** — Alignment/Coverage/FFR vs human grades | Incidental (in ChainForge) | Shipped in ChainForge; research line moved on |
| SPADE | Partial — prompt-delta criteria taxonomy | Yes — ILP assertion selection under Coverage/FFR constraints | No | Absorbed into LangSmith (2k+ pipelines) |
| AlignEval (Eugene Yan) | Light — forces data-looking first | Yes — κ/F1/precision/recall vs 20+ human labels | In-app only | Dormant prototype (last push Nov 2024) |
| EvalAssist (IBM) | Yes — criteria refinement + synthetic edge cases | Partial — positional-bias, certainty checks | Hands off to Unitxt | Active, Apache-2.0 |
| Verdict (Haize Labs) | No | Indirect — reliability via judge architecture | **Yes** — judge execution | Quiet since Nov 2025 |
| promptfoo | Partial — red-team taxonomy, persona dataset gen | Guidance only (documented workflow, manual) | **Yes (core)** | Very active, 24k stars |
| OpenAI Evals | Prose guidance only | Thin — grader validation endpoints, advice | Dying — platform shutdown Nov 2026 | Repo dormant; platform deprecated |
| Inspect AI (UK AISI) | No | Partial — Scanners (run integrity, reward-hacking on transcripts) | **Yes (core)** | Very active |
| DeepEval (Confident AI) | Partial — Synthesizer, DAG grammar | Doctrine in OSS; tooling SaaS-gated (Eval Alignment queues) | **Yes (core)** | Very active, ~17.5k stars |
| Braintrust (Loop, autoevals) | Partial — Loop mines failures, generates scorers/datasets | Weak — manual comparison, calibration review queues | **Yes (core)** | Very active; Loop shipping monthly |
| LangSmith (Align Evals, openevals) | Barely — AI-generated examples | **Yes — Align Evals** (percent agreement vs golden set) | **Yes (core)** | Align Evals live since Jul 2025 |
| Phoenix (Arize) | Minimal | Vendor-side only — benchmarks its own templates (F1 ≥ 85%) | **Yes (core)** | Very active; evals v3.4.0 Aug 2026 |

**Headline:** every execution platform now *preaches* EvalGrill's thesis (calibrate judges against humans, watch for grader hacking, mix edge/adversarial cases) in its official docs. Only one shipped product feature computes judge-vs-human agreement (LangSmith Align Evals, and its metric is naive percent agreement). **Nobody ships**: failure-first taxonomy as entry point, a failure-mode × test-case × criterion coverage matrix, veto-vs-weighted rubric semantics, reward-hacking/verbosity/stability probes as product features, or a vendor-neutral portable eval-design artifact.

---

## 1. EvalGen — "Who Validates the Validators?" (Shankar, Zamfirescu-Pereira, Hartmann, Parameswaran, Arawjo; UIST 2024)

Sources: [arXiv:2404.12272](https://arxiv.org/abs/2404.12272) (full paper), [ACM DOI 10.1145/3654777.3676450](https://dl.acm.org/doi/fullHtml/10.1145/3654777.3676450), shipped code in [ChainForge main branch](https://github.com/ianarawjo/ChainForge) (`chainforge/react-server/src/EvalGen/`, [evalgen backend README](https://raw.githubusercontent.com/ianarawjo/ChainForge/main/chainforge/react-server/src/backend/evalgen/README.md)).

This is EvalGrill's closest intellectual neighbor — the academic proof-of-concept for "evaluate the evaluator."

**Workflow** (paper §3): a wizard on ChainForge's Multi-Eval node. (1) Criteria via **Infer** (LLM suggests from the prompt), **Manual**, or **Grade First** (grade ≥5 outputs before criteria generation). (2) Per-criterion toggle between code-based (Python) and LLM-based evaluators; an LLM streams multiple candidate assertion implementations per criterion. (3) **Grade-while-you-wait:** users thumbs-up/down whole outputs while candidates generate; a thumbs-up asserts the output passes *all* criteria, down-ranking any candidate assertion that fails it. (4) Sampling alternates between high- and low-confidence outputs using per-assertion selectivity estimates — their offline experiment showed random sampling produces high variance in resulting alignment (Appendix A.4). (5) **Report card:** per-criterion alignment with hover confusion matrices, plus set-level coverage and false-failure rate; best candidate per criterion selected subject to an FFR threshold (20% default).

**Exact metrics** (Appendix A.3), defined over *failures*, not passes:

- `Coverage(F)` = fraction of human-flagged-**bad** outputs failed by ≥1 assertion in set F
- `FFR(F)` = fraction of human-flagged-**good** outputs failed by ≥1 assertion
- `Alignment(F) = 2 · Coverage · (1 − FFR) / (Coverage + (1 − FFR))` — harmonic mean, "similar to F1 … but concerned with the precision and recall of *failures*, and with a *set*."

**Criteria drift** (§7.3.1): the paper's most-cited finding. Users face a catch-22 — they must externalize criteria to grade, but must grade to externalize criteria. Two drift types: adding new criteria upon seeing new *types* of bad outputs mid-grading (the UI forced a restart), and reinterpreting existing criteria to fit observed behavior. Conclusion: some criteria are dependent on the outputs observed and cannot be fully specified up front — evals need **continuous re-alignment, not one-shot authoring**.

Two study findings that directly validate EvalGrill's PRD, from 2024:

- Participant P3 demanded **per-criterion FFR thresholds**: "There are criteria where you can be okay with failing, and then there are other criteria where you are like, 'this must absolutely pass.'" That is the veto-vs-weighted distinction (PRD §5.4), empirically demanded and never productized.
- P4/P6 asked to **export assertions as portable unit tests / a Python file** — vendor-neutral export (PRD §5.7) as a documented unmet need.

**(a)** Design: partial — criteria elicitation relieved "writer's block" for 8/9 participants; no failure taxonomy, no dataset construction (assumes outputs exist). **(b)** Validate: yes, its core — but no reward-hacking, verbosity, or stability checks. **(c)** Execute: incidental. **(d)** Overlap: highest conceptual overlap of anything surveyed, but single-prompt-template, binary-criteria, GUI-bound, no coverage matrix, no difficulty tiers, no veto semantics. **(e)** Steal: the Alignment/Coverage/FFR formulas verbatim; failure-precision-recall framing; grade-while-you-wait; selectivity-weighted sampling; per-criterion confusion-matrix report card; per-criterion FFR thresholds as the formal basis for vetoes; criteria drift as a product requirement (versioned rubrics, add-failure-mode-mid-calibration without restart).

**Successors:** no "EvalGen 2" exists ([sh-reya.com/papers](https://www.sh-reya.com/papers/)). The line continued into:

- **SPADE** (VLDB 2024, co-authored with LangChain's Harrison Chase; [arXiv:2401.03038](https://arxiv.org/abs/2401.03038)): mines **prompt version deltas** as implicit criteria, then selects a minimal assertion set via ILP — minimize |F′| s.t. Coverage ≥ α and FFR ≤ τ. Includes a 9-category taxonomy of prompt-delta criteria (Response Format, Example Demonstration, Inclusion/Exclusion Instruction, Qualitative Criteria, …) derived from 19 real LangChain pipelines. Deployed inside LangSmith, "used to generate data quality assertions for over 2000 pipelines" (abstract). Steal: mining prompt/spec edit history as a source of unstated requirements; min-set-cover-under-FFR as coverage-matrix optimization.
- **ChainForge** itself ([github.com/ianarawjo/ChainForge](https://github.com/ianarawjo/ChainForge), MIT, ~3k stars, last push 2026-06-10): a prompt-testing GUI — mainly executes; low overlap except as EvalGen's delivery vehicle; single-maintainer pace.
- **DocETL / DocWrangler** ([arXiv:2410.12189](https://arxiv.org/abs/2410.12189), [arXiv:2504.14764](https://arxiv.org/abs/2504.14764)): pipeline optimization and the "gulf of specification" framing — design-thinking sources, not competitors.
- **PromptEvals** (NAACL 2025, [arXiv:2504.14738](https://arxiv.org/abs/2504.14738)): open dataset of 2,087 production prompts + 12,623 assertion criteria; fine-tuned open models beat GPT-4o at criteria generation by ~21%. Free grounding/training data for EvalGrill's criteria-suggestion step.

---

## 2. Other judge-alignment / rubric-calibration tools

### AlignEval (Eugene Yan)

Sources: [eugeneyan.com/writing/aligneval](https://eugeneyan.com/writing/aligneval/), [aligneval.com](https://aligneval.com/), [github.com/eugeneyan/align-app](https://github.com/eugeneyan/align-app) (no license, last push 2024-11-09 — dormant).

Gamified solo prototype: upload labeled CSV → **evaluation mode unlocks only after 20 human labels, optimize mode after 50** → write binary criteria → run LLM evaluator → score it against your labels with **recall, precision, F1, Cohen's κ, and TP/TN/FP/FN counts** → auto-optimize the judge prompt on a dev split with a **held-out test split** to catch overfitting. Its stance mirrors criteria drift independently: "It is impossible to completely determine evaluation criteria prior to human judging of LLM outputs."

(a) light; (b) **yes — the cleanest minimal implementation of judge-vs-human calibration**; (c) in-app only; (d) direct overlap with the calibration pillar, but unmaintained; (e) steal the 20-label unlock gate, Cohen's κ alongside F1 (chance-corrected agreement is more honest on skewed pass/fail data), and the held-out split for judge optimization. Notably, LangSmith credits this work — not the EvalGen paper — as the inspiration for Align Evals ([langchain.com/blog/introducing-align-evals](https://www.langchain.com/blog/introducing-align-evals)).

### EvalAssist (IBM Research)

Sources: [github.com/IBM/eval-assist](https://github.com/IBM/eval-assist) (Apache-2.0, last push 2026-04-09 — active), [docs](https://ibm.github.io/eval-assist/), [arXiv:2507.02186](https://arxiv.org/abs/2507.02186) (EMNLP 2025 demo).

Web UX for iteratively refining LLM-as-judge criteria in a "structured and portable format"; direct (rubric) and pairwise assessment; **positional-bias checking and certainty estimation** built into the evaluator library; **AI-assisted synthetic edge-case generation to stress-test criteria**; exports an auto-generated Unitxt notebook for bulk execution. (a) yes; (b) partial — real bias/certainty checks but no human-label alignment metric in the headline workflow; (c) hands off to Unitxt; (d) **the closest maintained open-source overlap with EvalGrill's design+validate positioning — the one to watch**; (e) steal the portable criteria format, the "refine in UI, export to executor" architecture, positional-bias as a stock check, and edge-case generation wired to criteria.

### Verdict (Haize Labs)

Sources: [github.com/haizelabs/verdict](https://github.com/haizelabs/verdict) (MIT, last push 2025-11-05), [arXiv:2502.18018](https://arxiv.org/abs/2502.18018).

Declarative library composing judges from Units → Layers → Pipelines with verification/debate/aggregation primitives. (a) no; (b) indirect — reliability via architecture, not calibration to your humans; (c) yes, it executes judging; (d) low overlap, natural downstream export target; (e) steal the idea that a **veto criterion deserves a more expensive judge architecture** (hierarchical verification/debate) than a weighted criterion — judge-time compute as a per-criterion design recommendation.

### EvalLM (KAIST, CHI 2024)

Source: [arXiv:2309.13633](https://arxiv.org/abs/2309.13633). Interactive criteria authoring with per-criterion comparative explanations; users produced more diverse criteria and examined 2× more outputs. No systematic human-label calibration (precisely EvalGen's critique of this class). Research prototype, no maintained line. Steal: per-criterion NL explanations as a criteria-refinement driver.

### Meta-evaluation benchmarks and 2026 academic work

- **JudgeBench** (ICLR 2025, [arXiv:2410.12784](https://arxiv.org/abs/2410.12784)) and **RewardBench** ([arXiv:2403.13787](https://arxiv.org/abs/2403.13787)) instantiate "rejects known-bad / accepts known-good" as benchmark methodology; strong judges barely beat random on subtle-but-verifiable failures. Steal: per-project mini-JudgeBenches — minimal pairs where the rejected item is wrong for a known, subtle reason mapped to a failure mode — as the standard smoke test for any judge EvalGrill validates.
- **RADAR** ([arXiv:2608.01810](https://arxiv.org/abs/2608.01810), Aug 2026): probe-based **criterion coupling/redundancy audit** — criteria that are semantically distinct but behaviorally coupled distort aggregate scores. Directly relevant: EvalGrill's coverage matrix should audit the criterion axis for redundancy, not just failure-mode coverage.
- Rubrics survey ([arXiv:2606.08625](https://arxiv.org/abs/2606.08625)): three-tier rubric framework + reliability threat catalog; useful citation map. (Related 2026 items surfaced but not verified in this pass: CriterAlign, "From Rubrics to Reliable Scores.")

---

## 3. promptfoo

Sources: [github.com/promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) (MIT, ~24k stars, very active), [assertions overview](https://www.promptfoo.dev/docs/configuration/expected-outputs/), [model-graded](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/), [llm-rubric](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/), [dataset generation](https://www.promptfoo.dev/docs/configuration/datasets/), [CLI](https://www.promptfoo.dev/docs/usage/command-line/), [LLM-as-judge guide](https://www.promptfoo.dev/docs/guides/llm-as-a-judge/), [vulnerability types](https://www.promptfoo.dev/docs/red-team/llm-vulnerability-types/), [red team](https://www.promptfoo.dev/docs/red-team/), [web UI](https://www.promptfoo.dev/docs/usage/web-ui/).

Config-driven eval runner with two assertion families (deterministic + model-graded: `llm-rubric`, `factuality`, `g-eval`, `agent-rubric`, etc.), weights, `assert-set` groups with pass-proportion thresholds, named metric tags, and derived metrics. Dataset generation is persona-based volume synthesis (`promptfoo generate dataset --numPersonas ... --instructions ...`); `promptfoo generate assertions` exists. Red-team side has a real hierarchical failure taxonomy: 12 top-level categories → 150+ plugins with stable IDs, each annotated for applicability to RAG vs agent vs chatbot architectures.

**Calibration:** documented but not tooled. The official LLM-as-judge guide prescribes a 6-step workflow — golden set of 30–50 human-labeled examples, judge-vs-human agreement target >90%, holdout validation to catch rubric overfitting, weekly drift monitoring — but the agreement measurement is literally shown as `jq` commands. The web viewer supports human ratings that override automatic grading and persist into exports. The guide names verbosity/position/self-preference/authority biases and a 3-layer judge prompt-injection defense.

**(a)** Partial — real taxonomy but security/safety-domain only, not task-quality failures; generation is volume synthesis, not boundary-case/difficulty-tier methodology; no coverage matrix. **(b)** Guidance-only; nothing computes agreement, kappa, or coverage. **(c)** Yes — core. **(d)** Highest overlap among OSS runners: taxonomy, generation, and calibration *documentation* all adjacent; the gap is that promptfoo documents the calibration process and ships no tooling for it. **(e)** Steal: `{reason, score, pass}` structured grader output (pass-bool vs weighted-score is a half-formed veto distinction); plugin-ID scheme with per-architecture applicability flags; the 30–50-example → >90% agreement → holdout → drift-monitor recipe as *the calibration UX to automate*; the 4-bias table as concrete evaluate-the-evaluator checks.

---

## 4. OpenAI Evals (classic repo + platform)

Sources: [github.com/openai/evals](https://github.com/openai/evals), [eval-templates.md](https://github.com/openai/evals/blob/main/docs/eval-templates.md), [platform evals guide](https://developers.openai.com/api/docs/guides/evals), [graders guide](https://developers.openai.com/api/docs/guides/graders), [evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices), [Datasets getting started](https://developers.openai.com/api/docs/guides/evaluation-getting-started).

Classic repo: effectively maintenance mode (last push Apr 2026; README redirects to the dashboard). Its `ModelBasedClassify` YAML (`choice_strings` + `choice_scores` + `eval_type: cot_classify`) is the ancestor of promptfoo's `factuality` and Braintrust's classifiers. Platform Evals product: **deprecated — read-only Oct 31, 2026, shutdown Nov 30, 2026**. Graders include `string_check`, `text_similarity`, `score_model`, `label_model`, `python`, and compositional `multigraders` with a `calculate_output` formula; the API has grader **validation endpoints** (config dry-runs), and the guide warns about "grader hacking" (reward exploitation) — advice, not tooling. The successor "Datasets" surface builds in human annotation (Good/Bad, critiques, SME emphasis). The best-practices doc preaches edge/adversarial case mixes and judge calibration "until it consistently agrees with human annotations."

**(a)** Prose guidance only. **(b)** Thin — validation endpoints + advice. **(c)** The execution product is dying. **(d)** Low and shrinking; the overlap is rhetorical — OpenAI's docs now preach EvalGrill's thesis without shipping the layer. Market-gap validation, not competition. **(e)** Steal: the minimal portable rubric YAML format; `multigraders` compositional aggregation; "dry-run your grader" as an API shape; and the deprecation itself — EvalPack should offer an import path for orphaned OpenAI eval registry YAML/JSONL and platform eval configs.

---

## 5. Inspect AI (UK AI Security Institute)

Sources: [inspect.aisi.org.uk](https://inspect.aisi.org.uk/), [scorers](https://inspect.aisi.org.uk/scorers.html), [model-graded](https://inspect.aisi.org.uk/model-graded.html), [scoring](https://inspect.aisi.org.uk/scoring.html), [scanners](https://inspect.aisi.org.uk/scanners.html), [human agent](https://inspect.aisi.org.uk/human-agent.html), [github.com/UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai) (active), [inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals).

Research-grade execution framework: datasets/solvers/scorers/tasks, sandboxed agents, eval sets, log viewer, 200+ prebuilt evals. Model-graded scorers support multi-model majority voting, injection-hardened grade extraction, `partial_credit`, and a `model_role: "grader"` indirection. Human features: a **human agent** for baselining (humans work in the identical dataset/sandbox/scorer configuration as models, with session recording) and score editing / re-scoring of logs.

**Scanners** are the standout: a separate artifact class that reviews transcripts for "issues that may undermine the results (e.g. refusals, evaluation awareness, environment misconfiguration, runtime errors, reward hacking)" — sparse findings stored apart from scores, run online or offline via `scout scan`. This is the closest shipped *concept* to evaluate-the-evaluator, but it targets **run integrity**, not judge quality: no judge-vs-human agreement metrics, no coverage auditing anywhere in the docs.

**(a)** No — assumes you arrive with dataset and criteria. **(b)** Partial — strongest run-integrity story of any runner. **(c)** Yes — core. **(d)** Moderate but complementary; the ideal downstream execution target for an EvalPack. **(e)** Steal: the Scanners concept wholesale (named integrity checks as a separate artifact class — government-safety-institute-tested vocabulary for EvalGrill's audit outputs); `model_role` indirection for vendor-neutral judge protocols; `grade_pattern` + temperature/seed pinning as "stable judgments" checklist items; the human-baseline symmetry principle for EvalGrill's human-review guide.

---

## 6. DeepEval (Confident AI)

Sources: [github.com/confident-ai/deepeval](https://github.com/confident-ai/deepeval) (Apache-2.0, ~17.5k stars, very active), [G-Eval](https://deepeval.com/docs/metrics-llm-evals), [DAG](https://deepeval.com/docs/metrics-dag), [Synthesizer](https://deepeval.com/docs/synthesizer-introduction), [LLM-as-judge guide](https://deepeval.com/guides/guides-llm-as-a-judge), [DeepTeam](https://www.trydeepteam.com/docs/red-teaming-introduction), [Confident AI docs](https://www.confident-ai.com/docs), [datasets](https://deepeval.com/docs/evaluation-datasets), [benchmarks](https://deepeval.com/docs/benchmarks-introduction).

The highest feature-level overlap of any OSS framework:

- **G-Eval**: natural-language `criteria` → auto-generated chain-of-thought `evaluation_steps` (freezable for reproducibility), token-probability-weighted 1–5 scoring, optional `Rubric(score_range, expected_outcome)` objects with enforced non-overlapping bands, `strict_mode` for binary.
- **DAG metric**: deterministic decision-tree judge — `TaskNode` (extract evidence) → `BinaryJudgementNode` / `NonBinaryJudgementNode` → verdicts carrying hard scores or `then`-chains into a `GEval` leaf. This is PRD §5.3 ("deterministic checks before LLM judges") already shipped as a metric grammar.
- **Synthesizer**: goldens from docs/contexts/scratch/augmentation, with a critic-model filtration gate (`FiltrationConfig`), seven evolution types (REASONING, CONSTRAINED, COMPARATIVE, …) with probability distributions and depth — real dataset-construction machinery, though volume-oriented, not failure-mode-coverage-oriented.
- **DeepTeam** (split-out red teaming): 40+ vulnerabilities, 10+ attack methods — a security failure taxonomy.

**The crucial finding:** DeepEval's official LLM-judge guide has a section "Validate LLM Judges with Human Annotations" framing validation as a confusion matrix (with the warning that false positives create false confidence) and a remediation loop (tighten criteria → explicit steps → threshold → strict mode → split into DAG). But the **tooling lives in the paid Confident AI platform** — Annotation Queues with "Eval Alignment" and "Error Analysis" subsections, per-metric agreement, FP/FN reporting, a ~95% alignment-rate target ([confident-ai.com/docs](https://www.confident-ai.com/docs), [HITL blog](https://www.confident-ai.com/blog/human-in-the-loop-ai-agent-evaluation)). The OSS library has no calibration harness, no coverage audit, no reward-hacking checks.

**(a)** Partial. **(b)** Doctrine in OSS, implementation SaaS-gated. **(c)** Yes — core (pytest-style runner, 40+ metrics). **(d)** Highest feature overlap; EvalGrill's openings against it: OSS judge calibration, coverage matrices, anti-reward-hacking checks, vendor-neutral export (goldens push to their cloud; no portable eval-pack format). **(e)** Steal: the criteria → auto-steps → frozen-steps authoring progression; `Rubric` score bands; the DAG node vocabulary as a grammar for "vetoes before weighted judgment"; the FP/FN-asymmetry framing and ≥95% alignment target; the critic-model quality gate on synthetic data.

---

## 7. Braintrust (Loop, autoevals)

Sources: [autoevals](https://github.com/braintrustdata/autoevals), [Loop docs](https://www.braintrust.dev/docs/guides/loop), [Loop launch](https://www.braintrust.dev/blog/loop) (Nov 2025), [human review](https://www.braintrust.dev/docs/guides/human-review), [golden datasets blog](https://www.braintrust.dev/blog/human-review-golden-datasets) (May 2026), [scorer best practices](https://www.braintrust.dev/docs/best-practices/scorers), [playground](https://www.braintrust.dev/docs/guides/playground), [changelog](https://www.braintrust.dev/docs/changelog), [HITL article](https://www.braintrust.dev/articles/human-in-the-loop-evals-for-llm-apps).

- **autoevals**: portable scorer library; `LLMClassifier` = prompt template + `choice_scores` map + optional `use_cot` — the de-facto lingua franca for rubric-as-classifier. No rubric validation, no veto semantics; everything collapses to 0–1.
- **Loop** (Nov 2025, actively developed through Aug 2026): in-product agent that answers "What are the common failure modes of my agent?", generates scorers from observed failure patterns, and generates/augments dataset rows from logs. This is a compressed, automated, **bottom-up** version of EvalGrill's failure-first pipeline — mined from logs rather than derived from "what failure is unacceptable." Loop's "Optimize" button is **prompt** optimization from human annotations; per the docs and changelog through Aug 2026, **no feature optimizes a scorer against human labels or computes judge-vs-human agreement**.
- **Human review**: categorical/continuous scores, conditional score display via SQL filters, multi-reviewer independent scoring (June 2026), and a codified workflow with **tiered queues — triage, SME (fills `expected`), and a calibration queue where multiple reviewers periodically score the same items** (inter-rater calibration). Judge↔human calibration itself remains a documented manual practice ("compare automated scores with human scores … refine the scorer prompt"), not a product feature.
- Playground supports "scorers as tasks" — iterate on a judge as the system-under-test, but with eyeball-only validation, no alignment metric.

**(a)** Partial and increasing — Loop is real design assistance, log-mined not failure-first. **(b)** Weakest pillar: no alignment metric, no coverage audit, no bias/reward-hacking checks in any primary source. **(c)** Yes — core (Eval SDK, experiments, Brainstore observability). **(d)** **Loop is the encroachment vector**; everything Loop produces lives in Braintrust (only autoevals code is portable), and their own articles already sell the calibration workflow narratively — expect them to close the gap. **(e)** Steal: `LLMClassifier` as an EvalPack export format; SQL-gated conditional rubric display for hierarchical rubrics; the calibration queue (evaluate the *human* evaluator); "scorers as tasks"; `expected`-field hygiene rules.

---

## 8. LangSmith (Align Evals, openevals)

Sources: [Align Evals blog](https://www.langchain.com/blog/introducing-align-evals) (Jul 29, 2025), [Align Evals docs](https://docs.langchain.com/langsmith/improve-judge-evaluator-feedback), [few-shot evaluators](https://docs.langchain.com/langsmith/create-few-shot-evaluators), [annotation queues](https://docs.langchain.com/langsmith/annotation-queues), [dataset management](https://docs.langchain.com/langsmith/manage-datasets-in-application), [openevals](https://github.com/langchain-ai/openevals), [agentevals](https://github.com/langchain-ai/agentevals), [changelog](https://changelog.langchain.com/announcements/introducing-align-evals-streamlining-llm-application-evaluation).

- **Align Evals** — **the single closest shipped feature to EvalGrill's judge-calibration pillar**, live 13+ months. Workflow: select criteria → human-label representative good+bad outputs into a golden set via annotation queues (docs recommend ≥20 examples, balanced) → Evaluator Playground → "Start Alignment" runs the judge over labeled examples → **alignment score = percent of examples where judge matches human**, side-by-side human/LLM scores sorted by disagreement, hover-to-see judge reasoning, **saved baseline alignment score for before/after comparison**. Launch roadmap (alignment analytics over time, automatic judge-prompt optimization) not yet shipped per changelog.
- **Few-shot correction injection**: human corrections auto-accumulate in a dataset and are injected into the judge prompt via a `{{Few-shot examples}}` variable (default 5, with explanations) — continuous judge repair from ongoing disagreement; arguably more threatening than the one-shot Align flow.
- **openevals** ([repo](https://github.com/langchain-ai/openevals)): `create_llm_as_judge` with `continuous` vs `choices`, `few_shot_examples`, `output_schema`; large prebuilt prompt catalog (correctness, hallucination, RAG groundedness, PII, injection…). Release cadence slower (last tagged 0.2.0, Apr 2025). **agentevals**: trajectory-match evaluators — prior art for agent-process rubrics.
- Annotation queues support pairwise A/B/Equal review with keyboard shortcuts, multi-reviewer flows, auto-enqueue rules. Datasets have splits, schema validation, and "Add AI-Generated Examples" (thin synthesis).

**What Align Evals does NOT cover** (the boundary of the encroachment): the metric is naive percent agreement — no kappa/chance correction, no per-class precision/recall or FP-vs-FN asymmetry; no reward-hacking/verbosity/position probes; no judge stability testing; no known-bad/known-good canary suites; no coverage auditing; no veto semantics (feedback keys are flat scores); and the calibrated judge is a LangSmith-resident prompt — no portable export.

**(a)** Barely. **(b)** Yes — Align Evals occupies the calibration pillar. **(c)** Yes — core. **(d)** Direct overlap on calibration; EvalGrill's defensible ground is everything Align Evals ignores (taxonomy, coverage, vetoes, adversarial judge checks, honest statistics, portability). **(e)** Steal: the entire Align Evals UX loop (baseline-vs-current score, disagreement-sorted side-by-side, one-button alignment) and beat the metric; the ≥20-balanced-examples floor and anti-overfitting warning; `{{Few-shot examples}}` correction injection **as a portable artifact instead of a platform-locked one**; pairwise queues with keyboard shortcuts.

---

## 9. Phoenix (Arize)

Sources: [github.com/Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) (Elastic License 2.0 — not OSI-approved; very active, evals v3.4.0 released 2026-08-08), [pre-built metrics](https://arize.com/docs/phoenix/evaluation/pre-built-metrics), [pre-tested evals](https://arize.com/docs/phoenix/evaluation/running-pre-tested-evals), [evals library](https://arize-phoenix.readthedocs.io/projects/evals/), [datasets & experiments](https://arize.com/docs/phoenix/datasets-and-experiments/overview-datasets), [annotations](https://arize.com/docs/phoenix/tracing/how-to-tracing/feedback-and-annotations/annotating-in-the-ui), [LibreEval](https://arize.com/llm-hallucination-dataset/).

Tracing-first observability plus an evals library (`create_classifier` with label→score choice maps, structured `Score{label, score, explanation, direction}` objects). Its signature claim: **"All LLM evaluation templates are tested against golden datasets and achieve an F1 score of 85% or higher"** ([docs](https://arize.com/docs/phoenix/evaluation/pre-built-metrics)). The in-repo benchmark harness ([js/benchmarks/evals-benchmarks](https://github.com/Arize-ai/phoenix/blob/main/js/benchmarks/evals-benchmarks/src/aggregateMetrics.ts)) organizes golden examples **by failure category** (e.g. `contradicts_conversation`, `fabricated_specifics`) and gates on **macro precision/recall/F1**, with an explicit comment that per-case accuracy "is blind to class imbalance — a judge that always predicts the majority label can pass it." Evaluator templates are versioned YAML configs with a `<rubric>` block, per-label definitions, numbered decision rules, an **explicit out-of-scope list**, an uncertainty tie-break default, and a `choices` map ([example config](https://github.com/Arize-ai/phoenix/blob/main/prompts/classification_evaluator_configs/HALLUCINATION_CLASSIFICATION_EVALUATOR_CONFIG.yaml)). Annotations carry `annotator_kind: HUMAN | LLM | CODE`, shown side-by-side, exportable to datasets for "building a human-aligned eval" — the raw material for agreement, but **Phoenix computes no alignment metric for users**.

**(a)** Minimal. **(b)** Partial but **inverted**: Phoenix validates *its* judges against *its* goldens, vendor-side; EvalGrill validates *your* judges against *your* humans. **(c)** Yes — core. **(d)** The "benchmarked templates" story overlaps evaluate-the-evaluator rhetorically; ELv2 licensing strengthens the vendor-neutral EvalPack angle. **(e)** Steal: the YAML evaluator-config format (best rubric serialization any vendor ships — a strong EvalPack rubric-schema starting point); failure-category-organized benchmark suites (a coverage matrix in embryo); the macro-P/R/F1-over-accuracy insight verbatim; `annotator_kind` as a first-class field; per-template benchmark report cards as a trust signal EvalGrill can make *user-generated*.

---

## 10. Where EvalGrill's positioning is genuinely open vs merely asserted

### Genuinely open (no shipped competitor, confirmed against primary sources)

1. **Failure-first taxonomy as the entry point for quality evals.** The only shipped taxonomies are security/safety-domain (promptfoo red-team plugins, DeepTeam vulnerabilities). Nobody ships tooling that starts from "what failure would make this system unacceptable" and derives criteria/datasets for *task-quality* failures. Braintrust Loop mines failure modes bottom-up from logs — powerful, but it cannot see failures that haven't happened yet, which is exactly what boundary cases and adversarial tiers are for.
2. **Coverage matrices (failure mode × tasks × criteria × calibration cases).** Zero instances anywhere. The nearest artifacts are SPADE's ILP (assertion-set selection under coverage constraints) and Phoenix's failure-category benchmark suites — both fragments, neither productized as an audit.
3. **Veto-vs-weighted rubric semantics.** Demanded by an EvalGen study participant in 2024 ("this must absolutely pass"), half-present in promptfoo's pass-bool-vs-score, absent as a first-class concept everywhere. All platforms collapse everything to 0–1 weighted scores.
4. **Reward-hacking / verbosity / position / stability probes as product features.** Universally *named* in official guidance (promptfoo's bias table, OpenAI's "grader hacking," DeepEval's judge-bias notes, Inspect's Scanners rationale) and shipped by nobody as checks a user can run against their own rubric+judge. Inspect's Scanners are the closest, but audit *transcripts of runs*, not the evaluation design.
5. **Vendor-neutral, version-controllable eval-design artifact (EvalPack).** EvalGen participants asked for export in 2024; LangSmith's calibrated judges are platform-resident prompts; Braintrust Loop's outputs live in Braintrust; DeepEval goldens push to Confident AI; Phoenix is ELv2. Portability of the *whole design* — taxonomy + dataset + rubric + calibration evidence — is unoccupied. (Portability of scorer *code* alone is NOT differentiating: autoevals and openevals are already open source.)
6. **Statistically honest calibration for open-source users.** The one shipped calibration product (Align Evals) uses naive percent agreement. Nobody ships Cohen's κ, macro-F1, FP/FN asymmetry, or EvalGen's failure-oriented Coverage/FFR/Alignment in a user-facing loop. DeepEval documents the right math and gates it behind SaaS.

### Merely asserted (competitors already there or one step away)

1. **"Judge calibration against human labels" as a headline.** LangSmith Align Evals has shipped it for 13+ months with a polished UX (golden set, alignment score, baseline comparison, disagreement sorting, few-shot correction injection). Confident AI sells it (Eval Alignment queues). If EvalGrill's calibration story is "percent agreement + iterate the prompt," it already exists. The differentiated claim must be the *quality* of calibration (failure-oriented metrics, per-criterion confusion matrices, veto recall, adversarial probes) plus portability.
2. **"Generate evals from failures."** Braintrust Loop already answers "what are my agent's failure modes?" and generates scorers and dataset rows from them. EvalGrill's version must be visibly different: top-down (unacceptable-failure-first), provenance-tracked, coverage-audited — not just another generator (PRD Risk 1 is real).
3. **"Dataset construction tooling."** DeepEval's Synthesizer (evolutions, critic filtration, styling) and promptfoo's generators are substantial. EvalGrill's edge is not generation machinery but the *methodology binding*: every generated case tagged REAL/DERIVED/SYNTHETIC/ADVERSARIAL, mapped to a failure mode, and audited for coverage.
4. **"Evaluate the evaluator" as vocabulary.** Inspect's Scanners (a UK government safety institute product) already own adjacent vocabulary — refusals, evaluation awareness, reward hacking — for run integrity. EvalGrill must be precise that its target is the *evaluation design* (rubric+judge+dataset), pre-execution, or the claim will blur into what Inspect already does.

---

## 11. Sharpest differentiation risks

### Risk 1 — LangSmith and Braintrust converge on the full loop from both ends (highest probability, highest impact)

LangSmith has the calibration pillar (Align Evals) and announced alignment analytics + automatic judge-prompt optimization at launch ([blog](https://www.langchain.com/blog/introducing-align-evals)); Braintrust has the generation pillar (Loop) and narrates manual judge-vs-human calibration in its own articles with monthly human-review investment through mid-2026 ([changelog](https://www.braintrust.dev/docs/changelog)). Each is one roadmap item from the other's half, with production data flywheels EvalGrill will never have. **Defense:** occupy what platform incentives ignore — cross-platform portability (platforms are structurally disincentivized to make eval designs portable), statistically honest calibration, coverage auditing, veto semantics — and export *to* them rather than compete on execution. Speed matters: the calibration-only window is closing.

### Risk 2 — "Validation" collapses into a feature, not a product

The pattern across every neighbor is that design/validation ships as a *feature of an execution platform* (Align Evals, Loop, Eval Alignment queues, Scanners) or as *documentation* (promptfoo, OpenAI). The implicit market judgment: teams do eval design where their traces already live. EvalGrill asserts the layer deserves a standalone product; no surviving standalone proves it — AlignEval is dormant, EvalGen lives in a research GUI, and IBM's EvalAssist (the closest maintained analog to the standalone design+validate+export architecture) has ~100 stars. **Defense:** the skill-first/CLI form factor (meet engineers in their repo, not another dashboard), EvalPack as a git-versionable artifact, and the OpenAI Evals shutdown (Nov 2026) as concrete evidence that platform-resident eval assets are a liability worth insuring against.

### Risk 3 — DeepEval commoditizes the pieces before EvalGrill assembles the whole

DeepEval already ships, in OSS with ~17.5k stars: deterministic-before-LLM judging (DAG), rubric score bands (G-Eval `Rubric`), dataset synthesis with quality gates (Synthesizer), and documentation of the exact confusion-matrix calibration EvalGrill plans — gated behind their SaaS today, but a single OSS release away. If judge calibration lands in the free library, EvalGrill's remaining OSS wedge is taxonomy + coverage + vetoes + reward-hacking audits + portability. **Defense:** make the *validated bundle* the product — the coverage matrix and audit report tying taxonomy, dataset, rubric, and calibration evidence together is what no metric library can offer piecemeal — and publish EvalGen-grade metrics (Coverage/FFR/Alignment, κ, per-criterion confusion matrices) from day one so the calibration is credibly deeper, not just present.

---

## 12. Consolidated "worth stealing" shortlist

| Steal | From | Why |
|---|---|---|
| `Alignment = 2·Cov·(1−FFR)/(Cov+(1−FFR))`, Coverage/FFR over *failures* | EvalGen ([arXiv:2404.12272](https://arxiv.org/abs/2404.12272) App. A.3) | The right headline calibration metric family; PRD §15 should adopt it |
| Per-criterion FFR thresholds | EvalGen study (P3) | Formal basis for veto conditions |
| Criteria drift as product requirement (add failure modes mid-calibration; versioned rubrics; re-calibration triggers) | EvalGen §7.3.1 | Prevents one-shot-authoring design errors |
| Grade-while-you-wait + selectivity-weighted sampling | EvalGen §3 | Calibration UX; random sampling has high alignment variance |
| 20-label unlock gate; Cohen's κ; held-out split for judge optimization | AlignEval ([eugeneyan.com](https://eugeneyan.com/writing/aligneval/)) | Honest, cheap calibration defaults |
| Baseline-vs-current alignment score, disagreement-sorted side-by-side view | LangSmith Align Evals ([docs](https://docs.langchain.com/langsmith/improve-judge-evaluator-feedback)) | The UX bar to match, with better metrics |
| `{{Few-shot examples}}` correction injection — as a portable artifact | LangSmith ([docs](https://docs.langchain.com/langsmith/create-few-shot-evaluators)) | Turns disagreements into judge improvements |
| YAML evaluator config: `<rubric>` + per-label definitions + decision rules + out-of-scope list + tie-break default + choices map | Phoenix ([example](https://github.com/Arize-ai/phoenix/blob/main/prompts/classification_evaluator_configs/HALLUCINATION_CLASSIFICATION_EVALUATOR_CONFIG.yaml)) | Best shipped rubric serialization; EvalPack rubric.yaml starting point |
| Macro P/R/F1 gates ("accuracy is blind to class imbalance") | Phoenix ([aggregateMetrics.ts](https://github.com/Arize-ai/phoenix/blob/main/js/benchmarks/evals-benchmarks/src/aggregateMetrics.ts)) | Judge-calibration reporting rule |
| Scanners: named integrity checks as separate artifact class (refusals, eval awareness, reward hacking) | Inspect ([scanners](https://inspect.aisi.org.uk/scanners.html)) | Vocabulary + architecture for the audit outputs |
| `model_role: "grader"` indirection; seed/temperature pinning | Inspect ([model-graded](https://inspect.aisi.org.uk/model-graded.html)) | Vendor-neutral judge protocol |
| DAG node grammar (TaskNode → JudgementNodes → verdict/`then` chains) | DeepEval ([DAG](https://deepeval.com/docs/metrics-dag)) | Shipped grammar for "deterministic before LLM, vetoes before weights" |
| `criteria → auto evaluation_steps → frozen steps`; `Rubric(score_range, expected_outcome)` | DeepEval ([G-Eval](https://deepeval.com/docs/metrics-llm-evals)) | Rubric-authoring progression |
| 30–50 golden labels → >90% agreement → holdout → drift monitor (automate it) | promptfoo ([guide](https://www.promptfoo.dev/docs/guides/llm-as-a-judge/)) | The documented recipe nobody tooled |
| Plugin IDs with per-architecture applicability flags | promptfoo ([taxonomy](https://www.promptfoo.dev/docs/red-team/llm-vulnerability-types/)) | Failure-taxonomy schema pattern |
| `LLMClassifier` (template + choice_scores + use_cot) and openevals `create_llm_as_judge` params | Braintrust ([autoevals](https://github.com/braintrustdata/autoevals)), LangSmith ([openevals](https://github.com/langchain-ai/openevals)) | Priority EvalPack export targets |
| Calibration queue (periodic multi-reviewer overlap); SQL-gated conditional rubric display | Braintrust ([golden datasets](https://www.braintrust.dev/blog/human-review-golden-datasets), [human review](https://www.braintrust.dev/docs/guides/human-review)) | Evaluate the *human* evaluator; hierarchical rubrics |
| Known-bad minimal pairs per failure mode (mini-JudgeBench) | JudgeBench ([arXiv:2410.12784](https://arxiv.org/abs/2410.12784)) | Standard smoke test for validated judges |
| Prompt-delta mining; min-assertion-set ILP under Coverage/FFR | SPADE ([arXiv:2401.03038](https://arxiv.org/abs/2401.03038)) | Requirements source + coverage optimization |
| Criterion-coupling audit via synthetic probes | RADAR ([arXiv:2608.01810](https://arxiv.org/abs/2608.01810)) | Coverage matrix should audit criterion redundancy too |
| Portable criteria format + refine-then-export-to-executor architecture; positional-bias check | EvalAssist ([repo](https://github.com/IBM/eval-assist)) | Closest maintained analog — learn from and track it |
| Import path for orphaned OpenAI eval configs | OpenAI deprecation ([guide](https://developers.openai.com/api/docs/guides/evals)) | Concrete portability proof point, deadline Nov 2026 |
