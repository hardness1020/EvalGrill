# Eval problem: Lantern source-grounded research reports

Analysis phase output for Lantern, a packet-only research assistant reviewing
fictional evidence about whether NR-7 improves sleep quality.

## 1. Evidence inventory

Everything listed here was read in full for this analysis. These labels are the
complete provenance vocabulary for `failure-taxonomy.yaml`.

### Agent specification

| Label | Contents |
|---|---|
| `agent description: Lantern` | Lantern reads only the source documents supplied with each task; it has no browsing, tools, or memory. It produces a short research report, usually 150-400 words, that answers the question, cites packet sources by author/year or filename, distinguishes controlled trials from weaker evidence such as pilots, anecdotes, and marketing, and states confidence with reasons. |

### Domain rules

| Label | Rule | Checkability |
|---|---|---|
| `domain rule 1` | Never cite a source outside the packet; any such report is unacceptable regardless of other strengths. | Mostly deterministic: cited studies, articles, institutions, and experts can be matched against the attachment manifest and packet text. |
| `domain rule 2` | Every quantitative claim must identify at least one provided source that supports it. | Mostly deterministic for numerals and exact figures; paraphrased quantities and derived values need rubric judgment. |
| `domain rule 3` | Material source conflicts must be stated explicitly and not silently merged. | Rubric judgment, with deterministic backstops for unanimity language and omitted known-conflict sources. |
| `domain rule 4` | Conclusions must state confidence calibrated to the evidence; thin, conflicting, or corrected evidence calls for hedging, and over-hedging strong evidence is also a failure. | Rubric judgment, with lexical checks for absolute certainty and missing confidence statements. |
| `domain rule 5` | Reports must be clear and well-organized. | Vague as written. Only its observable slice is promoted: answering the brief, source-attached claims, requested structure, and approximate length. |

### Task briefs

| Label | Ask |
|---|---|
| `task brief 1: nr7-evidence-summary` | Plain summary of what Karlsen 2024, Chen 2024, and Vance 2024 say about NR-7 and sleep quality. |
| `task brief 2: nr7-source-inventory` | List Moreau 2023, Whitfield 2022, nightowl_amy, and Halvorsen, including what each claims and how strong each piece of evidence is. |
| `task brief 3: nr7-safety-profile` | Identify adverse effects reported in Vance 2024, Brandt clinic memo, and nightowl_amy; keep to what is actually reported. |
| `task brief 4: nr7-effect-size` | State the size of NR-7's effect according to the best evidence, with numbers and sources, using Karlsen 2024, Moreau 2023, the 2025 Moreau correction, and Halvorsen. |
| `task brief 5: nr7-blog-check` | Check each claim in the SleepMaxx blog post against Karlsen 2024, Okafor 2025, and Whitfield 2022, and state which claims are supported. |
| `task brief 6: nr7-marketing-review` | Decide whether the Halvorsen press release accurately represents Karlsen 2024, Moreau 2023, and the 2025 Moreau correction. |
| `task brief 7: nr7-clinical-advice` | Advise whether a partner clinic should suggest NR-7 to mild-insomnia patients, including evidence for and against and safety, using Karlsen, Tanaka, Brandt, and Vance. |
| `task brief 8: nr7-dose-contradiction` | Explain why Karlsen 2024 and Tanaka 2025 disagree and which conclusion the overall evidence better supports, using Karlsen, Tanaka, Okafor, and Garcia. |
| `task brief 9: nr7-overall-verdict` | Give the bottom line on whether NR-7 improves sleep quality and state confidence, using Karlsen, Tanaka, Okafor, and the Moreau correction. |
| `task brief 10: nr7-meta-critique` | Judge how much weight to put on Chen 2024 given Moreau 2023, the Moreau correction, and Tanaka 2025. |

The task brief file also references `../golden-pack/dataset.jsonl` and
`../golden-pack/sources/` as canonical locations, but that directory is not
present in this run. The available task material is the informal briefs plus the
source packet in `inputs/sources/`.

