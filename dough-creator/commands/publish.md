---
description: Register a workspace's authored automations into a running Toast — install kits, publish doughs, run verification bakes, and upgrade provenance to VERIFIED
argument-hint: "[workspace dir — defaults to scanning the cwd]"
---

# /publish — register workspace artifacts into Toast

Target workspace: **$ARGUMENTS** (when empty: scan the cwd, see step 1).

You are taking automations that already EXIST as workspace sources — authored
by a previous `/create` run (possibly in standalone tier, possibly on another
machine) or hand-edited by the user — and registering them into the running
Toast backend, then proving them with real bakes. This is the bridge from
"authored + statically verified" to "engine-VERIFIED". You do NOT redesign or
re-author here; the workspace is the source of truth. Work in the user's
language.

Tools: peel MCP (`mcp__plugin_dough-creator_peel__<tool>`), plus
`python ${CLAUDE_PLUGIN_ROOT}/scripts/kit_lifecycle.py` and
`python ${CLAUDE_PLUGIN_ROOT}/scripts/dough_publish.py`.

## 0. Preflight — this command REQUIRES the backend

Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/toast_env.py`. If `tier` is
`standalone`, STOP: tell the user to start the Toast app and re-run — unlike
`/create`, publishing has no offline mode (that is the point of this command).

Drift note: if the workspace's `provenance.yaml` carries `engine_core` stamps
that differ from `${CLAUDE_PLUGIN_ROOT}/vendor/engine_core/VERSION.json`'s
`mojo_rev`, mention it but do not block — the server re-validates everything
at publish time, and the server is authoritative.

## 1. Locate and inventory the workspace

- `$ARGUMENTS` given → that directory.
- Otherwise scan the cwd for workspace roots: a dir containing
  `provenance.yaml`, or matching the `./<slug>/{kits,doughs}/` shape. Multiple
  candidates → ask the user which one.

Inventory: every kit dir under `<ws>/kits/`, every dough dir under
`<ws>/doughs/` (dough.yaml + box.yaml), and the current `provenance.yaml`
levels. Tell the user what you found before acting.

## 2. Kits first (doughs reference them)

For each kit: check `kit_lifecycle.py list` — already registered with tools →
`reload <kit_id>` (picks up source edits); not registered → `install <kit_dir>`
(the script verifies the kit actually bound; follow its hint on failure).

## 3. Publish doughs

`dough_publish.py publish <dough_dir>` for each (no `--draft`). Publish order:
dependency-first when workspace doughs reference each other. A 422 carries the
validator's issues:
- mechanical fixes (a typo'd ref, a missing return key) → fix the workspace
  source, republish, and say what you changed;
- anything semantic (wiring, step changes) → show the issues and ask before
  touching the design.

## 4. Verification bakes — green or it isn't VERIFIED

Identify the workspace's ROOT doughs (those no other workspace dough calls).
For each root: `peel bake` with realistic inputs — defaults from `inputs:`
when sensible, otherwise ask the user. A root bake exercises the whole tree
(kits, sub-doughs, agent flours). On failure: `recall` the donut, read
`error_code`, fix (workspace source + republish / kit reload), re-bake.

Side-effect courtesy: if a root dough drives a browser or sends anything
outward, tell the user before baking it.

## 5. Upgrade provenance

After a green root bake, update `<ws>/provenance.yaml` for every artifact the
bake exercised (the root, its workspace sub-doughs, the kits' flours it
called):

```yaml
artifacts:
  user.my_automation:
    validated: verified          # was: static
    engine_core: <keep prior stamp if present>
    verified_at: <iso8601>
    donut: <root bake donut id>
```

Never downgrade an entry; artifacts that failed or weren't exercised keep
their previous level.

## 6. Report

In the user's terms: what got registered (kits, automations), what is now
engine-VERIFIED (with the bake as evidence), what remains unverified and why.
Name the slugs and the removal handles (`dough_publish.py delete`,
`kit_lifecycle.py uninstall`). Remind them the workspace stays the editable
source — edit → `/publish` again.
