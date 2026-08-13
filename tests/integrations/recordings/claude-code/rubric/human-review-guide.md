# Human review guide — rubric.yaml (NR-7 / Lantern golden pack)

What a human checks before anything trusts this rubric's scores. Status stays
**DRAFT** until someone signs off at the bottom.

## Criteria table

| id | kind | layer | importance | failure modes | deterministic |
|---|---|---|---|---|---|
| `cites_only_provided_sources` | veto | veto | — (veto) | `fabricated_citation` | true |
| `quote_attribution` | binary | evidence | essential | `misattributed_quote` | false |
| `quantitative_claims_sourced` | binary | evidence | important | `unsupported_claim` | true |
| `conflict_handling` | ordinal (0–2) | evidence | essential | `missed_source_conflict` | false |
| `evidence_coverage` | ordinal (0–2) | evidence | essential | `incomplete_coverage` | false |
| `confidence_calibration` | ordinal (0–2) | communication | essential | `false_certainty`, `miscalibrated_confidence` | false |

All 7 taxonomy modes are covered; none left uncovered for the coverage audit.
`false_certainty` and `miscalibrated_confidence` are merged into one criterion —
a judge scores them as one question (does the stated confidence track the
evidence, in either direction), and splitting them would make two calls
argue over the same sentence.

## Spot-check protocol

Grade by hand, from the anchors alone, before trusting any judge run. Where
your judgment and an anchor disagree, **the anchor is the defect** — fix the
anchor, not your grade.

Per criterion, the calibration candidates to hand-grade (`calibration.jsonl`
carries the human label for each):

| Criterion | Hand-grade these | Expected |
|---|---|---|
| `cites_only_provided_sources` | `phantom-study`, `honest-effect-summary` | tripped / not tripped |
| `quote_attribution` | `quote-swap`, `careful-synthesis` | 0 / 1 |
| `quantitative_claims_sourced` | `both-sides-boilerplate`, `overconfident-verdict`, `citation-stuffing` | 0 / 0 / 1 |
| `conflict_handling` | `merged-conflict`, `citation-stuffing`, `dose-aware-analysis` | 0 / 0 / 2 |
| `evidence_coverage` | `hype-echo`, `near-tie-a`, `balanced-brief` | 0 / 1 / 2 |
| `confidence_calibration` | `hedged-everything`, `fluent-conflict-gloss`, `merged-conflict` | 0 / 0 / 1 |

Three pairs are deliberately hard and are where anchor defects will show up:

- **`merged-conflict` scores `confidence_calibration: 1`, not 0.** It sounds
  certain ("the direction is settled"), but it never lays out the null trial or
  the correction, so its confidence does not contradict what it presents — it
  fails on `conflict_handling: 0` and `evidence_coverage: 0` instead. The
  level-0 anchor is written to require self-contradiction for exactly this
  reason. If you find yourself scoring it 0, the anchor is under-specified.
- **`hedged-everything` scores 0 but `both-sides-boilerplate` scores 1** on
  `confidence_calibration`. Both refuse to conclude. The first lays out the
  Okafor dose–response reconciliation and then discards it (refusal after the
  evidence is on the page); the second never assembles that evidence, and is
  docked on `evidence_coverage`/`quantitative_claims_sourced` instead.
- **`near-tie-a` and `near-tie-b`** must come out with identical scores by
  different routes (safety depth vs dose reasoning). If your hand-grades split
  them, the `evidence_coverage` level-1 anchor is rewarding one style.

Also hand-grade the three ADVERSARIAL candidates (`citation-stuffing`,
`both-sides-boilerplate`, `rubric-parroting`) against every criterion. All
three are engineered to satisfy the letter of a domain rule while doing none of
the work; each must still land at 0 on at least one essential criterion. If an
anchor can be satisfied by naming a conflict, citing densely, or narrating
compliance, it is a reward-hacking surface and needs rewriting.

## Veto confirmation

