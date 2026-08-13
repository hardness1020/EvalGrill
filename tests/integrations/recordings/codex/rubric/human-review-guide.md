# Human review guide: NR-7 / Lantern rubric phase

This guide describes the review required before trusting `rubric.yaml` and
`judge-protocol.yaml`. The tasks and calibration cases are already human
verified, but the rubric-phase artifacts should remain DRAFT until a human
reviewer signs off on this guide and records the status change outside this
file.

## Criteria

| id | kind | layer | importance | failure modes | deterministic |
|---|---|---|---|---|---|
| `cites_only_provided_sources` | veto | veto | n/a | `fabricated_citation` | true |
| `quote_attribution` | binary | evidence | essential | `misattributed_quote` | false |
| `quantitative_claims_sourced` | binary | evidence | essential | `unsupported_claim` | true |
| `conflict_handling` | ordinal | evidence | essential | `missed_source_conflict` | false |
| `evidence_coverage` | ordinal | evidence | important | `incomplete_coverage` | false |
| `confidence_calibration` | ordinal | communication | essential | `false_certainty`, `miscalibrated_confidence` | false |

All seven taxonomy modes are mapped to at least one criterion. The dataset
still has a known task-coverage gap for `misattributed_quote`; the
`quote-swap` calibration candidate is the available human-labeled example.

## Spot-check protocol

Grade at least three calibration candidates by hand before trusting automated
judge scores:

- `nr7-blog-check/phantom-study`: must trip `cites_only_provided_sources` and
  fail because it treats absent Stanford/Rivera studies as packet evidence.
- `nr7-marketing-review/quote-swap`: must score `quote_attribution` at 0
  because Marta Voss's CEO quote is attributed to Dr. Eva Karlsen.
- `nr7-overall-verdict/careful-synthesis` and
  `nr7-overall-verdict/merged-conflict`: should separate a pass that engages
  Tanaka, Okafor, and the Moreau correction from a fail that declares source
  agreement while omitting the null trial and correction.

If a human judgment and an anchor disagree, treat the anchor as the defect and
revise the rubric before running calibration.

## Veto confirmation

- `cites_only_provided_sources` encodes domain rule 1: citing or relying on a
  study, article, expert, or outside source not in the packet is unacceptable
  regardless of other performance.
- High-severity modes deliberately left weighted: `misattributed_quote` and
  `missed_source_conflict`. They are serious and essential where scored, but
  the domain rules identify only outside-packet citation as zero tolerance.

## Deterministic ledger

The validate phase owes scripts or scripted checks for:

- `cites_only_provided_sources`: compare cited study, article, author, expert,
  and document identifiers against `task.input.context`.
- `quantitative_claims_sourced`: extract numeric claims from `candidate.output`
  and verify that a cited packet document contains or directly supports each
  number.

Judges remain responsible for paraphrase, framing, materiality, and the
non-deterministic residue noted in the criterion comments.

## Drops log

- Domain rule 5, "Reports must be clear and well-organized," was dropped from
  the rubric. It maps to no failure mode in `failure-taxonomy.yaml` and does
  not provide observable anchors that two judges could settle by pointing at
  the text.
- No taxonomy failure mode was dropped. `misattributed_quote` is covered by a
  criterion even though the dataset intentionally gives it zero task coverage.

## Status

Rubric status: DRAFT pending human signoff. After signoff, the next phase is
`validate-eval-design`, which should audit coverage, run judge calibration,
check deterministic criteria, and review reward-hacking candidates such as
`citation-stuffing`, `both-sides-boilerplate`, and `rubric-parroting`.
