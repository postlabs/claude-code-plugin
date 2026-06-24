# skills-src — single source for the shared authoring skills

`toast-creator/` is ONE plugin folder that serves two harnesses from one copy
of `scripts/`, `vendor/`, and `tests/`:

| harness | manifest | reads skills from |
|---------|----------|-------------------|
| Claude Code | `.claude-plugin/plugin.json` (+ root `.claude-plugin/marketplace.json`) | `./skills/` (auto-discovered) |
| Codex | `.codex-plugin/plugin.json` (+ root `.codex-plugin/marketplace.json`) | `./skills-codex/` (set via `"skills"`) |

The three authoring skills are the **same** content in both `skills/` and
`skills-codex/`, differing only on two axes:

1. the plugin-root env token — `${CLAUDE_PLUGIN_ROOT}` vs `${CODEX_PLUGIN_ROOT}`
2. how the pipeline steps are named — Claude has real slash commands
   (`/toast-creator:test`, …), Codex has none and refers to them as prose
   ("the test step", …)

We can't share a single `skills/` dir (the way mem0 does) because our skills
invoke local scripts by path (`python ${PLUGIN_ROOT}/scripts/...`), so the env
token genuinely differs per harness. So the canonical copy lives here once with
placeholders, and `sync_skills.py` renders both.

## Workflow

```
# 1. edit a shared skill — ONLY ever in toast-creator/skills-src/
# 2. regenerate both harnesses
python toast-creator/skills-src/sync_skills.py

# CI / pre-commit: fail if a generated SKILL.md is stale
python toast-creator/skills-src/sync_skills.py --check
```

Placeholders in source: `${PLUGIN_ROOT}`, `{{test}}`, `{{build}}`, `{{publish}}`.

The generated files (`skills/<name>/SKILL.md`, `skills-codex/<name>/SKILL.md`)
are committed so the plugin installs straight from the repo — but **never edit
them directly**; the next sync overwrites them.

## Not synced

`skills-codex/toast-creator-codex/SKILL.md` is Codex-only (it replaces Claude's
slash commands with an orchestration skill). No Claude twin, so it is
hand-maintained in place — not generated here.
