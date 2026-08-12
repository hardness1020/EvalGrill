# Human review guide: golden pack (NR-7 / Lantern demo)

Hand-authored (ADR-0002). This pack is **HUMAN_REVIEWED**: all 10 tasks and
16 calibration cases carry `verified: true` from the HITL review of
2026-08-11. This guide records what that review covered and what a human
checks before advancing `evalgrill.yaml` status. A status advance is always
a human act, never a script's.

## Criteria

| id | kind | layer | importance | failure modes | deterministic |
|---|---|---|---|---|---|
| `cites_only_provided_sources` | veto | veto | n/a | fabricated_citation | true |
| `quote_attribution` | binary | evidence | essential | misattributed_quote | false |
| `quantitative_claims_sourced` | binary | evidence | essential | unsupported_claim | true |
| `conflict_handling` | ordinal | evidence | essential | missed_source_conflict | false |
| `evidence_coverage` | ordinal | evidence | important | incomplete_coverage | false |
| `confidence_calibration` | ordinal | communication | essential | false_certainty, miscalibrated_confidence | false |

All 7 taxonomy modes are covered by a criterion. Domain rule 5 ("clear and
well-organized") was reviewed and **dropped**: no failure mode, no observable
anchors. It is the demo's example of a criterion not surviving human review;
its vague form lives on in `fixtures/draft-rubric.yaml` as a planted defect.

## Veto confirmation

- `cites_only_provided_sources` encodes domain rule 1, the only
  zero-tolerance rule; deterministic against `task.input.context`.
- High-severity modes deliberately left weighted: `misattributed_quote` and
  `missed_source_conflict` are scored, not vetoed, because only rule 1 is
  stated as disqualifying.

## Deterministic ledger

Scripts owed by the validate phase: packet-citation match (the veto) and
numeral-vs-packet match (`quantitative_claims_sourced`). Each keeps the judge
as backstop for paraphrase residue, per the criterion comments in
`rubric.yaml`.

## Escalations (refreshed by the validate phase)

From the replay audit (`audit_pack.py --runner replay`, scripted verdicts):

- `misattributed_quote`: high severity, zero task coverage. Dataset work
  needed before trusting coverage claims.
- `nr7-clinical-advice` near-tie pair: pairwise preference follows
  presentation order. Human review of the pair.
- `nr7-overall-verdict/fluent-conflict-gloss`: runs disagree (pass then fail)
  and run 1 contradicts the human fail label. Human regrade.
- `nr7-effect-size/citation-stuffing`: ADVERSARIAL candidate passes the
  judge in both runs against a human fail label. Reward-hacking pattern,
  rubric hardening candidate.

## Status advance

`CALIBRATED` requires judge calibration executed and reviewed. Scripted-replay
calibration plus the live claude-cli sweep (map ticket #23: alignment 95%/95%,
veto recall 100%, citation-stuffing also games the live judge) are the
evidence on file; a human weighs them. The fixtures above are planted defects
and stay unfixed by design.
