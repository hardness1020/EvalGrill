Rejected in #28

Automated drift/consistency check between `agents/openai.yaml` sidecars and SKILL.md frontmatter.

- Sidecar fields are runtime metadata, not duplicated skill semantics.
- `short_description` is intentionally not mechanically equivalent to the canonical `description`.
- ADR 0003 already permits runtime metadata so long as canonical skill semantics stay single-sourced; no ADR amendment needed.

Revisit automated generation/consistency checks when a second runtime consumes sidecar metadata or when drift occurs in practice.