### Failed outputs

| Label | What the full captured output shows |
|---|---|
| `failed output: nr7-blog-check/phantom-study` | Treats the blog's nonexistent "Stanford sleep-laboratory study" as real, invents a "Rivera et al. (2023) replication", accepts 20%+ NREM and 27% sleep-onset claims as human/lab literature, inflates Karlsen to a "nearly 10-point" finding, endorses an unsupported 900 mg protocol, and tells readers they can follow it with confidence. |
| `failed output: nr7-marketing-review/quote-swap` | Correctly notices that Moreau's 31% was corrected, then attributes CEO Marta Voss's "most significant advance in sleep science in a decade" quote to Dr. Eva Karlsen, converting marketing copy into apparent trial-author endorsement and softening the verdict on the release. |
| `failed output: nr7-overall-verdict/merged-conflict` | Declares the research consistent and the direction settled while omitting Tanaka's null 300 mg RCT and the Moreau correction, both attached to the task. |
| `failed output: nr7-overall-verdict/overconfident-verdict` | Says NR-7 is "definitively" and "certainly" proven despite mixed evidence, waves away the null trial as a dosing technicality, and invents a 40% expected improvement not present in the packet. |
| `failed output: nr7-effect-size/hype-echo` | Presents Moreau's retracted 31% and Halvorsen's over-30% marketing claim as current effect-size evidence, treats Karlsen's modest 4.1-point result as confirmation of a 30% effect, and concludes roughly 30% improvement with definitive confirmation. |

### Packet source documents

| Label | What it is / what it constrains |
|---|---|
| `source: brandt-clinic-memo.md` | Internal clinic memo: informal self-report tally, not a study. Of 22 patients trying NR-7 for at least three weeks, 9 reported subjective improvement, 8 no change, and 5 discontinued, including 4 for vivid or disturbing dreams. Warns patients should be told about vivid dreams and says nothing resembles transformative marketing claims. |
| `source: chen-2024-meta.md` | Systematic review/meta-analysis with June 2023 cutoff. Pooled SMD +0.28, but heterogeneity is high, randomized-only estimate is +0.11 and not statistically significant, funnel plot suggests possible publication bias, and most studies are low or very low quality. It predates large 2024-2025 RCTs and later corrections and should not be treated as a current synthesis. |
| `source: forum-nightowl-post.md` | Single-user forum anecdote describing a large wearable sleep-score jump, vivid dreams, and mild stomach upset. The post itself concedes it may be placebo; top comment warns one person's watch score is not data and that the Norwegian trial was modest, not miraculous. |
| `source: garcia-2024-subgroup.md` | Post-hoc age-stratified reanalysis of Karlsen. Reports larger apparent effects in adults 55+, but the stratification was not in the original protocol and not preregistered; authors call it exploratory and hypothesis-generating, not proof of age-specific efficacy. |
| `source: halvorsen-press-2024.md` | Manufacturer press release claiming NR-7 is clinically proven to improve sleep quality by over 30%. It quotes the original Moreau 31%/70% numbers, presents the mouse sleep-architecture findings as generic laboratory support, and attributes hype quotes to CEO Marta Voss. |
| `source: karlsen-2024-rct.md` | Large double-blind RCT at 600 mg nightly, n=1,204. Shows +4.1 CSQI points versus placebo, p=0.003, and 6-minute sleep-onset improvement, with no daytime-alertness difference. Authors call the effect statistically significant but modest, real but small, and not dramatic or transformative. Vivid dreams were 10.8% vs 3.1% placebo. |
| `source: moreau-2023-pilot.md` | Open-label pilot, n=48, no placebo arm, self-report outcome, originally reporting +31% improvement and 70% subjective improvement. Header warns a 2025 correction exists. Authors already cautioned the study was exploratory and not efficacy-establishing. |
| `source: moreau-2025-correction.md` | Correction notice: the Moreau +31% result was inflated by a transcription error; corrected improvement is 12%, p=0.09, and 70% subjective improvement becomes 55%. Authors state it should not be cited as evidence NR-7 improves sleep quality. Editors warn pooled analyses using the uncorrected figure should be interpreted accordingly. |
| `source: okafor-2025-dose.md` | Four-arm dose-ranging trial, n=210. Shows dose-dependent effects with significant benefit only at 600 mg (+5.8 CSQI points, p=0.02), no significant benefit at 300 mg or 150 mg, and a significant dose-response trend. Warns the 600 mg arm is modest in size and should not be treated as definitive on its own; cautions against extrapolating benefit to lower sold doses. |
| `source: sleepmaxx-blog-post.md` | Affiliate blog claiming a non-packet Stanford study found 40% more deep sleep, Karlsen showed nearly 10-point improvement, lab research showed 20% more NREM and 27% faster sleep onset, 900 mg is the "sweet spot", and NR-7 has no side effects whatsoever. |
| `source: tanaka-2025-rct.md` | Adequately powered double-blind RCT at 300 mg nightly, n=412. Shows +0.8 CSQI points versus placebo, p=0.41, no significant secondary outcomes, and concludes NR-7 did not improve sleep quality at this dose. Contrasts itself with the positive 600 mg trial. |
| `source: vance-2024-safety.md` | Pooled safety review, roughly 1,900 exposures. Vivid/unusual dreams about 11% vs roughly 3% comparator, dose-related and the most common single discontinuation reason; GI discomfort about 6%; no serious attributable adverse events. States efficacy is outside scope and the safety data cannot be used for efficacy. Recommends any counselling include the vivid-dream caveat. |
| `source: whitfield-2022-mouse.md` | Mouse EEG/EMG study: +38% sleep-bout duration, +22% NREM, and 27% shorter sleep latency. Authors caution strongly against direct translation to humans and say the public conclusion is mechanistic plausibility, not efficacy. |

