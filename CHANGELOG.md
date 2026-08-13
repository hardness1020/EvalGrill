# Changelog

Hand-written, one section per release, newest first. A release is a git tag `v<version>` whose `<version>` matches `.claude-plugin/plugin.json`; [`release.yml`](.github/workflows/release.yml) fails the tag on drift or on a missing section here.

## 0.1.0

Initial dogfood release.

- `/evalgrill` router plus four phase skills: `analyze-eval-problem`, `build-eval-dataset`, `design-eval-rubric`, `validate-eval-design`.
- Canonical EvalPack JSON Schemas in `schemas/`; per-phase self-checks and `check_pack.py` referential integrity.
- Seven-detection validation engine (`audit_pack.py`): coverage gaps, vague criteria, script-checkable criteria, missing vetoes, run-to-run disagreement, order sensitivity, calibration failure incl. reward-hacking candidates.
- Provider-agnostic Judge Runner: `claude -p` by default (claude-sonnet-5, medium effort), scripted replay runner for deterministic CI.
- Exporters for Braintrust, LangSmith, and Phoenix, each compiling veto/essential gating into a `final_result` scorer.
- NR-7 Demo Corpus and golden EvalPack with all seven defects planted; PRD §30 acceptance run.
- CI: offline contract tests and acceptance run on every PR, live platform smokes on dispatch/release.
