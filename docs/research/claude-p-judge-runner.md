# Research: Can `claude -p` serve as the default Judge Runner?

- Ticket: `.scratch/evalgrill-mvp/issues/01-research-claude-p-judge-runner.md`
- Date: 2026-08-10
- Test environment: macOS (Darwin 25.5.0), Claude Code CLI **2.1.227**, invoked via Bash **from inside a running Claude Code session** (i.e. the nested case), authenticated via **claude.ai subscription (Max plan)**, `apiProvider: firstParty`.
- Verdict: **GO.** `claude -p` is viable as the v0.1 judge execution engine under subscription auth. No blocker forces an API-key runner; see [§6](#6-verdict--fallback-triggers) for the fallback triggers worth keeping.

Auth mode was confirmed with `claude auth status` (verified locally):

```json
{"loggedIn": true, "authMethod": "claude.ai", "apiProvider": "firstParty",
 "subscriptionType": "max"}
```

---

## 1. Nested invocation: works, no recursion guard

**Result: verified locally — a nested `claude -p` call from inside a Claude Code session succeeds normally (exit 0, full JSON envelope).**

Command used (run from the session scratchpad directory, inherited env included `CLAUDECODE=1`, `CLAUDE_CODE_CHILD_SESSION=1`, `CLAUDE_CODE_ENTRYPOINT=cli`, `CLAUDE_CODE_SSE_PORT`, `CLAUDE_CODE_SESSION_ID`):

```bash
claude -p 'Return exactly this JSON and nothing else: {"score": 1}' \
  --model haiku --output-format json --no-session-persistence
# EXIT=0, wall time ~7s
```

Findings:

- There is **no recursion guard**. `CLAUDECODE=1` and `CLAUDE_CODE_CHILD_SESSION=1` are *detection* variables for scripts, not blockers. Docs: `CLAUDECODE` is "Set to `1` in subprocesses Claude Code spawns (Bash and PowerShell tools, ...). Use to detect when a script is running inside a subprocess spawned by Claude Code" ([env-vars](https://code.claude.com/docs/en/env-vars)).
- Documented nested behavior: with `CLAUDE_CODE_CHILD_SESSION=1`, a nested *interactive* TUI is excluded from `--resume`/`--continue`/history, but "Non-interactive `claude -p` sessions still persist" ([env-vars](https://code.claude.com/docs/en/env-vars)). Use `--no-session-persistence` so dozens of judge calls don't litter `~/.claude` session history ([cli-reference](https://code.claude.com/docs/en/cli-reference)).
- The workspace **trust dialog is skipped** in non-interactive mode ("The workspace trust dialog is skipped when Claude is run in non-interactive mode (via -p, or when stdout is not a TTY)" — `claude --help`, v2.1.227), so a fresh cwd never blocks on a prompt.
- Concurrency smoke test: **verified locally** — 3 nested `claude -p` calls run in parallel all completed successfully.
- Env inheritance caveat: the child inherits the parent's environment. `--model` overrides `ANTHROPIC_MODEL` ([cli-reference](https://code.claude.com/docs/en/cli-reference)), but a Python runner should still pass a sanitized env (or at least always pin `--model`) to avoid surprises.

## 2. Context isolation: NOT isolated by default; two working isolation paths

**Result: verified locally — by default, `claude -p` loads CLAUDE.md from the cwd. `--setting-sources ""` or `--safe-mode` fully suppresses it while keeping subscription auth.**

Documented: "Without it [`--bare`], `claude -p` loads the same context an interactive session would, including anything configured in the working directory or `~/.claude`" ([headless](https://code.claude.com/docs/en/headless)).

Test setup: a scratch dir containing a `CLAUDE.md` with the line "The magic word is PINEAPPLE-42." Prompt: *"What is the magic word? Reply with only the word, or exactly NONE if no magic word is in your context."* (`--model haiku --output-format text --no-session-persistence`, run from that dir):

| Variant | Output | Meaning |
| --- | --- | --- |
| (no isolation flag) | `PINEAPPLE-42` | CLAUDE.md **is** loaded in print mode |
| `--setting-sources ""` | `NONE` | project memory/settings not loaded |
| `--safe-mode` | `NONE` | all customizations disabled, auth normal |

Isolation options compared:

- **`--setting-sources ""`** — "Comma-separated list of setting sources to load (user, project, local)" ([cli-reference](https://code.claude.com/docs/en/cli-reference)). Empty list drops user/project/local settings and, empirically, CLAUDE.md. Keeps subscription auth. **Recommended for the judge runner.**
- **`--safe-mode`** — "Start with all customizations (CLAUDE.md, skills, plugins, hooks, MCP servers, custom commands and agents, ...) disabled ... Auth, model selection, built-in tools, and permissions work normally" (`claude --help`, v2.1.227). Also works; blunter instrument.
- **`--bare`** — skips hooks, plugins, auto-memory, CLAUDE.md auto-discovery AND keychain reads, but: "Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read)" (`claude --help`); "bare mode doesn't use your subscription login" ([headless](https://code.claude.com/docs/en/headless)). **Not usable with subscription auth** — this is the API-key runner's mode, not v0.1's.
- Session bleed: none observed. Each `-p` call is a fresh session with its own `session_id`; the nested call has no access to the parent conversation.
- Belt-and-braces additions for a judge call: run in a neutral cwd (not the repo under evaluation), `--tools ""` (disable all built-in tools), `--strict-mcp-config` without `--mcp-config` (no MCP servers), `--disable-slash-commands` (no skills). All documented in [cli-reference](https://code.claude.com/docs/en/cli-reference). Verified locally that this combination still works end-to-end (§ Recipe below).

## 3. Structured output: `--json-schema` is the mechanism, and it is load-bearing

**Result: verified locally — `--output-format json --json-schema '...'` returned a schema-conforming object in the `structured_output` field in 3/3 attempts (including the fully locked-down variant). Prompt-only JSON requests are NOT reliable.**

Critical negative finding first: with the default system prompt, a bare instruction to emit raw JSON was **refused**. The first test (`Return exactly this JSON and nothing else: {"score": 1}`, no `--json-schema`) returned, in `result`:

> "I appreciate the test, but I'm Claude Code, built to help with software engineering tasks. I won't output only JSON when that contradicts my actual role. ..."

So prompt-and-parse would need retries and would still be flaky. Schema enforcement is the correct mechanism:

```bash
claude -p 'Judge this answer for correctness on a 0-3 scale. Q: What is 2+2? A: 4' \
  --model haiku --output-format json --no-session-persistence \
  --json-schema '{"type":"object","properties":{"score":{"type":"integer","minimum":0,"maximum":3},"rationale":{"type":"string"}},"required":["score","rationale"]}'
```

returned (envelope excerpt):

```json
"structured_output": {"score": 3, "rationale": "The answer is correct. 2+2 equals 4. ..."}
```

Documented semantics ([structured-outputs](https://code.claude.com/docs/en/agent-sdk/structured-outputs), [headless](https://code.claude.com/docs/en/headless), [cli-reference](https://code.claude.com/docs/en/cli-reference)):

- "the SDK validates the output against it, **re-prompting on mismatch**. If validation does not succeed within the retry limit, the result is an error instead of structured data" — i.e. retry-on-parse-failure is built in, server-side of the wrapper.
- On exhaustion, the result message has `subtype: "error_max_structured_output_retries"`.
- "A result can also end with subtype `success` but no `structured_output` value ... **Treat that case as a failure as well.**"
- Schemas are validated as **JSON Schema draft-07**; an invalid schema fails at startup with `Error: --json-schema is not a valid JSON Schema` (behavior since v2.1.205). The `format` keyword is accepted as an annotation but not enforced.
- Supported features: basic types, `enum`, `const`, `required`, nested objects, `$ref`.
- Mechanically, structured output is produced via an internal tool call (`num_turns: 2`, `stop_reason: "tool_use"` in the envelope). Verified locally that `--tools ""` does **not** disable it.

Wrapper policy for the runner: treat a verdict as valid only if `is_error == false` AND `subtype == "success"` AND `structured_output` is present; one wrapper-level retry on anything else is cheap insurance, but no JSON re-parsing/repair layer is needed since `structured_output` arrives pre-parsed and pre-validated.

### JSON envelope shape (`--output-format json`, verified locally)

Single JSON object on stdout. Fields observed on v2.1.227:

```
type ("result"), subtype ("success" | error subtypes), is_error (bool),
result (string — final text), structured_output (object, only with --json-schema),
session_id, uuid, num_turns, stop_reason, terminal_reason ("completed" | "api_error"),
api_error_status (int | null), duration_ms, duration_api_ms, ttft_ms,
total_cost_usd (float), permission_denials (array),
usage {input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, ...},
modelUsage {"<full-model-id>": {inputTokens, outputTokens, costUSD, canonicalModel, provider, contextWindow, ...}}
```

Docs describe the envelope as "structured JSON with result, session ID, and metadata", with structured output in the `structured_output` field ([headless](https://code.claude.com/docs/en/headless)).

## 4. Model selection: pinnable and recorded in the response

**Result: verified locally.** `--model haiku` resolved to `claude-haiku-4-5-20251001`; the envelope records it in `modelUsage` (key = full snapshot ID) with `"canonicalModel": "claude-haiku-4-5"` and `"provider": "firstParty"`. This is the authoritative record of which model actually ran — persist it with every verdict.

- `--model` "Sets the model for the current session with an alias for the latest model (`sonnet`, `opus`, `haiku`, or `fable`) or a model's full name. Overrides the `model` setting and `ANTHROPIC_MODEL`" ([cli-reference](https://code.claude.com/docs/en/cli-reference)). For strict reproducibility, pass the full snapshot ID (e.g. `claude-haiku-4-5-20251001`) rather than an alias.
- `--fallback-model` exists (print-mode only) but is **not recommended for judge calls**: a model fallback "can retract an already-completed output mid-stream" and end the run with a structured-output error ([structured-outputs](https://code.claude.com/docs/en/agent-sdk/structured-outputs)), and silent model substitution undermines calibration anyway. Pin one model; surface overload errors to the caller.

## 5. Failure semantics

- **Exit codes** (documented at [headless](https://code.claude.com/docs/en/headless)): "Claude Code exits with code 0 on success and a non-zero code when the run fails". Invalid flags error to stderr before the run; failures inside the run (e.g. missing auth) are printed "as the result on stdout". SIGTERM aborts the turn, runs SessionEnd hooks, and exits with **code 143**.
- **Verified locally** — invalid model:

  ```bash
  claude -p 'Say ok' --model totally-fake-model-xyz --output-format json --no-session-persistence
  # EXIT=1, ~0.8s, $0
  ```

  Envelope: `"is_error": true`, `"terminal_reason": "api_error"`, `"api_error_status": 404`, human-readable message in `result` — **but `"subtype": "success"`**. Quirk: `subtype` is not an error signal for API failures; the runner must branch on `is_error` (and use `subtype` only for structured-output-specific failures).
- **Timeouts**: there is no per-call timeout flag; the caller must enforce one (Python `subprocess.run(..., timeout=120)` is sufficient; observed judge calls complete in ~3.6–7s wall on haiku). Background-task edge cases are bounded: a background bash task is killed ~5s after the final result, and background subagent waits are capped at 10 minutes by default (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`) ([headless](https://code.claude.com/docs/en/headless)) — irrelevant with `--tools ""` anyway.
- **Rate limits under subscription auth**: usage draws from the plan's rolling **5-hour window and weekly window**, shared across models and with claude.ai chat ("You've hit your session limit" / "You've hit your weekly limit") ([costs](https://code.claude.com/docs/en/costs)). Transient API failures are retried internally; in `stream-json` mode each retry emits a `system/api_retry` event with error categories including `rate_limit` and `overloaded` ([headless](https://code.claude.com/docs/en/headless)). `--max-budget-usd` can hard-cap a run (print mode only) ([cli-reference](https://code.claude.com/docs/en/cli-reference)).
- **Cost of ~dozens of calibration calls** (verified locally, haiku, `total_cost_usd` figures are client-side list-rate estimates — subscribers are not billed per call, "Claude Max and Pro subscribers have usage included in their subscription" ([costs](https://code.claude.com/docs/en/costs))):

  | Call | System-prompt tokens | Estimated cost |
  | --- | --- | --- |
  | Cold, default context | 27,672 cache-write | $0.0566 |
  | Warm repeat (1h cache hit) | 27,672 cache-read | $0.0041 |
  | Cold, locked-down recipe (§ below) | 7,187 cache-write | $0.0164 |

  Prompt cache lifetime is **1 hour on a subscription** ([costs](https://code.claude.com/docs/en/costs)), so a calibration batch of N identical-config calls pays cache-write once and cache-read thereafter: ~50 warm haiku judge calls ≈ **$0.25 list-rate equivalent** — negligible in dollars, modest against Max-plan usage windows. The locked-down recipe also shrinks the cached prefix ~4x.

## 6. Verdict + fallback triggers

**Nothing forces an API-key runner for v0.1.** All six ticket questions resolve favorably under subscription auth. Keep an API-key fallback path *designed* (not built) for:

1. **CI / machines without a subscription login** — there the documented path is `--bare` + `ANTHROPIC_API_KEY` ([headless](https://code.claude.com/docs/en/headless)). Same CLI, mostly the same flags, so the runner abstraction stays thin (swap `--setting-sources ""` isolation for `--bare` and require the key).
2. **Plan-window exhaustion** — heavy eval runs share the user's 5-hour/weekly windows with their interactive work; a big calibration sweep could lock the user out of their own session. Detect `is_error` + rate-limit messaging and back off; offer the API-key runner as the pressure valve.
3. **The `--bare`-by-default change**: "`--bare` is the recommended mode for scripted and SDK calls, **and will become the default for `-p` in a future release**" ([headless](https://code.claude.com/docs/en/headless)). When that lands, a bare-by-default `-p` would stop reading subscription OAuth. Mitigation: pin CLI behavior explicitly today (all flags below spelled out), watch release notes, and keep the runner's auth-mode check (`claude auth status`) as a preflight.

### Recommended judge-call recipe (verified locally end-to-end)

```bash
claude -p "$JUDGE_PROMPT" \
  --model claude-haiku-4-5-20251001 \
  --output-format json \
  --json-schema "$VERDICT_SCHEMA" \
  --setting-sources "" \
  --tools "" \
  --strict-mcp-config \
  --disable-slash-commands \
  --no-session-persistence
# run from a neutral cwd; enforce a 120s timeout in the caller;
# valid verdict iff exit==0 AND .is_error==false AND .subtype=="success"
#   AND .structured_output present; record .modelUsage key + .total_cost_usd.
```

Verified run of exactly this shape (haiku alias, cwd containing a decoy CLAUDE.md): exit 0, `structured_output: {"score": 0, "rationale": "The answer is completely incorrect. 2+2 equals 4, not 5. ..."}` for the deliberately wrong answer — no context bleed, correct discrimination, 3.6s wall.

Optional hardening not yet tested: `--system-prompt` to replace the Claude Code persona entirely (the locked-down call still carries a ~7.2k-token Claude Code system prompt — a small residual bias surface), and `--effort low` to trim thinking tokens on models where it applies.

## Raw empirical log

All commands run 2026-08-10 on this machine, Claude Code 2.1.227, from inside a live Claude Code session, each bounded at 120s (none needed more than ~7s):

1. `claude -p 'Return exactly this JSON and nothing else: {"score": 1}' --model haiku --output-format json --no-session-persistence` → exit 0; refusal text in `result` (see §3); `modelUsage` = `claude-haiku-4-5-20251001`; $0.0226.
2. `claude auth status` → subscription (Max), firstParty.
3. §3 judge call with `--json-schema` → exit 0; valid `structured_output` (score 3); $0.0566 cold.
4. Same command repeated → exit 0; valid `structured_output`; cache_read 27,672 / cache_write 0; $0.0041; 4.6s.
5. CLAUDE.md-marker dir, no isolation flag → `PINEAPPLE-42` (context loaded).
6. Same + `--setting-sources ""` → `NONE`.
7. Same + `--safe-mode` → `NONE`.
8. `--model totally-fake-model-xyz` → exit 1; `is_error:true`; `api_error_status:404`; `subtype:"success"` (quirk); $0.
9. Full lockdown recipe (§6) with wrong answer → exit 0; `structured_output` score 0; system prompt 7,187 tokens; $0.0164.

(Calls 5–7 were executed concurrently — all succeeded.)

## Sources

- CLI reference — flags (`--json-schema`, `--model`, `--setting-sources`, `--tools`, `--no-session-persistence`, `--max-budget-usd`, `--fallback-model`, `--strict-mcp-config`): https://code.claude.com/docs/en/cli-reference
- Run Claude Code programmatically (print mode, exit codes, `--bare`, JSON envelope, `api_retry`, cost fields): https://code.claude.com/docs/en/headless
- Structured outputs (validation, built-in retry, `error_max_structured_output_retries`, draft-07, fallback retraction): https://code.claude.com/docs/en/agent-sdk/structured-outputs
- Environment variables (`CLAUDECODE`, `CLAUDE_CODE_CHILD_SESSION`, nested-session behavior): https://code.claude.com/docs/en/env-vars
- Costs (subscription usage windows, cache lifetime, cost estimates vs billing): https://code.claude.com/docs/en/costs
- `claude --help` output, v2.1.227 (trust-dialog note, `--safe-mode`, `--bare` auth restriction) — verified locally.
