---
status: accepted
---

# Subscription-first judge execution via `claude -p` behind a provider-agnostic Judge Runner

EvalGrill v0.1 executes judge calibration (never agent rollouts), and the default Judge Runner shells out to the locally authenticated Claude Code CLI (`claude -p`) rather than calling a model API. Chosen so users calibrate with their existing Claude subscription — zero API-key setup — which fits a skill-first, dogfood-first product. The runner is an interface, not a hardcoded path: API-based runners (e.g. matching the judge model an eval platform will actually use) can be added later without touching canonical artifacts.

## Consequences

- Calibration results depend on the local CLI's model selection; the calibration report must record which model/version ran (the envelope's `modelUsage`, persisted with each verdict).
- `claude -p` mechanics were validated empirically on 2026-08-10 — GO. The parts that are product contract, not research trivia:
  - Verified invocation: `claude -p --model <pinned> --effort <level> --output-format json --json-schema <verdict-schema> --setting-sources "" --tools "" --strict-mcp-config --disable-slash-commands --no-session-persistence`, run from a neutral cwd with a caller-enforced timeout (`subprocess.run(timeout=)` — the CLI has no timeout flag).
  - `--setting-sources ""` is mandatory: without it, parent-session CLAUDE.md leaks into judge context. `--bare` is forbidden: it isolates but kills subscription OAuth (that's the API-key runner's path).
  - `--json-schema` is mandatory: prompt-only "return raw JSON" gets refused by the default persona; the validated verdict arrives pre-parsed in `structured_output`.
  - Error handling branches on the envelope's `is_error`, never `subtype` (which stays "success" on API errors). `--fallback-model` is avoided (can retract structured output).
  - Watch-item: docs signal `--bare` may become the `-p` default, which would break subscription OAuth for scripted calls — preflight with `claude auth status`.
  - Full evidence trail: GitHub issue #2 and the `research/claude-p-judge-runner` branch (research findings stay off `main` by policy).
