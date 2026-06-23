---
name: web-api-capture
description: How to build a reusable web dough by capturing a site's OWN internal/page data API from the user's logged-in browser and re-calling it in-page — no official API, no httpx kit. Use when the request is "get data from site X for reuse" AND the user rejects the official API / a network kit, OR explicitly asks to capture the page's internal API. Connected tier only (needs the live browser). Drive the capture→verify→repair loop AUTONOMOUSLY; do not hand failures back turn-by-turn.
---

# Web API capture — reusable doughs from a site's own internal API

A site's logged-in pages call internal JSON/GraphQL endpoints. We capture one, then
emit a `user.webapi_*` dough that re-calls it **in-page** (the page's origin cookies
ride along; no token is stored). This is faster and more durable than DOM scraping,
and needs no official API key.

## The cardinal rule — be the repair loop, not the user

This task is inherently LIVE (it bakes). A real user will NOT patiently re-prompt
after each failure — if you stop and ask "how should I proceed?" on every 403 / empty
result, the build dies. **You** run the loop:

> bake → read the donut (`recall` / `get_artifact`) → diagnose the ACTUAL error →
> form a hypothesis → probe it → repair → re-bake. Repeat within a budget
> (~6–8 probes) before surfacing anything.

Surface to the user ONLY for: a genuine product fork (an irreversible write/send),
real scope ambiguity, or true block after the budget. NOT for a recoverable error you
can diagnose. (This mirrors {{test}}'s "On failure, repair — do not hand it back.")
A failed bake is a REPAIR SIGNAL, never a dead end — and never your first "it can't be
done." Test the cheap hypothesis before declaring a wall.

## The flow (peel tools)

1. `start_api_capture` → `capture_id` (arms a passive, read-only network capture).
2. `browse` the target page(s) — the capture records the page's XHR/Fetch JSON. The
   page may render slowly or stall on "Loading"; **the network calls fire anyway**, so
   the capture still gets the data even if the a11y snapshot shows only a spinner.
3. `promote_api(capture_id, answer, query_param?, shape_js?, name?)` → matches the
   `answer` tokens against captured bodies to pick the data API deterministically, and
   emits a `user.webapi_*` dough that re-fetches it in-page.
   - **Self-source the `answer`.** Read a distinctive token yourself — a number, an id,
     a phrase — from the page snapshot or (if rendering stalls) a value you can derive.
     NEVER ask the user for it. If the visible page won't yield one, bake a tiny probe
     that reads the page and returns a token.
   - `query_param` makes it reusable for any query — but only works when the user's
     input sits in a top-level URL query parameter (see playbook §3 for the common
     case where it does NOT).
   - `shape_js` returns just the requested fields; absent, you get the raw body.
4. **Bake the emitted dough and verify it returns real data** (this is the repair loop's
   first iteration — `ok:true` from promote_api only means the CAPTURE had the data, NOT
   that the re-fetch works).

## Auth-walled SPA playbook (the failure modes, in order of likelihood)

Modern logged-in SPAs (x/twitter, instagram, linkedin, …) wall their internal API.
When the emitted dough's re-fetch fails, walk these — cheapest first:

1. **403 / 401 → missing auth HEADERS (the #1 cause).** `promote_api`'s default fetch
   sends cookies only. The site's GraphQL/JSON API also needs headers the page's own JS
   adds: an `Authorization: Bearer <token>` (usually a PUBLIC, static token baked into
   the site's JS — not a secret, the same for all web users) plus a CSRF header read
   live from a cookie. Hand-author the eval_js to add them:
   - read CSRF from `document.cookie` each run (e.g. x.com: `x-csrf-token` = the `ct0`
     cookie) → self-fresh, never stale.
   - include the site's `x-*-active-user` / `auth-type` headers if it uses them.
   Do NOT assume the hardest cause (an anti-bot per-request transaction id) first —
   most 403s are just the missing Bearer + CSRF. Test that before giving up.
2. **Session auth is self-fresh — don't store tokens.** Because the fetch runs in the
   logged-in page (`credentials:"include"` + CSRF read live), auth never goes stale as
   long as the user stays logged in. You hold nothing. "Auth is hard" is usually a
   header-omission bug, not a session problem.
3. **Args buried in a JSON `variables` URL param.** GraphQL sites encode arguments as a
   url-encoded JSON `variables=` param, so `promote_api`'s single-field `query_param`
   can't inject just the user's input. Hand-author an eval_js that builds the request:
   `encodeURIComponent(JSON.stringify({...variables, <field>: input}))`.
4. **Two-step entity resolution.** Data endpoints take an internal numeric id, not the
   human handle/slug. Resolve first, then fetch: e.g. x.com `UserByScreenName(screen_name)`
   → `rest_id`, then `UserTweets(userId)`. Chain both fetches in one eval_js.
5. **Rotating GraphQL query ids.** The `/graphql/<queryId>/<Op>` id changes per frontend
   build (weeks–months). Two options: (a) HARDCODE the id + the `features`/`fieldToggles`
   blobs (capture gives you the exact current ones) and repair on a `... http 404` —
   cheap, low-maintenance, RECOMMENDED; (b) read the current id live at runtime (heavier,
   depends on the site's bundle being parseable; `performance` entries are often cleared,
   and timeline-mount/scroll triggers are flaky). Prefer (a).

## eval_js safety (you can take the backend down)

The generated eval_js runs in the real browser. **Cap fetch concurrency** — sequential,
or ≤3 in flight, with short timeouts. A `Promise.all` over dozens of requests (e.g.
scraping every JS chunk) can crash the browser/backend. Keep probes small.

## Output + cleanup

- Shape the output to exactly the requested fields (`shape_js` or parse in the eval_js),
  not the raw body. Note any field the API reports oddly (e.g. retweets carry their own
  zeroed like count).
- Author the final dough in the workspace (`./<slug>/doughs/<slug>/` dough.yaml + box.yaml)
  so the user owns an editable copy — even though the live capture/promote also registers
  a backend copy. Delete throwaway probe doughs (`dough_publish.py delete`) when done;
  keep only the final.
- Record the hardcoded query ids / endpoint in a comment in the dough so the repair
  (when an id rotates) is a two-line edit, not a re-investigation.

## Honest trade to state in the report

Using the site's INTERNAL API (vs the official one) means: no key/paid tier, works on the
logged-in session — but the query ids rotate, so a `... http 404` someday means
"re-capture and swap two ids." Say this plainly.
