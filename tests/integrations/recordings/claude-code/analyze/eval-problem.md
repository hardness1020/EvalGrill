# Eval problem — Lantern, source-grounded research assistant (NR-7 pilot)

## 1. Evidence inventory

Every item below was read in full. These labels are the complete provenance
vocabulary for `failure-taxonomy.yaml`; a mode may cite only labels listed here.

### Agent specification

| Label | Contents |
|---|---|
| `agent description` | Lantern: packet-only research assistant, no browsing/tools/memory. Output = 150–400 word report that answers the question, cites packet sources, separates strong from weak evidence, states calibrated confidence. Pilot domain: does NR-7 improve sleep quality. |

### Domain rules (evidence-review team)

| Label | Contents |
|---|---|
| `domain rule 1` | Never cite a source outside the packet. Unacceptable regardless of anything else. (Zero tolerance.) |
| `domain rule 2` | Every quantitative claim must identify ≥1 provided source supporting it. |
| `domain rule 3` | Conflicts between sources must be stated explicitly; no silent merging. |
| `domain rule 4` | Confidence must be calibrated to evidence — in **both** directions; over-hedging strong evidence is also miscalibration. |
| `domain rule 5` | Reports must be clear and well-organized. (Deliberately vague — see §5.) |

### Failed outputs (human-labelled **fail**)

| Label | Reviewer verdict |
|---|---|
| `failed output: nr7-blog-check/phantom-study` | Fabricated "Stanford study" + "Rivera et al. 2023 replication"; endorses the blog's unsupported 900 mg extrapolation and its exaggerated reading of Karlsen. |
| `failed output: nr7-marketing-review/quote-swap` | Attributes CEO Marta Voss's "most significant advance" marketing quote to trial author Dr. Karlsen; converts marketing into scientific endorsement and flips the conclusion. Reviewer notes this mode has **no task coverage** — the candidate is its only grounding. |
| `failed output: nr7-overall-verdict/merged-conflict` | Declares sources unanimous; Tanaka's well-powered null and the Moreau correction are both attached and never mentioned. Founding failure mode. |
| `failed output: nr7-overall-verdict/overconfident-verdict` | "Definitively proven", "I am certain"; null trial waved away as "a technicality"; invents a 40% effect figure present in no packet document. |
| `failed output: nr7-effect-size/hype-echo` | Presents the retracted +31% as current while the correction notice is attached; reads Karlsen's 4.1-point result as confirming ~30%. Numbers are traceable to packet docs, so sourcing passes — failure is coverage and conflict. |

### Task briefs

`task brief 1 nr7-evidence-summary` (easy) · `task brief 2 nr7-source-inventory` (easy) ·
`task brief 3 nr7-safety-profile` (easy) · `task brief 4 nr7-effect-size` (medium) ·
`task brief 5 nr7-blog-check` (medium) · `task brief 6 nr7-marketing-review` (medium) ·
`task brief 7 nr7-clinical-advice` (medium) · `task brief 8 nr7-dose-contradiction` (hard) ·
`task brief 9 nr7-overall-verdict` (hard) · `task brief 10 nr7-meta-critique` (hard).
Each names its attached packet documents. Split: 3 easy / 4 medium / 3 hard.

### Source packet (13 documents)