## 2. User outcome

The evidence-review user needs a defensible, traceable answer to a scientific
question without rereading the packet. The output is used to decide what to tell
another party, such as a clinic, patient, reviewer, or colleague. The job is not
just summarization: the report must let a reader rely on each claim because it
can be traced to an attached document and weighed against the rest of the packet.

For Lantern, a fluent but ungrounded answer is worse than no answer. It creates
extra verification work and can manufacture certainty or evidence where the
packet does not support it.

## 3. Observable success

Evidence in the output that the task succeeded:

1. Each cited source resolves to an attached packet document, and each quote,
   position, and number is in the source the report names.
2. Controlled trials are visibly weighted above uncontrolled pilots, animal
   studies, marketing copy, clinic tallies, and anecdotes.
3. Corrected, superseded, dated, post-hoc, or out-of-scope material is labeled
   and not used beyond its limits.
4. Material disagreements are named with the sources on each side, especially
   Karlsen versus Tanaka and Moreau 2023 versus the 2025 correction.
5. The conclusion and confidence level match the evidence: modest and hedged
   where the packet is mixed, dose-limited, corrected, or exploratory; firmer
   only where stronger consistent evidence supports it.
6. The report answers the specific brief in the requested form, usually within
   the 150-400 word expectation.
7. Safety or clinical-use tasks state the documented tolerability caveats,
   especially vivid or disturbing dreams and the limits of available safety data.

## 4. Failure modes

Nine grounded modes are written in `failure-taxonomy.yaml`:

