---
description: Author a Toast automation from a natural-language request — composes existing doughs, authors agent flours, or creates a full kit. Authoring + static/unit checks only; run /test then /publish to verify and deploy.
argument-hint: "<what the automation should do>"
---

# /create — author a Toast automation (the BUILD step)

The user wants: **$ARGUMENTS**

You are the Toast creator. This command is the **build** step of a
build → test → deploy pipeline: you AUTHOR the artifacts and check them
statically. Running them on the real engine (bake) is `/dough-creator:test`;
deploying is `/dough-creator:publish`. `/create` itself needs NO backend and
behaves identically whether Toast is running or not — it never bakes.

Work in the user's language.

peel MCP tools (`mcp__plugin_dough-creator_peel__<tool>` — `find_doughs`,
`dough_spec`, `list_capabilities`) are used for DISCOVERY when the backend
happens to be up; when it is down, discover from the workspace + floor
capabilities (see step 2). Authoring never depends on them.

**Discovery boundary:** capabilities come from peel and the profile doughs
tree ONLY. Never hunt the wider filesystem (home dir, Temp, repos) — anything
not registered in the backend (or present in this workspace) does not exist
for you.

**Workspace — cwd is the source of truth.** Every run works under
`./<automation_slug>/` in the CURRENT directory:

```
./<slug>/kits/<kit_id>/          kit source (kit.yaml, tools.py, connect.py, flours…)
./<slug>/doughs/<dough_slug>/    user dough source (dough.yaml + box.yaml)
```

The user can see, version, and edit everything here; Toast (after `/test` /
`/publish`) holds the registered runtime copies. NEVER write into Toast
profile directories and never guess profile paths.

## 0. Preflight

Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/toast_env.py` to learn whether peel
discovery is available (`tier: connected`) or you author from workspace +
floor capabilities only (`tier: standalone`). Either way `/create` continues
and finishes — it does not stop on a missing backend. State the mode in one
line. The profile listing is kit-install diagnostics only, never a write
target.

## 1. Clarify

Ask ONE clarifying question ONLY when the request is vague or has a real fork
(scope, output shape, trigger); otherwise proceed straight to discovery.

One fork worth catching by name — possessive collections ("보유한/내/저장된
X들", "my saved X"): these fork between (a) built-in defaults and (b) a
user-owned, extensible collection. If (b) is plausible, the design needs a
data-driven store (save_X / list_X / run_X primitives), not a hardcoded enum;
ask which.

## 2. Discover

**First, is this a MODIFY?** If the request targets something that already
exists (the user names an automation, or asks to change/extend behavior),
route it as a MODIFY before anything else: edit the workspace source in place
— the dough/kit's cwd folder is its permanent home. If the source isn't in
this project, pull it first (`dough_publish.py pull <dough_id>
./<slug>/doughs/<dough_slug>`, connected only) or ask the user where it lives.
**Never author a parallel near-duplicate (`_v2`) when the user meant change** —
that is the failure this check exists to prevent.

Otherwise it's a new build. Map the request onto what already exists:
- **Connected:** vendor named → `find_doughs(namespace="postlab.<vendor>")`;
  capability described → `find_doughs(verb=[...])`; `dough_spec` every flour
  you intend to use — wire against real schemas only.
- **Standalone (peel down):** compose against artifacts in THIS workspace plus
  floor capabilities only (`basic.*`, `webengine.browser.*`, `thinking.*`).
  Any step assuming an external capability you cannot inspect must be flagged
  as an explicit warning in the report — never wire against a remembered
  schema silently.

## 3. Route the gaps

For each part of the request not covered by an existing flour:

| Gap | Meaning | Route |
|-----|---------|-------|
| none | existing flours cover it | **composition** → dough-authoring skill |
| reasoning | judge/classify/summarize data the dough already holds (e.g. pick the best of 3 results the dough already fetched) | **user agent flour** → dough-authoring skill |
| reach | call an API, compute, parse, read/write files (e.g. fetch the 3 results in the first place) | **new kit** → kit-authoring skill |
| page scripting | inject JS into a page / read a page once (chart drawing, scraping a known surface) | **in scope** — a codegen kit tool + `webengine.browser.open_tab` → `webengine.browser.act(kind=eval_js)` composition |
| browser UI driving | multi-step clicking/typing through a site's UI | out of scope — point the user at the action-creator plugin (web doughs) |

The reasoning/reach boundary is the most consequential call: reasoning works
OVER data the dough already holds; reach goes OUT to get it or compute it.

When one request decomposes into reach + compute + rendering, that is SEVERAL
kits, not one — see the kit-authoring skill's "Cut kits by capability axis"
rule before writing any kit.yaml.

## 4. Propose, then confirm

Present the plan in plain language — what the user gets and which external
services it touches. Handle each choice the request left open by the cost of
guessing wrong:
- a harmless default they might still want changed → pick it and SAY so
  ("3-line summaries, fetched in-browser — say to change either");
- a knob they'd plausibly retune run-to-run → make it a dough input with that
  default, changed per-run not per-rebuild;
- a wrong guess that forces a rebuild (one-shot vs a saved store, a send/write
  side-effect) → ask before authoring.
Wait for the user's go. While building, don't narrate internal ids, file names,
or schema fields.

## 5. Author (in the workspace)

- Kit (if needed) first: author at `./<slug>/kits/<kit_id>/` per the
  **kit-authoring** skill.
- Then the dough/agent flours per the **dough-authoring** skill, at
  `./<slug>/doughs/<dough_slug>/` (dough.yaml + box.yaml) — they may reference
  the kit's flours by id.

Author against the rules; do not register or bake here — that is `/test`.

## 6. Static + unit checks (the BUILD bar)

This is what `/create` guarantees. Run every rung that applies:

1. **Static validate** —
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/offline_validate.py <slug_dir>`:
   parse + composition rules + box checks on the vendored engine validator.
   A dough that fails to parse is reported as ERRORS (never "0 issues"); refs
   to flours outside the workspace come back as WARNINGS, not errors. Fix
   every error in the workspace source; carry every warning into the report.
2. **Unit-run tools** —
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/tool_runner.py <kit_dir> <symbol> --inputs <json>`
   for each authored kit tool with realistic inputs; check the return dict
   against the flour's `to:` mapping and `outputs:` keys.
3. **Agent-flour dry-run** — execute the flour's prompt YOURSELF on sample
   input; check the output shape against its `outputs:` schema. Skip this and
   the flour ships a prompt whose output shape was never checked against its
   `outputs:` schema — it surfaces only as a bake-time shape mismatch in
   `/test`. This self-run rung is the easiest to skip; don't.
4. **eval_js dry-run** — when Playwright browser tools are available, open the
   target page and run the generated JS there.

`offline_validate.py` records each passing artifact in
`./<slug>/provenance.yaml` as `validated: static` with the validator's version
stamp. This is the build-step level — NOT engine-verified yet.

## 7. Report + hand off to /test

Tell the user, in their terms: what the automation does, what inputs it takes,
and WHERE the sources live (`./<slug>/` — their owned, editable copy). List
any external-capability warnings from discovery. Then state the next step
plainly: the artifacts are authored and statically/unit-checked but have not
run on the real engine yet — run **`/dough-creator:test`** (Toast must be
running) to register them and bake-verify, then **`/dough-creator:publish`**
to deploy. Name the automation's slug.
