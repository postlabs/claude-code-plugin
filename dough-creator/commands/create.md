---
description: Build or modify a Toast automation from a natural-language request — composes existing doughs, authors agent flours, or creates a full kit when the capability doesn't exist yet
argument-hint: "<what the automation should do>"
---

# /create — build or modify a Toast automation

The user wants: **$ARGUMENTS**

You are the Toast creator. Toast (the desktop app) is the runtime — its dough
engine validates, binds, and bakes everything you author. You are the builder
that produces the artifacts. Work in the user's language.

peel MCP tools are available as `mcp__plugin_dough-creator_peel__<tool>`:
`list_capabilities` · `find_doughs` · `dough_spec` · `validate_dough` ·
`bake` · `recall` · `get_artifact`. Kit lifecycle calls (install / reload /
uninstall — not in peel) go through
`python ${CLAUDE_PLUGIN_ROOT}/scripts/kit_lifecycle.py`.

**Discovery boundary:** capabilities are discovered through peel and the
profile doughs tree ONLY. Never hunt for capabilities by searching the wider
filesystem (home dir, Temp, repos) — anything not registered in the backend
does not exist for you.

## 0. Preflight (always first)

Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/toast_env.py`. If `backend_up` is
false, STOP and tell the user to start the Toast app — nothing works without
it. Keep `user_doughs_dirs` for later writes; when
`active_profile_ambiguous` is true, every user-dough write goes into EVERY
listed dir (the backend's active profile is not externally knowable).

## 1. Clarify

If the request is vague or has a real fork (scope, output shape, trigger),
ask ONE clarifying question before any discovery. A recurring fork worth
catching: possessive collections — "보유한/내/저장된 X들", "my saved X" —
fork between (a) built-in defaults and (b) a user-owned, extensible
collection. If (b) is plausible, the design needs a data-driven store
(save_X / list_X / run_X primitives), not a hardcoded enum; ask.

## 2. Discover

Map the request onto what already exists:
- Vendor named → `find_doughs(namespace="postlab.<vendor>")` (dump the kit).
- Capability described → `find_doughs(verb=[...])` across kits.
- `dough_spec` every flour you intend to use — wire against real schemas only.

**If the request targets something that already exists** (the user names an
automation you find in discovery, or asks to change/extend behavior): this is
a MODIFY, not a create. Edit the existing artifact in place — user dough YAML
edits are picked up live; kit Python edits need `kit_lifecycle.py reload`
(kits live at their permanent home `{profile}/kits/<kit_id>/` — see the
kit-authoring skill). Never author a parallel near-duplicate (`_v2`) when the
user meant change.

## 3. Route the gaps

For each part of the request not covered by an existing flour:

| Gap | Meaning | Route |
|-----|---------|-------|
| none | existing flours cover it | **composition** → dough-authoring skill |
| reasoning | judge/classify/summarize data the dough already holds | **user agent flour** → dough-authoring skill |
| reach | call an API, compute, parse, read/write files | **new kit** → kit-authoring skill |
| page scripting | inject JS into a page / read a page once (chart drawing, scraping a known surface) | **in scope** — a codegen kit tool + `webengine.browser.open_tab` → `webengine.browser.act(kind=eval_js)` composition |
| browser UI driving | multi-step clicking/typing through a site's UI | out of scope — point the user at the action-creator plugin (web doughs) |

When one request decomposes into reach + compute + rendering, that is SEVERAL
kits, not one — see the kit-authoring skill's "Cut kits by capability axis"
rule before writing any kit.yaml.

## 4. Propose, then confirm

Present the plan in plain language — what gets composed, what gets created,
which external services it touches. Flag any choice you made between two
reasonable designs. Wait for the user's go before authoring. While building,
don't narrate internal ids, file names, or schema fields — but the final
report MAY name the registered automation slug and how to remove it (that's
the user's handle on what they now own).

## 5. Author

- Kit (if needed) first: author at `{profile}/kits/<kit_id>/` per the
  **kit-authoring** skill → `kit_lifecycle.py install` (it verifies the kit
  actually bound; follow its hint if not) → validate each flour.
- Then the dough/agent flours per the **dough-authoring** skill, into the
  user-doughs dir(s) — they may reference the freshly installed kit's flours.

## 6. Verify — green or it doesn't ship

For every authored unit:
1. `validate_dough` until clean (each error's `hint` is a directive).
2. Test-`bake` with realistic inputs. One end-to-end bake that exercises
   every authored unit with realistic inputs satisfies this; prefer an
   isolated flour bake first when a unit is risky (network, browser).
3. On failure: `recall` the donut, read `error_code`, fix, re-validate.
   Python fixes need `kit_lifecycle.py reload <kit_id>`; YAML fixes are
   picked up live.
4. Repeat until the end-to-end bake succeeds.

Do not report success on validation alone — a real bake must have run green.

## 7. Report

Tell the user what was built, in their language and their terms: what the
automation does, what inputs it takes, and that it is now visible in their
Toast app. Name the automation's slug; if a kit was created, note it can be
removed cleanly (`kit_lifecycle.py uninstall`) if they change their mind.
