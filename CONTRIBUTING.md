# Contributing to EvalGrill

Thanks for your interest. Please read this before opening anything.

## Read this first

EvalGrill is at v0.1, dogfood stage: the design is still being validated against real use, and the maintainer is deliberately keeping scope tight. Small, focused contributions are welcome; large ones will probably be closed without review.

**Most likely to be accepted**

- Bug fixes with a reproduction
- Reliability and correctness fixes in the scripts (`scripts/`) and exporters
- Documentation fixes where the docs and the code disagree

**Least likely to be accepted**

- New features, new skills, or new export targets (the roadmap is maintained outside the repo; propose via an issue first)
- Large refactors or PRs touching many files at once
- Fixes to the planted defects in the Demo Corpus (see below: they are the test)

## Issues first

For anything non-trivial, open a GitHub issue before writing code. It saves you from building something that won't be merged. An acknowledged issue is not a promise the PR will be accepted.

Bug reports should include: what you ran, what you expected, what happened, and your Claude Code + uv versions.

## Development setup

Requires [Claude Code](https://claude.com/claude-code) ≥ 2.1.216 (bare `/evalgrill` aliasing of namespaced skills) and [uv](https://docs.astral.sh/uv/). No Python environment setup: all scripts are single-file PEP 723 scripts run via `uv run`. The repo root is the plugin.

```bash
git clone https://github.com/hardness1020/EvalGrill
cd EvalGrill
claude --plugin-dir .   # loads the plugin in place, session-only
```

Edit skills, then `/reload-plugins` inside the session; no restart needed. Do not develop against `plugin install`: marketplace installs copy to a cache and silently run stale code.

Two dev-loop gotchas:

- Headless `-p` runs need the namespaced form `/evalgrill:evalgrill`: the bare alias doesn't resolve there (observed at 2.1.227).
- With the opt-in Bash sandbox enabled, the first cold-cache `uv run` prompts for PyPI domains; allow `pypi.org` and `files.pythonhosted.org` in `sandbox.network.allowedDomains`.

## Testing

Everything a PR needs runs offline, with no secrets:

```bash
claude plugin validate . --strict                                  # marketplace manifest
claude plugin validate .claude-plugin/plugin.json --strict         # plugin manifest + skill frontmatter
uv run scripts/check_pack.py demo/golden-pack                      # schema + referential integrity
uv run scripts/audit_pack.py demo/golden-pack --runner replay      # all seven detections
uv run tests/test_export_braintrust.py                             # contract tests, one per surface
uv run tests/test_export_langsmith.py
uv run tests/test_export_phoenix.py
uv run tests/test_judge_runner.py
uv run tests/acceptance_30.py                                      # the full acceptance bar
```

Note: the plugin-manifest validate exits 1 if you keep a local `CLAUDE.md` at the repo root (a benign warning; the plugin runtime ignores plugin-root CLAUDE.md). Fresh clones pass clean.

CI runs the contract tests and the acceptance run on every PR. The live platform smokes (`live-smoke.yml`) need maintainer secrets and run on dispatch/release only; you do not need platform accounts to contribute.

## The Demo Corpus is a fixture

`demo/golden-pack/fixtures/` contains deliberately defective artifacts: a vague rubric criterion, a missing veto, a judge that contradicts human labels. The acceptance bar asserts these defects are detected. **Do not fix them.** A PR that "cleans up" the fixtures breaks the test suite by design. The spoiler map in [`demo/README.md`](demo/README.md) lists every plant.

## Pull requests

- Target `main`, one concern per PR. Small PRs get reviewed; big ones get closed.
- [Conventional commits](https://www.conventionalcommits.org/), under 50 words, short bullets when a body is needed.
- No `Co-Authored-By` trailers or generated-with footers.
- Say what changed and why in the description; link the issue it resolves.
- All offline checks above must pass.

## License

By contributing you agree your contributions are licensed under [Apache-2.0](LICENSE), the project license.