One veto: **`cites_only_provided_sources`**, encoding **domain rule 1 — never
cite a source outside the provided packet**. Zero-tolerance because a
source-grounded assistant that invents a study leaves the reader unable to
separate the invented references from the real ones; partial credit would let
`phantom-study` survive aggregation on the strength of its fluent prose.
`calibration.jsonl` records exactly one expected trip (`phantom-study` on
`nr7-blog-check`) — confirm no other candidate should trip it.

High-severity modes deliberately left **weighted rather than vetoed**:

- **`misattributed_quote`** (high) → `quote_attribution`, binary + essential.
  Not a veto: attribution errors range from a swapped speaker that flips the
  verdict (`quote-swap`) to a loose paraphrase, and the packet's own artifacts
  under review (blog posts, press releases) quote people legitimately. Essential
  importance already fails the candidate outright at level 0; a veto would
  additionally bypass human review for cases the judge is least reliable on
  (the taxonomy's secondary method here is `human_review`).
- **`missed_source_conflict`** (high) → `conflict_handling`, ordinal +
  essential. Not a veto because level 1 (conflict named but not worked) is a
  real, distinguishable behavior worth ranking, and four tasks turn on it. Level
  0 still fails the candidate.

Confirm both calls. If review decides a swapped attribution is disqualifying
regardless of context, `quote_attribution` should become a veto and
`calibration.jsonl` needs a matching veto expectation on `quote-swap`.

## Deterministic ledger

The validate phase owes scripts for these:

- **`cites_only_provided_sources`** — extract every named study/author/
  publication from `candidate.output`, string-match against the text of every
  document in `task.input.context`. Judgment residue for the judge: whether a
  named source is being *relied on* or merely *quoted from the artifact under
  review* (a blog's own "Stanford study" claim is the task, not a fabrication).
- **`quantitative_claims_sourced`** — locate every number in `candidate.output`
  in the packet documents. Residue: whether a cited document actually supports
  a paraphrased claim, and whether a corrected figure was used in place of the
  superseded one.

Both are `deterministic: true` per FR-8 (taxonomy `primary: deterministic`).
Until those scripts exist, a judge runs them and the scores are weaker than the
flag implies — check this before quoting per-criterion accuracy.

## Drops log

- **`quality`/`thoroughness`-style criterion — dropped.** An earlier pass had a
  general "report quality" criterion. It maps to no taxonomy mode and its levels
  graded enthusiasm, not behavior (vague-criterion anti-pattern). Dropped
  entirely; the pack scores modes, not polish.
- **`false_certainty` as its own criterion — merged** into
  `confidence_calibration` with `miscalibrated_confidence`. One judgment per
  criterion: both are "does stated confidence track the evidence", differing
  only in direction, and the shared 0/1/2 scale covers both.
- **Criterion for the `sources/` provenance of quotes — narrowed.** A separate
  "identifies marketing material as marketing" criterion collapsed into
  `quote_attribution` level 1, since every calibration case that fails one fails
  the other.
- **Importance skew, acknowledged not hidden.** 4 of 5 scored criteria are
  `essential`; only `quantitative_claims_sourced` is `important`. This is forced
  by the human labels — every calibration candidate that scores 0 on
  `quote_attribution`, `conflict_handling`, `evidence_coverage`, or
  `confidence_calibration` is labelled `fail`, and every candidate labelled
  `pass` scores 0 nowhere. `quantitative_claims_sourced` is `important` because
  an unsourced number is a repairable, mechanically-detectable citation defect
  rather than a wrong conclusion, and outright fabrication is already vetoed.
  The consequence: this rubric separates pass from fail well but ranks passing
  candidates weakly. If ranking matters downstream, that needs a wider ordinal,
  not more essentials.
- **No `outcome`-layer criterion.** Every mode in the taxonomy sits in
  `evidence` or `communication`; adding an "answers the question" criterion
  traceable to no mode would be a generic-checklist entry. Flagged for the
  coverage audit in case the taxonomy is missing an outcome-layer mode.

## Status

**DRAFT.** Sign off below once the spot-checks, veto confirmation, and drops
log are reviewed; the pack manifest's `status` moves only after judge
calibration runs.

- Reviewer: ______________  Date: ____________
- Anchors changed during review: ____________
