# Integrations

Thin harness layer: each subdirectory documents how one agent harness installs and invokes the canonical `skills/` tree ([ADR-0003](../docs/adr/0003-canonical-skills-thin-integrations.md)). Integrations may change invocation; they must not change EvalGrill semantics.

- [claude-code/](claude-code/README.md): plugin install, dev loop
- [codex/](codex/README.md): manual symlink install

No other harnesses (gemini, cursor, opencode) until real demand, and no `npx skills add`.
