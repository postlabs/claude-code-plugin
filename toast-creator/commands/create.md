---
description: Author a Toast automation from a natural-language request — composes existing doughs, authors agent flours, or creates a full kit. Authoring + static/unit checks only; run /test then /publish to verify and deploy.
argument-hint: "<what the automation should do>"
---

# /create — author a Toast automation (the BUILD step)

The user wants: **$ARGUMENTS**

You are the Toast creator. This command is the **build** step of a
build → test → deploy pipeline: you AUTHOR the artifacts and check them
statically. Running them on the real engine (bake) is `/toast-creator:test`;
deploying is `/toast-creator:publish`. `/create` itself needs NO backend and
behaves identically whether Toast is running or not — it never bakes.

Work in the user's language.

peel MCP tools (`mcp__plugin_toast-creator_peel__<tool>` — `find_doughs`,
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

Ask ONE clarifying question ONLY when the request is too vague to even map
onto capabilities — a **what-is-it** ambiguity that blocks discovery itself
(no namable source → trigger → output, no buildable domain, e.g. "make me an
automation"). In that case the single question IS the what-is-it question (what
are we automating, and which source → trigger → output), NOT a
scope/output/trigger sub-fork that presupposes a domain you don't have yet.
Otherwise proceed straight to discovery — scope, output shape, trigger, the
target channel, and possessive phrasing like "my repo" are NOT step-1
questions; they become Build Spec card fields ([assumed]/[input]) in step 4.

One fork worth catching by name — possessive collections ("my saved X", "the
X I keep"): these fork between (a) built-in defaults and (b) a user-owned,
extensible collection. If (b) is plausible, the design needs a data-driven
store (save_X / list_X / run_X primitives), not a hardcoded enum — but carry
that fork into the card as a field, don't stop to ask here. A possessive
collection that lives on an EXTERNAL site ("my shopping-site wishlist") is no
buildable store at all — it's a reach/acquisition field, exempt from the
built-in-vs-store fork entirely.

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

**Discovery output now fills the Build Spec card.** Step 2's mechanics are
unchanged — the capability map, the tier, and the external services it touches
are the same — but its OUTPUT is no longer free prose: it populates the
numbered fields of the step-4 Build Spec card (① acquisition, ② auth, …
⑦ references), so step 4 renders from structured discovery results, not a fresh
guess. In `tier: standalone`, a field discovery could not verify against a live
schema is tagged `[assumed — UNVERIFIED]` — it still ships (no extra
round-trip); step 7 enumerates exactly those.

**Gate A — the acquisition fork, resolved BEFORE the card.** When a reach gap's
acquisition approach (official API vs internal-API capture vs browser session)
has **no dominant winner** AND the choice **rebinds auth / reference / scope**,
resolve it in its OWN `AskUserQuestion` before rendering the card — a rebinding
fork must NEVER be folded into the card's [assumed] fallback batch. A dominant
winner — only one approach actually survives — skips Gate A entirely and renders
into card ① as [assumed]. When `tier: standalone`, the internal-API-capture
choice is dropped (capture is connected-only); if that leaves browser-session as
the sole survivor it IS the dominant winner — render it into card ① as
[assumed — UNVERIFIED], do NOT fire a degenerate one-option Gate A. Two or more
independently-rebinding reach forks (e.g. a scrape approach AND a separate data
source) are resolved in ONE combined `AskUserQuestion`, one question per fork —
still a single round-trip, still never the [assumed] batch. Mind the in-scope
boundary: "browser session" means reading a single KNOWN surface (the
page-scripting row); if acquisition needs multi-step navigation / login /
clicking, that is **browser UI driving — out of scope** → hand off to
action-creator, never quietly build it as an acquisition leg.

**Auth-category landmine.** `auth.category: local` is the no-auth / pure-compute
pattern ONLY (connect.py no-op, always authenticated — kit-authoring rule 3.4).
A third-party credential — a GitHub PAT, a Slack token — is NOT
`category: local`; never tag a card ② Auth that collects a third-party token as
local.

## 3. Route the gaps

For each part of the request not covered by an existing flour:

| Gap | Meaning | Route |
|-----|---------|-------|
| none | existing flours cover it | **composition** → dough-authoring skill |
| reasoning | judge/classify/summarize data the dough already holds (e.g. pick the best of 3 results the dough already fetched) | **user agent flour** → dough-authoring skill |
| reach | call an API, compute, parse, read/write files (e.g. fetch the 3 results in the first place) | **new kit** → kit-authoring skill |
| page scripting | inject JS into a page / read a page once (chart drawing, scraping a known surface) | **in scope** — a codegen kit tool + `webengine.browser.open_tab` → `webengine.browser.act(kind=eval_js)` composition. This webengine wiring is what SHIPS and runs inside Toast — see the web-engine rule below. |
| internal data API capture | reuse a site's OWN internal/page data API for repeated reads (no official API, no httpx kit) — esp. when the user rejects the official API or asks to "capture the page's API" | **in scope (connected only)** — the **web-api-capture** skill: `start_api_capture` → `browse` → `promote_api`, then drive the capture→bake→repair loop AUTONOMOUSLY |
| browser UI driving | multi-step clicking/typing through a site's UI | out of scope — point the user at the action-creator plugin (web doughs) |

**Connected apicapture is the one carve-out from "never bakes."** It is inherently live
(capture + bake-verify), so when you route there you DO go live — and you own the
repair loop: a failed bake is a repair signal, not a question for the user. Diagnose the
actual error, test the cheap hypothesis first (e.g. a 403 on an internal-API re-fetch is
almost always missing `Authorization`/CSRF headers, not a hard block), and retry within a
budget before surfacing. See the **web-api-capture** skill for the auth-walled-SPA
playbook. The rest of `/create` still never bakes.

**Web-engine rule — two axes, do not conflate them.** A web task touches the
browser at two distinct moments:

- **What the dough USES at runtime → ALWAYS `webengine.browser.*` (Toast's
  browser), regardless of tier.** The dough is executed by Toast, so it must
  wire Toast's web engine. Playwright is an MCP tool *you* drive interactively;
  it is NOT part of the Toast runtime, so a dough wired to Playwright is dead on
  arrival at bake. NEVER reference a `mcp__…playwright…` tool from a dough/kit.
  This holds even in standalone — the dough runs later under `/test`/`/publish`,
  when Toast IS up; "Toast is down right now" never changes the runtime target.
- **What YOU test WITH during build → tier-gated (see step 6.4).** Connected,
  drive Toast's own browser (peel `browse`) so the smoke test matches the
  runtime engine; standalone, fall back to Playwright. Either way the real proof
  is `/test`'s bake, not the build-time check.

The reasoning/reach boundary is the most consequential call: reasoning works
OVER data the dough already holds; reach goes OUT to get it or compute it.

When one request decomposes into reach + compute + rendering, that is SEVERAL
kits, not one — see the kit-authoring skill's "Cut kits by capability axis"
rule before writing any kit.yaml. A compute leg that depends on an EXTERNAL
value (an FX rate, a live price) hides its own reach: fetching that value is a
separate acquisition with its own kit and its own card ① line — never fold it
into the compute step as if it were reasoning over data the dough already
holds.

A reach gap rarely has one obvious source — "fetch KOSPI data" could be an
official API, a free library, or a scrape. Don't silently pick blind, and don't
bare-ask "which source?" (the user usually can't choose unaided): scout the
realistic options (WebSearch / WebFetch their current docs), weighing what they
actually trade — free vs keyed, official vs scraped (reliability/ToS), realtime
vs delayed. **Terminus:** if the scout yields a **dominant winner** that does
NOT rebind auth/reference/scope, render it straight into card field ① as
[assumed] — no question, no phantom alternatives. If there is **no dominant
winner AND the fork rebinds auth/reference/scope**, fire **Gate A** (the single
dedicated acquisition question from step 2) before the card; any remaining minor
choices ride into the card as [assumed]/[input]. Author against the docs you
just fetched, not a half-remembered API — the step-6 unit-run is what proves
the endpoint real.

## 4. Propose the card, then react

Don't ask a batch of questions and don't narrate a prose plan. Render ONE
filled-in **Build Spec card** — every decision already made, each line TAGGED
so the user reads it in seconds and reacts by editing only the wrong lines. The
card IS the confirmation: a bare "go" ships it as shown. (Worked example — the
GitHub-issue → Slack happy path; tags are computed per field, not fixed.)

```
Build Spec — GitHub issue → Slack summary
① Acquisition  GitHub REST API (official, dominant winner)   [assumed]
② Auth         GitHub PAT — third-party token, NOT local     [assumed]
③ Trigger      issue assigned to me → run                    [assumed]
④ Summary      3-line summary, per issue                     [assumed]
⑤ Destination  Slack #<channel>                              [input]
⑥ Scope        repo <owner/name>                             [assumed]
⑦ References   none needed (official API)                    [assumed]
```

**The tags ARE the cost-of-guessing triad, made structural:**
- a harmless default they might still want changed → **[assumed]** (the old
  "pick it and SAY so" — e.g. "3-line summary, in-browser fetch");
- a knob they'd plausibly retune run-to-run → **[input]** (a dough input
  carrying that default, changed per-run not per-rebuild);
- a rebuild-forcing unknown with NO safe default → **[need you]**, applied
  STRICTLY: only when the field genuinely blocks authoring (a page URL/HAR the
  build cannot proceed without). An explicitly-requested side-effect is NOT a
  [need you] — "send to Slack" makes the channel an ⑤ [input] target, not a
  question.

**Editing a parent field REGENERATES the card — recompute, not patch.** When
the user edits a field others depend on, rebuild the whole card from inputs so
stale lines are structurally impossible; a line that no longer applies is
REMOVED, never crossed out. Acquisition is the parent that rebinds the most:
e.g. on the GitHub-read side, "① browser" recomputes that side to ② Auth =
Toast-browser-session (the PAT line DISAPPEARS, not struck through) and ⑦
References to the page to read. If that surface is inferable (a known URL,
logged in via the Toast session), keep it [assumed — UNVERIFIED]; reserve
[need you] BLOCKING for a page/HAR that genuinely cannot be inferred without the
user pasting it. Only the edited side recomputes — the untouched Slack side
stays put. A no-dominant-winner rebinding acquisition fork is resolved at Gate A
(step 2) BEFORE the card, never inside this fallback batch.

**One line per leg when the build is SEVERAL kits.** When step 3's SEVERAL-kits
rule fires (multiple distinct new acquisitions — e.g. a scrape source + an
FX-rate source + a Notion write), ① Acquisition and ② Auth are NOT single rows:
every distinct new acquisition gets its own ① line and every distinct new
third-party credential its own ② line (①a/①b…, ②a/②b…, or one card per kit),
each tagged. A guessed secondary source that never gets a line is a hidden
decision "go" cannot veto — exactly what the card exists to prevent. An existing
connected-vendor flour whose auth Toast already manages (e.g. postlab.slack)
needs NO ② line; say so, so a missing auth line reads as "pre-managed", not
"forgotten".

A card with zero [need you] lines and a "go" ships in exactly one round-trip.
While building, don't narrate internal ids, file names, or schema fields.

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
4. **eval_js dry-run** — a build-time smoke test of the generated JS, NOT proof
   (the real proof is `/test`'s bake in Toast). Pick the engine by tier:
   - **Connected:** drive Toast's OWN browser via peel `browse` — same engine,
     cookies, and login the dough will use at runtime, so the check is
     meaningful.
   - **Standalone:** fall back to Playwright browser tools (the only
     backend-free option) — open the target page and run the JS there. Treat a
     pass cautiously: Playwright's generic Chromium differs from Toast's browser
     (auth/headers/context), so it only confirms the JS parses and runs, not
     that it works in Toast.
   Either way, this is the ONLY place Playwright is allowed, and only as a
   throwaway check — never wire it into the dough (see the web-engine rule).

`offline_validate.py` records each passing artifact in
`./<slug>/provenance.yaml` as `validated: static` with the validator's version
stamp. This is the build-step level — NOT engine-verified yet.

## 7. Report + hand off to /test

Tell the user, in their terms: what the automation does, what inputs it takes,
and WHERE the sources live (`./<slug>/` — their owned, editable copy). Surface
the card's [assumed] (and standalone [assumed — UNVERIFIED]) fields so the user
can still veto a guess — and when the build is several kits, do this for EVERY
leg: each acquisition and each third-party auth, not only the fields that fit a
single row. Name the auth (e.g. "GitHub PAT — a third-party token, NOT
auth.category:local") and the chosen scope (e.g. the repo). `category: local`
is the no-auth / pure-compute pattern only; never report a third-party-token
field as local.

**Standalone unverified-fields rule.** In standalone tier a card field the
peeled-down build could not verify against a live schema is tagged
**[assumed — UNVERIFIED]** during discovery (no extra round-trip — it ships,
flagged). Step 7 enumerates exactly those tagged fields as the
unverified-warning list, alongside the external-capability warnings from
discovery. Round-trips do not increase versus the connected path.

Then state the next step plainly: the artifacts are authored and
statically/unit-checked but have not run on the real engine yet — run
**`/toast-creator:test`** (Toast must be running) to register them and
bake-verify, then **`/toast-creator:publish`** to deploy. Name the
automation's slug.
