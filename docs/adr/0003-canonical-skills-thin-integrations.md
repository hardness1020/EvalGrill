---
status: accepted
---

# Repo root is the plugin: one canonical `skills/`, thin integrations

The repo root is the Claude Code plugin and the single canonical skill set: `skills/`, `scripts/`, and `schemas/` live at the root with `.claude-plugin/plugin.json` beside them. There are no per-agent copies of skills; any future integration surface (other agent runtimes, an installer) consumes the canonical set rather than forking it. The root `marketplace.json` points its plugin source at `./`. Scripts stay single-file PEP 723 uv scripts; a Python package is deferred to the installer milestone.

Decided in a grill session comparing mattpocock/skills, obra/superpowers, and anthropics/skills: all three converge on skills-at-root; the nested `plugin/` wrapper added a path segment to every command, doc, and CI step while enabling nothing.

One deviation from the originating ticket (#26), which kept the marketplace as an "undocumented fallback": Claude Code has no direct-from-repo plugin install, a marketplace is the only remote install path, so `marketplace.json` stays the documented end-user install in the README quickstart. What is undocumented is only the persistent local dev install (`claude plugin marketplace add .`); the documented dev loop is `claude --plugin-dir .`.

## Rejected: per-agent copies

Duplicating skills per integration target (e.g. `claude/skills/`, `cursor/skills/`) guarantees drift between copies and multiplies the review surface. Skill bodies reference bundled resources via `${CLAUDE_PLUGIN_ROOT}`, so one canonical tree already works wherever the plugin loads from.

## Rejected: Python package

A package adds build/publish machinery for scripts that `uv run` already executes with inline dependencies. Revisit when an installer needs versioned distribution.

## Consequences

- All paths shortened: `plugin/scripts/…` → `scripts/…` across README, CONTRIBUTING, demo docs, CI workflows, and tests.
- `plugin/README.md` is gone; its dev-loop content lives in CONTRIBUTING.md.
- `claude plugin validate . --strict` resolves to the marketplace manifest (both manifests share `.claude-plugin/`); skill frontmatter is validated separately by `claude plugin validate .claude-plugin/plugin.json --strict`. The latter warns when a local untracked `CLAUDE.md` sits at the repo root (the plugin runtime ignores plugin-root CLAUDE.md), so it exits 1 on the maintainer's machine; fresh clones and CI pass clean.
- With source `./`, a marketplace install ships the whole repo tree as plugin payload (demo corpus, tests, docs included), and the local `marketplace add .` form copies even untracked files (e.g. `.env`) into the plugin cache. `plugin.json` has no include/exclude mechanism; slimming the payload belongs to the installer milestone. Prefer `--plugin-dir .` locally.
- The blanket `docs/` `.gitignore` entry is narrowed to `docs/*` + `!docs/adr/`: ADRs (including this one) are now tracked, since CI comments and the READMEs cite them; `docs/prd.md` and `docs/agents/` stay local working docs. New tracked docs need their own carve-out.
