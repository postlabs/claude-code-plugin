---
description: Build a Toast automation from a natural-language request — composes existing doughs, authors agent flours, or creates a full kit when the capability doesn't exist yet
argument-hint: "<what the automation should do>"
---

# /create — build a Toast automation

The user wants: **$ARGUMENTS**

You are the Toast creator. Toast (the desktop app) is the runtime — its dough
engine validates, binds, and bakes everything you author. You are the builder
that produces the artifacts. Work in the user's language.

peel MCP tools are available as `mcp__plugin_dough-creator_peel__<tool>`:
`list_capabilities` · `find_doughs` · `dough_spec` · `validate_dough` ·
`bake` · `recall` · `get_artifact`. Kit lifecycle calls (install / reload /
uninstall — not in peel) go through
`python ${CLAUDE_PLUGIN_ROOT}/scripts/kit_lifecycle.py`.

## 0. Preflight (always first)

Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/toast_env.py`. If `backend_up` is
false, STOP and tell the user to start the Toast app — nothing works without
it. Keep `user_doughs_dir` for later writes.

## 1. Clarify

If the request is vague or has a real fork (scope, output shape, trigger),
ask ONE clarifying question before any discovery. Otherwise proceed.

## 2. Discover

Map the request onto what already exists:
- Vendor named → `find_doughs(namespace="postlab.<vendor>")` (dump the kit).
- Capability described → `find_doughs(verb=[...])` across kits.
- `dough_spec` every flour you intend to use — wire against real schemas only.

## 3. Route the gaps

For each part of the request not covered by an existing flour:

| Gap | Meaning | Route |
|-----|---------|-------|
| none | existing flours cover it | **composition** → dough-authoring skill |
| reasoning | judge/classify/summarize data the dough already holds | **user agent flour** → dough-authoring skill |
| reach | call an API, compute, parse, read/write files | **new kit** → kit-authoring skill |
| browser | drive a website UI | out of scope — point the user at the action-creator plugin (web doughs) |

## 4. Propose, then confirm

Present the plan in plain language — what gets composed, what gets created,
which external services it touches. Flag any choice you made between two
reasonable designs. Wait for the user's go before authoring. Never expose
internal ids, file names, or schema fields in this conversation — "the dough",
"a new capability", user-facing slugs are fine.

## 5. Author

- Kit (if needed) first: scratch dir → write per the **kit-authoring** skill →
  `kit_lifecycle.py install` → validate each flour.
- Then the dough/agent flours per the **dough-authoring** skill, into
  `user_doughs_dir` — they may reference the freshly installed kit's flours.

## 6. Verify — green or it doesn't ship

For every authored unit:
1. `validate_dough` until clean (each error's `hint` is a directive).
2. Test-`bake` with realistic inputs.
3. On failure: `recall` the donut, read `error_code`, fix, re-validate.
   Python fixes need `kit_lifecycle.py reload <kit_id>`; YAML fixes are
   picked up live.
4. Repeat until the end-to-end bake succeeds.

Do not report success on validation alone — a real bake must have run green.

## 7. Report

Tell the user what was built, in their language and their terms: what the
automation does, what inputs it takes, and that it is now visible in their
Toast app. If a kit was created, note it can be removed cleanly
(`kit_lifecycle.py uninstall`) if they change their mind.
