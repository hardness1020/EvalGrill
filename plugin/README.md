# EvalGrill plugin

Claude Code plugin: `/evalgrill` router + four phase skills (analyze → dataset → rubric → validate).

## Prerequisites

- Claude Code ≥ 2.1.216 (bare `/evalgrill` aliasing of namespaced skills). Headless `-p` runs need the namespaced form `/evalgrill:evalgrill` — the bare alias doesn't resolve there (observed at 2.1.227).
- [uv](https://docs.astral.sh/uv/) — bundled scripts are PEP 723 single-file scripts run via `uv run`

## Dev loop (recommended)

```bash
claude --plugin-dir ./plugin     # session-only, loads in place
```

Edit skills, then `/reload-plugins` inside the session — no restart. Don't dogfood via `plugin install`: marketplace installs copy to a cache and silently run stale code.

## Persistent install (optional)

The repo root is its own marketplace:

```bash
claude plugin marketplace add .
claude plugin install evalgrill@evalgrill-dev
```

## Validation

```bash
claude plugin validate ./plugin --strict   # manifest + skill frontmatter
claude plugin validate .                   # marketplace.json (repo root)
uv run plugin/scripts/smoke.py             # uv/PEP 723 plumbing
```

## Sandbox note

With the opt-in Bash sandbox enabled, the first cold-cache `uv run` prompts for PyPI domains — allow `pypi.org` and `files.pythonhosted.org` in `sandbox.network.allowedDomains`.
