# AGENTS.md

Canonical contract for coding agents working in this repo. Tool-specific entrypoints (e.g. a local `CLAUDE.md`) stay thin and defer here.

## Project shape

The repo root is a Claude Code plugin: skills in `skills/`, manifests in `.claude-plugin/`. All scripts are single-file PEP 723 Python run with `uv run`; no environment setup. Dev loop: `claude --plugin-dir .`, then `/reload-plugins` after edits (details in CONTRIBUTING.md).

## Conventions

- Conventional commits, under 50 words, short bullets when a body is needed.
- No Co-Authored-By trailers or generated-with footers on commits or PRs.
- One concern per PR, target `main`, link the issue it resolves.

## Validation

Every check runs offline, no secrets needed. A change is done when the checks it touches pass; run the full list before opening a PR:

```bash
claude plugin validate . --strict                              # marketplace manifest
claude plugin validate .claude-plugin/plugin.json --strict     # plugin manifest + skill frontmatter
uv run scripts/check_pack.py demo/golden-pack                  # schema + referential integrity
uv run scripts/audit_pack.py demo/golden-pack --runner replay  # all seven detections
uv run tests/test_export_braintrust.py                         # contract tests, one per surface
uv run tests/test_export_langsmith.py
uv run tests/test_export_phoenix.py
uv run tests/test_judge_runner.py
uv run tests/integrations/test_cross_harness.py                # replay recorded claude-code + codex runs
uv run tests/acceptance_30.py                                  # the full acceptance bar
```

The plugin-manifest validate warns (exit 1 under `--strict`) when a local `CLAUDE.md` sits at the repo root; benign, the plugin runtime ignores plugin-root `CLAUDE.md`. Fresh clones pass clean.

## Fixtures are the test

`demo/golden-pack/fixtures/` contains deliberately planted defects; the acceptance bar asserts they are detected. Leave them in place, never repair them. Spoiler map: `demo/README.md`.

## Working docs (local, gitignored; proceed silently when absent)

- `CONTEXT.md`: domain glossary. Use its vocabulary; consumption rules in `docs/agents/domain.md`.
- `docs/agents/issue-tracker.md`: issues live in this repo's GitHub Issues, `gh` CLI conventions.
- `docs/agents/triage-labels.md`: five-role triage vocabulary, label string = role name.

`docs/adr/` is tracked. Read ADRs touching the area you change; when your output contradicts one, say so rather than silently overriding.

## Out of scope

`.out-of-scope/` holds one record per rejected feature: `<slug>.md`, first line `Rejected in #<issue>`, then the reasons. Before proposing or building a feature, check here; a hit means the feature stays unbuilt, comment on the cited issue instead. The directory appears with its first record.
