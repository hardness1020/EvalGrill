# Codex

Manual install: symlink each canonical `skills/<name>/` into Codex's skills directory. Symlinks, not copies, keep one canonical tree ([ADR-0003](../../docs/adr/0003-canonical-skills-thin-integrations.md)): the links point into the clone, so `git pull` updates everything and the repo-root `scripts/` and `schemas/` stay reachable.

```bash
git clone https://github.com/hardness1020/EvalGrill
mkdir -p ~/.agents/skills
for s in "$PWD"/EvalGrill/skills/*/; do
  ln -sfn "$s" ~/.agents/skills/"$(basename "$s")"
done
```

For a per-project install, use `<project>/.agents/skills` instead of `~/.agents/skills`.

Each skill ships an `agents/openai.yaml` sidecar with harness-facing display metadata; `SKILL.md` stays the canonical skill definition.

## Notes

- Skill bodies reference bundled scripts as `${CLAUDE_PLUGIN_ROOT}/scripts/...`. Outside Claude Code that variable is unset; it means the repo root of the clone the symlinks point into.
- [uv](https://docs.astral.sh/uv/) is required: all scripts are single-file PEP 723 scripts run via `uv run`, no environment setup.
- Optional [claude CLI](https://claude.com/claude-code) dependency: the validate phase's live Judge Runner (`audit_pack.py --runner claude-cli`) shells out to `claude -p` and needs a logged-in CLI (subscription auth, [ADR-0001](../../docs/adr/0001-subscription-first-judge-runner.md)). Without it, `--runner replay` keeps every detection deterministic and offline.
