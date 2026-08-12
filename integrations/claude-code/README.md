# Claude Code

The primary harness: the repo root is the plugin ([ADR-0003](../../docs/adr/0003-canonical-skills-thin-integrations.md)). Requires [Claude Code](https://claude.com/claude-code) ≥ 2.1.216 and [uv](https://docs.astral.sh/uv/).

Install from inside any Claude Code session:

```
/plugin marketplace add hardness1020/EvalGrill
/plugin install evalgrill@evalgrill-dev
```

Or, to hack on it, clone and load in place (session-only):

```bash
git clone https://github.com/hardness1020/EvalGrill
cd EvalGrill
claude --plugin-dir .
```

Dev loop: edit skills, then `/reload-plugins` inside the session. The full loop and its gotchas (stale plugin-install cache, headless invocation, sandbox PyPI domains) live in [CONTRIBUTING.md](../../CONTRIBUTING.md).