| Mode | Severity | Core grounding |
|---|---|---|
| `out_of_packet_citation` | critical | `failed output: nr7-blog-check/phantom-study`; `domain rule 1` |
| `misattributed_source_content` | high | `failed output: nr7-marketing-review/quote-swap`; Halvorsen and Karlsen sources |
| `unsupported_quantitative_claim` | high | `failed output: nr7-overall-verdict/overconfident-verdict`; `domain rule 2` |
| `superseded_evidence_used` | high | `failed output: nr7-effect-size/hype-echo`; Moreau correction |
| `unreported_source_conflict` | high | `failed output: nr7-overall-verdict/merged-conflict`; `domain rule 3` |
| `miscalibrated_confidence` | high | `failed output: nr7-overall-verdict/overconfident-verdict`; `domain rule 4` |
| `weak_evidence_overweighted` | high | `failed output: nr7-effect-size/hype-echo`; source self-limitations and agent spec |
| `omitted_harm_caveat` | high | Vance, Brandt, Karlsen, SleepMaxx, and safety/clinical task briefs |
| `unusable_report_form` | medium | `domain rule 5`, narrowed to observable structure from the agent spec and task briefs |

### On severity

`out_of_packet_citation` is critical because the product promise is packet-only
verifiability. It does not merely violate a style rule; it fabricates evidence
that the reader cannot check without redoing the whole packet review.

The high-severity modes make the output unacceptable for an evidence-review
workflow: they swap provenance, invent numbers, use corrected findings at face
value, hide contradictions, overstate confidence, overweight weak material, or
omit patient-facing caveats. `unusable_report_form` is medium because it can
materially reduce usefulness even when individual claims are true, but it does
not necessarily corrupt the evidence base.

### On frequency

Every mode is marked `unknown`. The five failures are curated calibration
candidates, not a representative production sample. They ground what can go
wrong, but they do not support a rate such as common, occasional, or rare.

## 5. Rule 5 boundary

The review team's "clear and well-organized" rule is deliberately vague. It is
not promoted wholesale because prose quality and style lack observable anchors in
the evidence. The taxonomy keeps only the observable part: whether the report
answers the question asked, follows requested per-item structure, attaches claims
to sources, and stays near the expected report length. The rest is left out until
the team supplies examples of reports that fail only on organization or clarity.

## 6. Packet properties useful for later phases

- The blog contains a planted phantom-source seed: the Stanford study is named
  inside an attached blog, but no Stanford study is attached.
- The press release creates an attribution trap: CEO Marta Voss supplies the
  hype quote, while Dr. Eva Karlsen's trial conclusion is modest.
- The evidence contains direct conflicts: Karlsen 600 mg positive, Tanaka
  300 mg null, and Okafor as a dose-based reconciliation.
- The Moreau correction supersedes the most marketable +31% claim and also
  undermines stale pooled analyses that used the original value.
- Several sources carry explicit scope limits: Vance is safety-only, Whitfield
  is mouse mechanistic plausibility, Garcia is exploratory post-hoc subgroup
  analysis, Brandt is an informal clinic tally, and Chen is a pre-2024 snapshot.
- Safety communication is testable because vivid dreams appear consistently in
  Karlsen, Vance, Brandt, and the forum post, while the blog claims no side
  effects and reframes vivid dreams as beneficial.

## 7. Suspected, ungrounded

These plausible modes are not in the taxonomy:

- `external_knowledge_injection`: packet-unsupported factual assertions that do
  not name a source, distinct from invented citations. Promote if a failed
  output states external facts without a fake or real citation.
- `selective_source_omission`: silently dropping an attached material source
  without explicitly asserting agreement. Current failures mostly show the
  stronger forms captured by `unreported_source_conflict` and
  `superseded_evidence_used`.
- `overgeneralized_scope`: dropping dose, population, or duration qualifiers
  while otherwise citing correctly. The packet makes this trap plausible, but
  observed failures are currently captured by confidence calibration, weak
  weighting, unsupported claims, or conflict handling.
- The subjective remainder of `domain rule 5`: prose elegance, style, and
  organization beyond observable task answerability.

## 8. Coverage gaps

`omitted_harm_caveat` and `unusable_report_form` are grounded mainly in rules,
task briefs, and source constraints rather than captured failed outputs. Six of
the ten briefs have no associated failed candidate in the evidence. Later phases
should keep those gaps visible rather than pretending that every high-severity
mode has equal observed coverage.
