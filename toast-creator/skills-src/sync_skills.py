#!/usr/bin/env python3
"""Single-source sync for the toast-creator shared skills.

This plugin ships ONE copy of scripts/vendor/tests and serves two harnesses
from one folder:

  .claude-plugin/plugin.json -> skills auto-discovered from ./skills/
  .codex-plugin/plugin.json  -> "skills": "./skills-codex/"

The three authoring skills below are byte-for-byte twins across those two
skill dirs, differing only on two axes:

  1. the plugin-root env token  (${CLAUDE_PLUGIN_ROOT} vs ${CODEX_PLUGIN_ROOT})
  2. how they name the pipeline steps — Claude has real slash commands,
     Codex has none and refers to them as prose.

(We can't share a single skills/ dir the way mem0 does, because our skills
invoke local scripts by path — `python ${PLUGIN_ROOT}/scripts/...` — so the
env token genuinely differs per harness. mem0's skills are pure MCP, no path.)

So the canonical copy lives HERE once, with placeholders, and this script
renders the per-harness output into ./skills/ (Claude) and ./skills-codex/
(Codex).

    edit  toast-creator/skills-src/<name>/SKILL.md     (the ONLY place to edit)
    run   python toast-creator/skills-src/sync_skills.py        (regenerate both)
    or    python toast-creator/skills-src/sync_skills.py --check (CI: fail on drift)

NOTE: skills-codex/toast-creator-codex/SKILL.md is Codex-only (it replaces
Claude's slash commands with an orchestration skill). It has no Claude twin,
so it is NOT synced here — edit it in place.
"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent          # toast-creator/skills-src
PLUGIN = SRC.parent                            # toast-creator

# Skills that are true twins across both skill dirs.
SHARED_SKILLS = ["dough-authoring", "kit-authoring", "web-api-capture"]

# Per-harness rendering of the placeholders.
HARNESSES = {
    "claude": {
        "out": PLUGIN / "skills",
        "${PLUGIN_ROOT}": "${CLAUDE_PLUGIN_ROOT}",
        "{{test}}": "`/toast-creator:test`",
        "{{build}}": "`/toast-creator:create`",
        "{{publish}}": "`/toast-creator:publish`",
    },
    "codex": {
        "out": PLUGIN / "skills-codex",
        "${PLUGIN_ROOT}": "${CODEX_PLUGIN_ROOT}",
        "{{test}}": "the test step",
        "{{build}}": "the build step",
        "{{publish}}": "the publish step",
    },
}


def render(text: str, cfg: dict) -> str:
    for token, value in cfg.items():
        if token == "out":
            continue
        text = text.replace(token, value)
    return text


def iter_targets():
    for skill in SHARED_SKILLS:
        src = SRC / skill / "SKILL.md"
        if not src.exists():
            raise SystemExit(f"missing source: {src}")
        source_text = src.read_text(encoding="utf-8")
        for harness, cfg in HARNESSES.items():
            dest = cfg["out"] / skill / "SKILL.md"
            yield harness, skill, dest, render(source_text, cfg)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    drift = []
    wrote = 0
    for harness, skill, dest, rendered in iter_targets():
        current = dest.read_text(encoding="utf-8") if dest.exists() else None
        if current == rendered:
            continue
        if check:
            drift.append(f"  {harness}/{skill}: {dest}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered, encoding="utf-8")
        wrote += 1
        print(f"wrote {harness}/{skill} -> {dest.relative_to(PLUGIN.parent)}")

    if check:
        if drift:
            print("SKILL drift (run sync_skills.py):", file=sys.stderr)
            print("\n".join(drift), file=sys.stderr)
            return 1
        print("skills in sync")
        return 0

    total = len(SHARED_SKILLS) * len(HARNESSES)
    print(f"done - {wrote} file(s) updated, {total} skill targets in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