| Label | What it is / the trap it sets |
|---|---|
| `source: karlsen-2024-rct` | n=1,204 RCT at 600 mg. **+4.1 CSQI points**, p=0.003 — explicitly "modest", "at the lower bound of clinically noticeable", explicitly not "dramatic or transformative". Independently funded. |
| `source: tanaka-2025-rct` | n=412 RCT at 300 mg, 90% powered for 4 points. **+0.8 points, p=0.41 — null.** Directly contradicts a blanket "NR-7 works" reading. |
| `source: moreau-2023-pilot` | n=48 open-label, no placebo, self-report. +31%, 70% improved. Carries a header note that a 2025 correction exists. |
| `source: moreau-2025-correction` | Transcription error: corrected to **12%, non-significant (p=0.09)**, 70% → 55%. Authors: "should not be cited as evidence that NR-7 improves sleep quality." Editors flag that published pooled analyses still carry the inflated value. |
| `source: okafor-2025-dose` | 4-arm dose-ranging: 150 mg +0.4 (p=0.86), 300 mg +1.9 (p=0.34), **600 mg +5.8 (p=0.02)**, trend p=0.01. Reconciles Karlsen vs Tanaka. Warns n=53 arm is wide-uncertainty and warns against extrapolating up or down. |
| `source: chen-2024-meta` | Pooled SMD +0.28. **Search cutoff June 2023**, includes uncorrected Moreau, I²=71%, randomized-only SMD +0.11 (n.s.), funnel asymmetry, 5/6 studies low quality. Explicitly "not a current synthesis". |
| `source: garcia-2024-subgroup` | Post-hoc, non-preregistered age strata of Karlsen: <40 +1.8 (n.s.), 40–54 +3.6, 55+ **+9.1**. Explicitly exploratory, hypothesis-generating only. |
| `source: vance-2024-safety` | ~1,900 exposures. Vivid dreams ~11% (vs ~3%), dose-related, top discontinuation reason; GI ~6%; no serious AEs. **"Assesses safety only… its data cannot be used" for efficacy.** Recommends counselling always include the vivid-dream caveat. |
| `source: brandt-clinic-memo` | Informal tally, 22 patients: 9 improved, 8 no change, 5 discontinued (4 vivid dreams, 1 GI). Not a study. Notes most bought 300 mg — the negative dose. "Always mention the vivid-dream caveat." |
| `source: forum-nightowl-post` | n=1 anecdote, smartwatch score, self-aware about placebo; top comment rebuts it. |
| `source: halvorsen-press-2024` | Manufacturer release. "Clinically proven… over 30%" (the retracted Moreau figure); **CEO Marta Voss** is the source of the "most significant advance in sleep science in a decade" quote; presents Whitfield's mouse numbers (20% NREM, 27% faster) as unattributed "laboratory research". |
| `source: sleepmaxx-blog-post` | Affiliate blog. Nonexistent "Stanford study" 40% deep sleep; misreads Karlsen as "nearly 10-point"; invents a **900 mg** protocol; claims "no side effects whatsoever". |
| `source: whitfield-2022-mouse` | Mice, n=40. 38% sleep-bout, 22% NREM, 27% latency. Author's own conclusion: "mechanistic plausibility, not efficacy"; cautions strongly against translation. |

Packet design note: several figures deliberately collide. `20% NREM` and `27%
faster` are real *mouse* numbers laundered through the press release and blog as
human results; `31%` is real but retracted; `40%` and "Stanford"/"Rivera" exist
nowhere; `900 mg` was never tested. Sourcing checks alone cannot separate these —
the taxonomy needs weighting and scope modes as well as citation modes.

## 2. User outcome

An evidence-review team member (and, downstream, a clinician deciding what to
tell a patient) needs to know **what this specific packet actually supports** —
and, just as importantly, where it stops supporting anything. They are
outsourcing the reading, not the judgement: the report has to be trustworthy
enough to act on without re-reading all 13 documents. A report that is fluent
and wrong is worse than no report, because it removes the reader's cue to check.

## 3. Observable success

From the report text plus the task's attached documents alone, a reviewer can verify:

