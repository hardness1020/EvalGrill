# Contributing to EvalGrill

Thanks for your interest. Please read this before opening anything.

## Read this first

EvalGrill is at v0.1, dogfood stage: the design is still being validated against real use, and the maintainer is deliberately keeping scope tight. Small, focused contributions are welcome; large ones will probably be closed without review.

**Most likely to be accepted**

- Bug fixes with a reproduction
- Reliability and correctness fixes in the scripts (`plugin/scripts/`) and exporters
- Documentation fixes where the docs and the code disagree

**Least likely to be accepted**

- New features, new skills, or new export targets (the roadmap is tracked in [`docs/prd.md`](docs/prd.md))
- Large refactors or PRs touching many files at once
- Fixes to the planted defects in the Demo Corpus (see below: they are the test)

## Issues first

For anything non-trivial, open a GitHub issue before writing code. It saves you from building something that won't be merged. An acknowledged issue is not a promise the PR will be accepted.

Bug reports should include: what you ran, what you expected, what happened, and your Claude Code + uv versions.

## Development setup

Requires [Claude Code](https://claude.com/claude-code) ≥ 2.1.216 and [uv](https://docs.astral.sh/uv/). No Python environment setup: all scripts are single-file PEP 723 scripts run via `uv run`.

```bash
git clone https://github.com/hardness1020/EvalGrill
cd EvalGrill
claude --plugin-dir ./plugin   # loads the plugin in place, session-only
```

Edit skills, then `/reload-plugins` inside the session. Do not develop against `plugin install`: marketplace installs copy to a cache and silently run stale code. Details in the [plugin README](plugin/README.md).

## Testing

Everything a PR needs runs offline, with no secrets:

```bash
claude plugin validate ./plugin --strict                                  # manifest + skill frontmatter
uv run plugin/scripts/check_pack.py demo/golden-pack                      # schema + referential integrity
uv run plugin/scripts/audit_pack.py demo/golden-pack --runner replay      # all seven detections
uv run tests/test_export_braintrust.py                                    # contract tests, one per surface
uv run tests/test_export_langsmith.py
uv run tests/test_export_phoenix.py
uv run tests/test_judge_runner.py
uv run tests/acceptance_30.py                                             # the full acceptance bar
```

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
