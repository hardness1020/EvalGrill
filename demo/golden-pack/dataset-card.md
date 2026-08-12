# Dataset card: golden pack (NR-7 / Lantern demo)

10 tasks in `dataset.jsonl`, one per line, schema `task.schema.json`. Source
documents live in `sources/` inside this pack; every `input.context` path is
pack-root-relative and resolves here. `input` is the only agent-visible field.

Hand-authored (ADR-0002) from `failure-taxonomy.yaml` (7 modes) and
`evaluation-dimensions.yaml`, over the Demo Corpus inputs in `demo/inputs/`
(agent description, 10 briefs, 5 domain rules, 13-document NR-7 packet).

## Counts

**By difficulty**: easy 3, medium 4, hard 3. *Easy* means read a small packet
and report what it says; *medium* means cross-source verification or audit;
*hard* means synthesis under conflict, correction, or dose mismatch.

**By provenance**: SYNTHETIC 10, REAL 0. Every task was invented for this
corpus; nothing claims production origin. Reward-hacking candidates in the
calibration set are ADVERSARIAL.

**By risk**: low 3, medium 5, high 2 (`nr7-clinical-advice`,
`nr7-overall-verdict`: wrong answers reach a clinic or a published verdict).

**Clean vs failure-targeted**: 0 clean; all 10 tasks target at least one mode.

**Review**: 10/10 tasks and 16/16 calibration cases `verified: true`
(HITL review 2026-08-11).

## Regression coverage

The five known failed outputs (PRD §30 input) are committed as calibration
candidates; each has a task recreating its conditions:

| Failed output | Task |
|---|---|
| `nr7-blog-check/phantom-study` | `nr7-blog-check` |
| `nr7-marketing-review/quote-swap` | `nr7-marketing-review` |
| `nr7-overall-verdict/merged-conflict` | `nr7-overall-verdict` |
| `nr7-overall-verdict/overconfident-verdict` | `nr7-overall-verdict` |
| `nr7-effect-size/hype-echo` | `nr7-effect-size` |

## Coverage map

| Failure mode | Severity | Tasks targeting it |
|---|---|---|
| `fabricated_citation` | high | `nr7-blog-check` |
| `misattributed_quote` | high | none (zero coverage; `audit_pack.py` flags it, the §30 coverage-gap plant, see `demo/README.md`) |
| `missed_source_conflict` | high | `nr7-marketing-review`, `nr7-dose-contradiction`, `nr7-overall-verdict`, `nr7-meta-critique` |
| `false_certainty` | medium | `nr7-marketing-review`, `nr7-clinical-advice`, `nr7-dose-contradiction` |
| `unsupported_claim` | medium | `nr7-evidence-summary`, `nr7-source-inventory`, `nr7-safety-profile`, `nr7-effect-size`, `nr7-blog-check` |
| `incomplete_coverage` | medium | `nr7-evidence-summary`, `nr7-source-inventory`, `nr7-effect-size`, `nr7-clinical-advice`, `nr7-overall-verdict` |
| `miscalibrated_confidence` | medium | `nr7-effect-size`, `nr7-overall-verdict`, `nr7-meta-critique` |

## Calibration slate (16 candidates, 6 focal tasks)

4 clearly-good, 5 clearly-bad (the failed outputs above), 4 borderline
(`near-tie-a`/`near-tie-b`, `hedged-everything`, `fluent-conflict-gloss`),
3 reward-hacking ADVERSARIAL (`citation-stuffing`, `both-sides-boilerplate`,
`rubric-parroting`). Expected labels: 6 pass, 10 fail; one veto expectation
(`cites_only_provided_sources` on `phantom-study`).
