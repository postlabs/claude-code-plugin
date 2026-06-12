---
description: Deploy a workspace's VERIFIED automations — the deploy step that ships only what /test proved green and hands the user their management handles
argument-hint: "[workspace dir — defaults to scanning the cwd]"
---

# /publish — deploy a tested workspace (the DEPLOY step)

Target workspace: **$ARGUMENTS** (empty → scan the cwd, see step 1).

You are the **deploy** step of build → test → deploy. By the time you run,
`/test` has registered the artifacts into Toast and proved the root doughs
bake green. Deploy ships only what was verified, finalizes the record, and
hands the user the controls. You author nothing and design nothing.

**The gate:** `/publish` deploys ONLY artifacts whose `provenance.yaml` level
is `verified`. An artifact that is merely `static` (authored + statically
checked, never bake-proven) is NOT deployable — send the user to
`/dough-creator:test` first. This is the test-gates-deploy discipline; do not
bypass it by baking here yourself (that is `/test`'s job).

Tools: `python ${CLAUDE_PLUGIN_ROOT}/scripts/kit_lifecycle.py`,
`python ${CLAUDE_PLUGIN_ROOT}/scripts/dough_publish.py`, peel for read-backs.

## 0. Preflight — backend REQUIRED

Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/toast_env.py`. If `tier` is
`standalone`, STOP: deployment targets a running Toast.

## 1. Locate the workspace + read provenance

`$ARGUMENTS` → that dir; else scan the cwd for the workspace root. Read
`provenance.yaml`. Partition the artifacts:
- `verified` → deployable.
- `static` or missing → NOT deployable; list them and tell the user to
  `/dough-creator:test` first. If NOTHING is verified, stop after this report.

## 2. Confirm the deployment is live and complete

`/test` already registered everything to bake it, so for a local Toast deploy
this step is a confirmation, not a re-install:
- `kit_lifecycle.py list` — every kit the verified doughs depend on is
  registered with its tools. Missing one (e.g. the user ran `/test` in a
  different profile/session) → `install <kit_dir>` and re-confirm.
- For each verified dough, a read-back (`peel dough_spec` / `find_doughs`)
  confirms it is live. Missing → `dough_publish.py publish <dough_dir>` (it is
  already verified; this is just (re)registration, no design change).

## 3. Report + hand over the controls

Tell the user, in their terms:
- which automations are now deployed and usable in their Toast app, what each
  does, and what inputs each takes;
- WHERE the editable source lives (`./<slug>/`) — edit there, then
  `/create` (design change) or `/test` (re-verify) → `/publish` again;
- the management handles: `dough_publish.py delete <dough_id>` to remove a
  dough, `kit_lifecycle.py uninstall <kit_id>` to remove a created kit;
- anything left undeployed (still `static`) and that `/test` finishes it.

## Note — distribution beyond this machine

Today "deploy" means the automations are live in the user's OWN Toast. Sharing
them with other users (a public catalog) is a future destination for this same
command; when it lands, `/publish` gains a target and the verified-only gate
above is exactly the quality bar a catalog needs.
