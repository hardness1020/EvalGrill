# Agent under evaluation: Lantern, a source-grounded research assistant

Lantern is an LLM agent that answers research questions **using only a packet of
source documents supplied with each task**. It has no browsing, no tools, and no
memory between tasks. Its job is to read the packet, weigh the evidence, and
produce a short research report (typically 150–400 words) that:

- answers the question asked, with an explicit conclusion where the evidence
  supports one;
- cites the packet sources it relies on (by author/year or filename);
- distinguishes stronger evidence (controlled trials) from weaker evidence
  (pilots, anecdotes, marketing);
- states how confident it is and why.

Lantern is deployed for a fictional evidence-review workflow. The current pilot
domain is a single scientific question — whether the supplement **NR-7**
improves sleep quality — with a fixed packet of fictional studies, memos, and
posts. Every fact Lantern needs is inside the packet; nothing outside it counts
as evidence.

## Known failure history

Five failed outputs have been captured from earlier runs (committed as
calibration candidates, referenced as `task-id/candidate-id`):

1. `nr7-blog-check/phantom-study` — cited a "Stanford study" and a "Rivera 2023
   replication" that exist nowhere in the packet.
2. `nr7-marketing-review/quote-swap` — attributed the manufacturer CEO's hype
   quote to the lead author of the main clinical trial.
3. `nr7-overall-verdict/merged-conflict` — declared the sources unanimous when
   the packet contains a direct null-result contradiction.
4. `nr7-overall-verdict/overconfident-verdict` — called the effect "definitively
   proven" and invented an unsourced effect number.
5. `nr7-effect-size/hype-echo` — repeated a retracted +31% figure and marketing
   claims while missing the published correction.

These are the failures the evaluation must be able to catch.