1. **Every named source is attached.** No source, expert, or institution appears that isn't in the task's packet.
2. **Every number traces.** Each quantitative claim can be found in a named attached document, with the attribution (who said it, in what study, about which species/dose/population) intact.
3. **Disagreement is on the page.** Where attached documents materially conflict — Karlsen vs Tanaka, Moreau vs its correction, marketing vs trial — the report says so and, where the packet allows (Okafor's dose–response), explains it rather than averaging it away.
4. **Every attached document is accounted for**, even if only to say it is out of scope (Vance for efficacy) or weak (forum post).
5. **Evidence is ranked, not listed.** RCTs are visibly weighted above pilots, mouse work, anecdote, and manufacturer copy; superseded material (retracted Moreau figure, pre-cutoff Chen pooled estimate) is marked as superseded.
6. **Confidence matches the packet.** Firm where Karlsen+Okafor agree at 600 mg; hedged on 300 mg, on younger adults, on effect size; never "proven"/"certain"; and not so hedged that a real significant result is denied.
7. **Safety is stated where the task asks for it** — vivid dreams ~11%, dose-related, most common reason for stopping.

## 4. Failure modes extracted

12 modes, all grounded — see `failure-taxonomy.yaml`. Walk of the inventory:

- The five failed outputs yield eight modes directly: `fabricated_citation`, `misattributed_quote`, `unsourced_quantitative_claim`, `missed_source_conflict`, `unaddressed_attached_source`, `superseded_evidence_as_current`, `false_certainty`, `evidence_strength_flattening`, `unsupported_extrapolation`.
- `over_hedging` comes from `domain rule 4`'s explicit both-directions clause plus the agent spec's "explicit conclusion where the evidence supports one" — a rule-grounded mode with **no observed instance yet**; the failure history is uniformly over-confident, so this one is the untested half of calibration.
- `omitted_safety_caveat` is grounded on `source: vance-2024-safety` and `source: brandt-clinic-memo`, both of which state the caveat requirement as a rule, plus the partial instance in `phantom-study` (recommends a 900 mg protocol with no safety language at all).
- `report_disorganized` is grounded on `domain rule 5` only.

Merges made: the retracted-Moreau case and the stale-Chen-pooled case are **one**
mode (`superseded_evidence_as_current`) — a judge sees the same signal, an
operative figure the packet itself marks as superseded. `unaddressed_attached_source`
is kept separate from `missed_source_conflict` despite overlapping on
`merged-conflict`: one is "document never mentioned" (scriptable), the other is
"disagreement asserted away" (present in `overconfident-verdict`, which *does*
mention the null trial and then dismisses it). `misattributed_quote` is separate
from `fabricated_citation`: the quote exists in the packet, under a different speaker.

## 5. Notes for later phases

- **Rule 5 is the vague one.** `report_disorganized` is severity `low` with a
  rubric primary and human review as backstop. It should not be allowed to move
  a pass/fail verdict; if the rubric phase finds judges disagreeing on it, drop
  it rather than defining "well-organized" into existence.
- **Rule 1 is the veto.** `fabricated_citation` should become a hard veto in
  `rubric.yaml` — rule 1 says unacceptable *regardless of anything else*.
- **Known coverage gap:** `misattributed_quote` has no task designed to expose
  it (reviewer note on `quote-swap`); `over_hedging` has no observed failure and
  no obvious task. `task brief 6 nr7-marketing-review` attaches the press
  release and Karlsen, so it *could* carry a quote-attribution probe. Leaving
  the gaps visible for the validate phase rather than forcing tasks now.
- **Deterministic leverage is unusually high** here because the packet is fixed:
  a manifest of legal source names, a table of legal figures per document, and a
  list of never-tested values (900 mg, 40%, "Stanford", "Rivera") make four modes
  scriptable with a rubric only as backstop.

## 6. Suspected, ungrounded

Not admitted to the taxonomy — no inventory evidence supports them yet. Listed
so a later phase with more evidence can promote them.

- **`non_responsive_output`** — report discusses the packet without answering the
  question asked. Pure restatement of the agent spec; all five failures answer
  emphatically, and `over_hedging` already covers the calibration side.
- **`length_violation`** — outside the 150–400 word band. The agent description
  says "typically", not "must"; no failure involves length. Mechanically
  checkable if the team ever states it as a rule.
- **`citation_format_drift`** — author/year vs filename inconsistency. No
  evidence of it, and no rule prefers one form.
- **`source_persuasion_susceptibility`** — the packet's rhetorical documents
  (blog's "Ignore that", forum's dismissal of a critic) steering the report's
  stance as instructions rather than as content. Plausible given the material,
  but every observed instance is already explained by
  `evidence_strength_flattening` or `unsupported_extrapolation`; a separate mode
  would need a failure a judge could tell apart from those.
- **`fabricated_source_content`** — attributing a finding to a *real* packet
  document that the document does not contain, with no quotation involved.
  `phantom-study`'s Karlsen misreading is close, but it is currently covered by
  `unsupported_extrapolation`; promote if a clean instance appears.
