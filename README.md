<h1 align="center">EvalGrill</h1>

<p align="center"><b>Turn real AI agent failures into trustworthy evals — then prove the eval works.</b></p>

<p align="center">
<a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
<a href="#quickstart"><img src="https://img.shields.io/badge/Claude%20Code-plugin-d97757.svg" alt="Claude Code plugin"></a>
</p>

Most eval tooling assumes you already have a good eval. EvalGrill is the layer before that: it turns evidence of real agent failures into a portable, validated **EvalPack** (failure taxonomy, dataset, rubric, calibration, coverage), the test cases that decide which agent is actually better. Platforms like Braintrust, LangSmith, and Phoenix then execute it.

[Quickstart](#quickstart) · [The four phases](#the-four-phases) · [What validation catches](#what-validation-catches) · [Exporters](#exporters) · [Demo Corpus](#demo-corpus) · [Repository structure](#repository-structure) · [Development](#development)

## Why

- **Failure-first design.** Every failure mode starts from evidence of something actually going wrong (failed outputs, complaints, domain rules), never from a generic quality checklist.
- **The eval itself gets tested.** Coverage audits, rubric defect checks, and judge calibration against human labels prove the eval catches what it claims before anything trusts its scores.
- **Calibration with EvalGen alignment metrics.** Judge-vs-human Coverage, False Failure Rate, and Alignment, plus stability probes: run-to-run disagreement, pairwise order sensitivity, and reward-hacking candidates.
- **Vetoes and portability.** Zero-tolerance criteria gate the final result on every platform, compiled into each exporter since no platform ships native veto semantics.

## Quickstart

Requires [Claude Code](https://claude.com/claude-code) ≥ 2.1.216 and [uv](https://docs.astral.sh/uv/).

Install from inside any Claude Code session:

```
/plugin marketplace add hardness1020/EvalGrill
/plugin install evalgrill@evalgrill-dev
```

Or, to hack on it, clone and load in place:

```bash
git clone https://github.com/hardness1020/EvalGrill
cd EvalGrill
claude --plugin-dir .
```

Then inside the session:

```
/evalgrill                # report EvalPack status, route to the right phase
/evalgrill analyze        # or jump to a phase directly
```

For the dev loop (`/reload-plugins`, validation, sandbox notes), see [CONTRIBUTING.md](CONTRIBUTING.md).

## The four phases

`/evalgrill` routes work through four skills; each phase produces canonical artifacts validated by a bundled script.

| Phase | Skill | Produces |
|---|---|---|
| 1. Analyze | `analyze-eval-problem` | `failure-taxonomy.yaml`, `evaluation-dimensions.yaml`: grounded failure modes with severity and provenance |
| 2. Dataset | `build-eval-dataset` | `dataset.jsonl`, `dataset-card.md`: tasks engineered to expose the failure modes |
| 3. Rubric | `design-eval-rubric` | `rubric.yaml`, `judge-protocol.yaml`, `human-review-guide.md`: checkable criteria with observable anchors and vetoes |
| 4. Validate | `validate-eval-design` | coverage audit, calibration report, lifecycle status: the detection engine |

Every artifact conforms to the JSON Schemas in [`schemas/`](schemas/), and scripts are single-file PEP 723 scripts run via `uv run`: no Python environment setup.

## What validation catches

The validate phase runs seven deterministic detections (PRD §30):

1. High-severity failure mode with zero task coverage
2. Vague rubric criterion (no observable anchors)
3. Criterion marked judge-scored that a script could check deterministically
4. Missing veto where a zero-tolerance domain rule demands one
5. Judge disagreement across repeated runs
6. Pairwise order sensitivity (position bias)
7. Calibration failure: judge verdicts contradicting human labels, including reward-hacking candidates that game the judge

Judging runs through a provider-agnostic **Judge Runner**. The default shells out to `claude -p` with JSON-schema-validated verdicts; a scripted replay runner makes every detection deterministic in CI.

## Exporters

One validated EvalPack exports to all three platforms. Each export is a static, self-contained tree (`eval_pack.py` + `pack_data.json`) with one evaluator per criterion and the veto/essential gate compiled into a `final_result` scorer.

| Platform | Target packages | Veto semantics |
|---|---|---|
| [Braintrust](https://braintrust.dev) | `braintrust`, `autoevals` | generated composite scorer |
| [LangSmith](https://smith.langchain.com) | `langsmith`, `openevals` | client-side composite evaluator |
| [Phoenix](https://phoenix.arize.com) | `arize-phoenix-client`, `arize-phoenix-evals` | compiled code evaluator |

Offline contract tests cover each exporter on every PR; live golden-path smokes (export → dataset → evaluate → read scores back) run on dispatch/release.

## Demo Corpus

[`demo/`](demo/README.md) ships a fully hand-authored, fictional pilot (the NR-7 sleep-claim corpus): 13 sources, 10 tasks, 16 human-labeled candidates including reward-hacking plants, plus a golden EvalPack and a deliberately flawed draft rubric with all seven detections planted. It is both the acceptance bar and a worked example of what an EvalPack looks like.

> ⚠️ The defects in `demo/golden-pack/fixtures/` are intentional. Do not fix them; they are the test.

## Repository structure

The repo root is the Claude Code plugin (`.claude-plugin/plugin.json`):

```
skills/            /evalgrill router + four phase skills
scripts/           uv/PEP 723 scripts: checks, audit, exporters
schemas/           canonical EvalPack JSON Schemas
demo/              NR-7 Demo Corpus + committed golden EvalPack
tests/             §30 acceptance run + exporter/runner contract tests
integrations/      per-harness install docs (claude-code, codex)
docs/adr/          architecture decision records
```

## Development

```bash
claude plugin validate . --strict                                  # marketplace manifest
uv run scripts/check_pack.py demo/golden-pack                      # schema + referential integrity
uv run scripts/audit_pack.py demo/golden-pack --runner replay      # all seven detections
uv run tests/acceptance_30.py                                      # the full §30 done-bar
```

CI: [`contract.yml`](.github/workflows/contract.yml) (offline, every PR), [`acceptance.yml`](.github/workflows/acceptance.yml) (offline §30 run), [`live-smoke.yml`](.github/workflows/live-smoke.yml) (live platform golden paths, dispatch/release), [`release.yml`](.github/workflows/release.yml) (tag/version/[CHANGELOG](CHANGELOG.md) drift, on `v*` tags).

Contributions welcome: [CONTRIBUTING.md](CONTRIBUTING.md) has the full offline checklist.

## Further reading

- [awesome-agent-architecture · 23 · Evaluation](https://github.com/hardness1020/awesome-agent-architecture/tree/main/sections/23-evaluation): the agent-evaluation study behind this project, on why measuring agents takes more than scoring transcripts.

## License

[Apache-2.0](LICENSE)
