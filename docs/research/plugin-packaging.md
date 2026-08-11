# Claude Code plugin packaging for EvalGrill (skills + bundled uv scripts)

Research ticket: `.scratch/evalgrill-mvp/issues/05-research-plugin-packaging.md`
Date: 2026-08-10. Verified against Claude Code **2.1.227** (`claude --version`) on macOS, with `uv 0.9.26`.

Primary sources (all claims below cite one of these):

- Create plugins: <https://code.claude.com/docs/en/plugins>
- Plugins reference: <https://code.claude.com/docs/en/plugins-reference>
- Skills: <https://code.claude.com/docs/en/skills>
- Plugin marketplaces: <https://code.claude.com/docs/en/plugin-marketplaces>
- Skill authoring best practices: <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>
- Sandboxed Bash: <https://code.claude.com/docs/en/sandboxing>

Items marked **[verified locally]** were reproduced with the CLI on this machine; the exact command is quoted. Nothing was installed permanently (session-only `--plugin-dir` loads; the one marketplace add was removed in the same step).

---

## 1. Plugin manifest

- **File**: `.claude-plugin/plugin.json` at the plugin root. Only `plugin.json` goes inside `.claude-plugin/`; every component directory (`skills/`, `commands/`, `agents/`, `hooks/`, `scripts/`, `bin/`, …) must be at the plugin root, **not** inside `.claude-plugin/`. (<https://code.claude.com/docs/en/plugins-reference#plugin-directory-structure>)
- **The manifest itself is optional**: without it, Claude Code auto-discovers components in default locations and derives the plugin name from the directory name. Use a manifest to pin the name (which is the skill namespace) and add metadata. (<https://code.claude.com/docs/en/plugins-reference#plugin-manifest-schema>)
- **Required field**: if a manifest exists, `name` is the only required field — "Unique identifier (kebab-case, no spaces)". It is used for namespacing (`/plugin-name:skill-name`). (<https://code.claude.com/docs/en/plugins-reference#required-fields>)
- **Optional fields**: `displayName`, `version`, `description`, `author` (`{name, email?, url?}`), `homepage`, `repository`, `license`, `keywords`, `metadata`, `defaultEnabled`, plus component-path overrides (`skills`, `commands`, `agents`, `hooks`, `mcpServers`, `lspServers`, `outputStyles`, `workflows`, `experimental.*`, `userConfig`, `dependencies`). Unrecognized top-level fields are ignored at load time (warnings under `claude plugin validate --strict`). (<https://code.claude.com/docs/en/plugins-reference#plugin-manifest-schema>)
- **Version behavior**: setting `version` pins the plugin — users only get updates when you bump it. Omitting it falls back to the marketplace entry version, then the git commit SHA. For a dogfooding repo, omitting `version` (SHA-based) avoids "forgot to bump" staleness; for published releases, set and bump it. (<https://code.claude.com/docs/en/plugins-reference#version-management>)
- **Path rules**: all custom component paths must be relative to the plugin root and start with `./`. The `skills` field *adds to* the default `skills/` scan; most other path fields *replace* their defaults. (<https://code.claude.com/docs/en/plugins-reference#path-behavior-rules>)
- **[verified locally]** A manifest with `name`, `description`, `version`, `author`, `license`, `keywords` passes: `claude plugin validate <plugin-dir>` → `✔ Validation passed` (also with `--strict`).

## 2. How skills ship inside a plugin

- **Location**: `skills/<skill-name>/SKILL.md` directories at the plugin root (a legacy `commands/` dir of flat `.md` files also works; docs say "Use `skills/` for new plugins"). Skills are auto-discovered on install — no registration list needed. (<https://code.claude.com/docs/en/plugins-reference#skills>)
- **Frontmatter**: *all fields are optional* in Claude Code; only `description` is recommended (Claude uses it to decide when to auto-invoke). Full field list: `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell`, `metadata`, `license`, `compatibility`. (<https://code.claude.com/docs/en/skills#frontmatter-reference>)
- **Name/description constraints** (Agent Skills spec, enforced on claude.ai/API packaging; good hygiene in Claude Code too): `name` max 64 chars, lowercase letters/numbers/hyphens only, no XML tags, no reserved words "anthropic"/"claude"; `description` non-empty, max 1,024 chars, no XML tags, written in third person. (<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#skill-structure>) In Claude Code's skill listing, combined `description` + `when_to_use` text is truncated at 1,536 chars. (<https://code.claude.com/docs/en/skills#frontmatter-reference>)
- **Slash-command name derivation**: for a plugin skill the command is `/<plugin-name>:<skill-dir-name>`, with the frontmatter `name` replacing the last segment if set (`my-plugin/skills/review/SKILL.md` → `/my-plugin:review`; with `name: fancy` → `/my-plugin:fancy`). The **bare** `/<skill-name>` also invokes the skill unless another command already uses that name (v2.1.216+). So EvalGrill's router skill dir `skills/evalgrill/` in plugin `evalgrill` is typable as both `/evalgrill:evalgrill` and bare `/evalgrill`. (<https://code.claude.com/docs/en/skills#how-a-skill-gets-its-command-name>)
- Plugin skills are always namespaced, so they never conflict with (or get overridden by) personal/project/bundled skills. `skillOverrides` does not apply to plugin skills — they're managed via `/plugin`. (<https://code.claude.com/docs/en/skills#where-skills-live>, <https://code.claude.com/docs/en/skills#override-skill-visibility-from-settings>)
- Router pattern control knobs: `disable-model-invocation: true` = user-only trigger; `user-invocable: false` = model-only background knowledge. (<https://code.claude.com/docs/en/skills#control-who-invokes-a-skill>)
- **[verified locally]** `claude --plugin-dir <dir> plugin details evalgrill` listed all 5 skills (`analyze-eval-problem, build-eval-dataset, design-eval-rubric, evalgrill, validate-eval-design`) under "Component inventory / Skills (5)" with ~281 always-on tokens projected.

## 3. Referencing bundled scripts from SKILL.md

Two documented path variables matter:

| Variable | Resolves to | Documented substitution scope |
| --- | --- | --- |
| `${CLAUDE_PLUGIN_ROOT}` | Absolute path to the plugin's installation directory (the cache copy for marketplace installs) | Skill and agent content: "anywhere the placeholder appears"; also exported as env var to hook/MCP/LSP processes (<https://code.claude.com/docs/en/plugins-reference#environment-variables>) |
| `${CLAUDE_SKILL_DIR}` | The directory containing the skill's `SKILL.md` — for plugin skills, the skill's subdirectory *within* the plugin, not the plugin root | Skill markdown content **and** `Bash(...)` rules in `allowed-tools` frontmatter (<https://code.claude.com/docs/en/skills#available-string-substitutions>) |

- For **shared** scripts used by several skills, put them at the plugin root (`scripts/`) and reference `${CLAUDE_PLUGIN_ROOT}/scripts/foo.py` from any SKILL.md body. `scripts/` at the plugin root is the documented convention ("Hook and utility scripts"). (<https://code.claude.com/docs/en/plugins-reference#plugin-directory-structure>)
- For **per-skill** supporting files, the documented skill layout is `SKILL.md` + optional `reference.md` / `examples.md` / `scripts/` inside the skill directory, referenced with relative links so Claude loads them only when needed (progressive disclosure; keep SKILL.md under 500 lines, references one level deep). (<https://code.claude.com/docs/en/skills#add-supporting-files>, <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#progressive-disclosure-patterns>)
- **Runtime path reality**: marketplace-installed plugins are copied to `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, so `${CLAUDE_PLUGIN_ROOT}` points into the cache and **changes on every update**; never hard-code it and never write state there (old versions are garbage-collected after ~14 days). `--plugin-dir` and `@skills-dir` plugins are used in place. (<https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution>)
- **Path traversal is blocked**: installed plugins cannot reference files outside their own directory (`../shared-utils` breaks after install, because only the plugin dir is copied to the cache). All scripts EvalGrill skills call must live inside the plugin directory. (<https://code.claude.com/docs/en/plugins-reference#path-traversal-limitations>)
- Alternative for executables: a `bin/` directory at the plugin root is added to the Bash tool's `PATH` while the plugin is enabled, so a wrapper there is invokable as a bare command. (<https://code.claude.com/docs/en/plugins-reference#file-locations-reference>)
- Permission pre-approval pattern (documented with `${CLAUDE_SKILL_DIR}`): use the same variable in the body command and the `allowed-tools` rule so the script runs without a prompt:

  ```yaml
  allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/render.sh *)
  ```

  (<https://code.claude.com/docs/en/skills#available-string-substitutions>)

## 4. Running bundled Python via uv + PEP 723

- **No first-class uv/PEP 723 pattern exists in the official Claude Code or Anthropic skills docs.** The skill-authoring guidance covers bundled Python scripts generically ("Run `python scripts/analyze_form.py ...`", "List required packages in your SKILL.md") but never mentions uv or inline script metadata. (<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#advanced-skills-with-executable-code>)
- What *is* documented and composes cleanly:
  - Skills "can bundle and run scripts in any language"; scripts are executed via the Bash tool, so they follow normal Bash permission rules. (<https://code.claude.com/docs/en/skills#generate-visual-output>)
  - `allowed-tools` Bash rules in frontmatter pre-approve the exact command for the invoking turn (see §3). A skill instruction like ``Run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/check_dataset.py <args>` `` plus a matching allow rule is the closest documented pattern.
  - For dependencies that should persist across sessions/updates (e.g. uv's cache or a venv), the documented location is `${CLAUDE_PLUGIN_DATA}` (`~/.claude/plugins/data/<id>/`), which survives plugin updates — explicitly recommended for "Python virtual environments … and caches". (<https://code.claude.com/docs/en/plugins-reference#persistent-data-directory>) In practice uv's own global cache (`~/.uv`/`~/.cache/uv`) makes this unnecessary for PEP 723 scripts.
- **Sandbox constraints** (relevant only if the user has enabled the opt-in Bash sandbox): sandboxed commands can write only to the cwd and session temp dir, and **no network domains are pre-allowed** — the first `uv run` that needs to download from PyPI triggers a domain-approval prompt (`pypi.org`, `files.pythonhosted.org`) unless those are in `sandbox.network.allowedDomains`, or `uv` is listed in `excludedCommands`. The sandbox is not on by default; it's enabled per-project via `/sandbox` or `sandbox.enabled` in settings. There is no uv- or PyPI-specific carve-out in the docs. (<https://code.claude.com/docs/en/sandboxing>)
- **[verified locally]** PEP 723 inline deps resolve fine with the system uv:

  ```
  $ uv run evalgrill/scripts/check_dataset.py     # script has `# /// script` block requiring pyyaml
  Installed 1 package in 4ms
  ok: pyyaml 6.0.3 python 3.14.2
  ```

  (uv 0.9.26; run from the scratchpad test plugin.)
- Practical guardrails from the docs to adopt: state the uv prerequisite explicitly in SKILL.md ("Avoid assuming tools are installed"), make execution intent explicit ("Run X" vs "See X"), and have scripts handle their own errors verbosely. (<https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>)

## 5. Local dev / install flow for dogfooding

**A marketplace entry is NOT mandatory.** Three no-marketplace paths exist, plus the marketplace path for distribution:

1. **`--plugin-dir` (recommended for dev)** — session-only, loads the plugin in place, no state written:

   ```bash
   claude --plugin-dir ./plugin        # also accepts a .zip; repeatable for multiple plugins
   ```

   Edits to SKILL.md and other components are picked up with `/reload-plugins` (no restart). A `--plugin-dir` plugin with the same name as an installed one takes precedence for the session. (<https://code.claude.com/docs/en/plugins#test-your-plugins-locally>)
   **[verified locally]** `claude --plugin-dir <dir> plugin list` showed `Session-only plugins (--plugin-dir / --plugin-url): ❯ evalgrill@inline … Status: ✔ loaded` without touching any settings file.

2. **Skills-directory plugin** — any folder under `~/.claude/skills/` (personal) or `<cwd>/.claude/skills/` (project, gated on workspace trust) containing `.claude-plugin/plugin.json` auto-loads next session as `<name>@skills-dir`, discovered **in place** (not copied), no marketplace, no install step. `claude plugin init <name>` scaffolds one. Caveat: project-scope `@skills-dir` plugins load only from the `.claude/skills/` of the directory where Claude Code starts (no walk-up), and SKILL.md edits are live while other components need `/reload-plugins`. (<https://code.claude.com/docs/en/plugins-reference#skills-directory-plugins>)

3. **`--plugin-url`** — session-only load of a hosted `.zip` (CI artifacts). (<https://code.claude.com/docs/en/plugins#test-your-plugins-locally>)

4. **Local marketplace (persistent install)** — needed only when you want the plugin *installed* (persisting across sessions via `enabledPlugins`) or distributed:

   ```bash
   claude plugin marketplace add ./path/to/marketplace-root   # dir containing .claude-plugin/marketplace.json
   claude plugin install evalgrill@evalgrill-dev [--scope user|project|local]
   ```

   or interactively `/plugin marketplace add ./...` + `/plugin install ...`. Minimal `marketplace.json` requires `name`, `owner.name`, and a `plugins` array whose entries need `name` + `source` (relative `./` paths resolve against the marketplace root). (<https://code.claude.com/docs/en/plugin-marketplaces#marketplace-schema>)
   **Dogfooding caveat**: marketplace installs are **copied to `~/.claude/plugins/cache`**, so live edits in the repo are not seen until `claude plugin marketplace update` + `claude plugin update` — which is why `--plugin-dir` is the better inner loop. (<https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution>)
   **[verified locally]** Full roundtrip with the test marketplace, then removed:

   ```
   $ claude plugin marketplace add <scratchpad>/evalgrill-plugin-test
   ✔ Successfully added marketplace: evalgrill-dev (declared in user settings)
   $ claude plugin marketplace remove evalgrill-dev
   ✔ Successfully removed marketplace: evalgrill-dev
   ```

   (Removing a marketplace also uninstalls plugins installed from it — nothing was installed here.)

Validation and inspection commands **[all verified locally via `--help` and/or execution]**:

```bash
claude plugin validate ./plugin            # plugin.json + skill/agent/command frontmatter + hooks.json
claude plugin validate ./plugin --strict   # warnings → errors (CI)
claude plugin validate .                   # marketplace.json (run at marketplace root)
claude --plugin-dir ./plugin plugin details evalgrill   # component inventory + token cost
claude plugin eval [target]                # run evals/**/case.yaml against a plugin (exists in 2.1.227)
```

To later require the plugin for everyone in the repo: `extraKnownMarketplaces` + `enabledPlugins` in `.claude/settings.json`. (<https://code.claude.com/docs/en/plugin-marketplaces#require-marketplaces-for-your-team>)

## 6. Recommended skeleton for the scaffold ticket (12)

Layout below assumes the repo doubles as its own marketplace (repo root = marketplace root) so a persistent install stays possible, while day-to-day dev uses `claude --plugin-dir ./plugin`. The whole plugin lives under one directory because installed plugins cannot reach outside their root (§3).

```text
EvalGrill/                                  # repo root = marketplace root
├── .claude-plugin/
│   └── marketplace.json                    # name: evalgrill-dev; plugins: [{name: evalgrill, source: ./plugin}]
└── plugin/                                 # plugin root (pass to --plugin-dir)
    ├── .claude-plugin/
    │   └── plugin.json                     # {"name": "evalgrill", "description": ...}  ← name = skill namespace
    ├── skills/
    │   ├── evalgrill/                      # thin router → /evalgrill:evalgrill AND bare /evalgrill
    │   │   └── SKILL.md
    │   ├── analyze-eval-problem/           # → /evalgrill:analyze-eval-problem
    │   │   ├── SKILL.md
    │   │   └── references/                 # optional per-skill deep docs, linked one level from SKILL.md
    │   ├── build-eval-dataset/             # → /evalgrill:build-eval-dataset
    │   │   ├── SKILL.md
    │   │   └── references/
    │   ├── design-eval-rubric/             # → /evalgrill:design-eval-rubric
    │   │   ├── SKILL.md
    │   │   └── references/
    │   └── validate-eval-design/           # → /evalgrill:validate-eval-design
    │       ├── SKILL.md
    │       └── references/
    ├── scripts/                            # SHARED uv/PEP 723 scripts, referenced as
    │   ├── check_dataset.py                #   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py ...`
    │   └── ...                             #   shebang: #!/usr/bin/env -S uv run --script  (+ chmod +x)
    ├── README.md
    └── CHANGELOG.md
```

Scaffold notes:

- Skill dir names are already valid skill names (lowercase/hyphens, <64 chars, no reserved words) — no `name:` frontmatter needed except on the router if a different bare command is ever wanted.
- Router SKILL.md: give it `argument-hint` and route by invoking the four namespaced skills; consider `disable-model-invocation: true` on the router if it should be user-triggered only.
- Each SKILL.md that runs a shared script should carry a matching `allowed-tools` Bash rule (see §3/§4) and state the uv prerequisite.
- Omit `version` from `plugin.json` during MVP (SHA-versioned updates); add it when publishing.
- CI: `claude plugin validate ./plugin --strict` and `claude plugin validate .` (marketplace) — both exit non-zero on errors.

This exact structure (plugin manifest + 5 skills + shared `scripts/`) was assembled in the session scratchpad and passed `claude plugin validate` (strict), loaded via `--plugin-dir` with all 5 skills discovered, and its PEP 723 script ran under `uv run` — see the **[verified locally]** entries above.

---

## Open risks

1. **`${CLAUDE_PLUGIN_ROOT}` inside `allowed-tools` is not explicitly documented.** The skills page documents only `${CLAUDE_SKILL_DIR}` and `${CLAUDE_PROJECT_DIR}` substitution in `allowed-tools` Bash rules; the plugins reference says plugin placeholders resolve "anywhere" in *skill content*. Whether an `allowed-tools: Bash(uv run ${CLAUDE_PLUGIN_ROOT}/scripts/* ...)` rule expands correctly needs an interactive test at scaffold time; fallback is a per-skill relative rule via `${CLAUDE_SKILL_DIR}` or a broader `Bash(uv run *)` rule.
2. **uv is an undocumented dependency choice** — no official pattern, and users without uv installed will see the skill fail; SKILL.md must state the prerequisite and scripts should fail with a clear "install uv" message (docs: "Avoid assuming tools are installed").
3. **Sandbox users hit a PyPI domain prompt** on first cold-cache `uv run`; acceptable but worth a line in the plugin README (`pypi.org`, `files.pythonhosted.org` in `sandbox.network.allowedDomains`).
4. **Marketplace installs copy to a cache**, so anyone who dogfoods via `plugin install` instead of `--plugin-dir` will silently run stale code until they update; the README should prescribe the `--plugin-dir` + `/reload-plugins` loop.
5. **Docs are release-coupled** (multiple "requires v2.1.2xx" behaviors, e.g. bare-name aliasing of namespaced skills is v2.1.216+); re-verify against the shipping Claude Code version at release time.
6. `claude plugin init` scaffolds into `~/.claude/skills/` (skills-dir plugin), not into a repo — the scaffold ticket should create the tree by hand (or copy the validated scratchpad skeleton) rather than rely on `plugin init`.
