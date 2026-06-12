---
description: Register a workspace's authored automations into a running Toast and prove them with real bakes — the active verify-and-repair step that gates /publish
argument-hint: "[workspace dir — defaults to scanning the cwd]"
---

# /test — register and bake-verify a workspace (the TEST step)

Target workspace: **$ARGUMENTS** (empty → scan the cwd, see step 1).

You are the **test** step of build → test → deploy. The artifacts already
exist (authored by `/create`, or hand-edited by the user). Your job: get them
onto the real Toast engine and prove they actually run — and when a bake
fails, REPAIR and re-bake until green. This is where engine-grade quality is
won; do not treat it as a pass/fail gate that bounces back to the user. You
fix things here.

You do NOT redesign the automation here. You make the authored design WORK:
fix wiring typos, ref mistakes, tool bugs, shape mismatches — the things a
real bake surfaces that static checks cannot. If a failure means the DESIGN is
wrong (the user wanted different behavior), stop and say so; that is a
`/create` modify, not a test repair.

Tools: peel MCP (`bake`, `recall`, `validate_dough`, `get_artifact`),
`python ${CLAUDE_PLUGIN_ROOT}/scripts/kit_lifecycle.py`,
`python ${CLAUDE_PLUGIN_ROOT}/scripts/dough_publish.py`.

## 0. Preflight — backend REQUIRED

Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/toast_env.py`. If `tier` is
`standalone`, STOP: tell the user to start the Toast app — `/test` runs real
bakes and cannot work offline. (Authoring and static checks already happened
in `/create`; there is nothing to retry offline here.)

Drift note: if the workspace's `provenance.yaml` has `engine_core` stamps that
differ from `vendor/engine_core/VERSION.json`, mention it but do not block —
the live engine re-validates everything; it is authoritative.

## 1. Locate and inventory the workspace

`$ARGUMENTS` → that dir. Else scan the cwd for a workspace root (a dir holding
`provenance.yaml`, or the `./<slug>/{kits,doughs}/` shape); multiple
candidates → ask which. Inventory the kits, the doughs, and current
provenance levels. Tell the user what you found before acting.

## 2. Register (so the engine can bake)

Baking requires the artifacts to be live in Toast, so registration is part of
testing.
- **Kits first** (doughs reference them): `kit_lifecycle.py list` → registered
  with tools → `reload <kit_id>` (picks up edits); not registered →
  `install <kit_dir>` (the script verifies the kit actually bound — follow its
  hint on failure).
- **Doughs**, dependency-first: `dough_publish.py publish <dough_dir>`. A 422
  carries the validator's issues — fix mechanical ones (a typo'd ref, a
  missing return key) in the workspace source and republish, saying what you
  changed. (Static checks in `/create` should have caught these; a 422 here
  means the workspace drifted or skipped `/create`'s build bar.)

**Install/bind failures (one root cause, many faces):**

| Symptom | Meaning |
|---|---|
| install → 400 "Failed to load kit — check kit.yaml" | usually NOT the yaml |
| bake → "Tool not found: '<kit>.<tool>' — no kit registered" | same cause |
| reload → "Kit not found" | same cause |

Root cause (verified): the backend's ACTIVE profile (JWT-derived when logged
in) differs from the profile whose doughs dir is on sys.path — the install
copies the kit where Python can't import it. `kit_lifecycle.py install`
auto-verifies binding and prints this hint; the last-resort workaround is
copying the kit source under EVERY `{profiles}/<key>/doughs/<kit_id>/` and
installing again (`toast_env.py` profile enumeration exists ONLY for this
test-time diagnostic path — never to choose authoring locations, and this is
the one path where writing under a profile is sanctioned, overriding
`/create`'s authoring prohibition). User doughs are unaffected: they go through
the publish API (`dough_publish.py`), which always targets the backend's active
profile.

## 3. Bake-verify the root doughs — with a repair loop

Identify the ROOT doughs (those no other workspace dough calls). For each:

1. `peel bake` with realistic inputs (defaults from `inputs:` when sensible;
   otherwise ask). A root bake exercises the whole tree — kits, sub-doughs,
   agent flours, browser steps.
2. **On failure, repair — do not hand it back:** `recall` the donut, read
   `error_code` FIRST (it names the bug class; never guess from the prose
   message alone), then fix the workspace source and re-register:
   - YAML/wiring fix → edit cwd dough.yaml → `dough_publish.py publish`
   - kit Python fix → edit cwd source → `kit_lifecycle.py reload <kit_id>`
   - then re-bake. Repeat until green.

   For a LARGE donut, don't pull the whole thing through `recall` — read the
   persisted donut JSON from the profile and extract the keys you need.
3. Side-effect courtesy: before baking a root that drives a browser or sends
   anything outward, tell the user.

**Canonical `error_code` reference** (other docs point here):
- `tool_failed` — kit Python raised; fix, reload.
- `output_shape_mismatch` — the `to:` mapping or return shape is wrong.
- `each_not_list` / `all_not_list` — a ref didn't resolve to a list.
- `child_dough_failed` — recurse into the sub-dough.
- `provider_not_connected` — a kit missing connect.py / an unconnected vendor
  (see kit-authoring rule 3.4).

## 4. Stamp provenance VERIFIED

After a green root bake, update `<ws>/provenance.yaml` for every artifact the
bake exercised (the root, its workspace sub-doughs, the kit flours it called):

```yaml
artifacts:
  user.my_automation:
    validated: verified          # was: static
    engine_core: <keep prior stamp if present>
    verified_at: <iso8601>
    donut: <root bake donut id>
```

Never downgrade an entry. Artifacts that failed or weren't exercised keep
their prior level.

## 5. Report + hand off to /publish

In the user's terms: what now runs green on the engine (with the bake as
evidence), and what (if anything) is still unverified and why. The automations
are live in THIS Toast and usable now. State the next step: run
**`/dough-creator:publish`** to deploy (it ships only VERIFIED artifacts). If
a failure turned out to be a design problem, say that the user should re-run
`/create` to change the design.
