Rejected in #29

`npx skills add` (skills.sh CLI) as an install path.

- It installs skill folders as copies; copies drift from the canonical `skills/` tree (ADR 0003).
- Skill bodies reference repo-root `scripts/` and `schemas/`, which a copied `skills/<name>/` does not carry.
- Both documented paths already suffice: Claude Code via the plugin marketplace, codex via symlinks into the clone (`git pull` updates everything).

Revisit at the installer milestone, or if demand for registry install appears.
