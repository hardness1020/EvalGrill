Rejected in #29

Integration surfaces for further harnesses (gemini, cursor, opencode) beyond claude-code and codex.

- Each additional harness is a doc and support surface with no known user; the thin layer stays at two entries until real demand.
- The canonical `skills/` tree (ADR 0003) already works wherever a harness can load it, so speculative per-harness docs only invite drift.

Revisit when a real user asks for a specific harness.
