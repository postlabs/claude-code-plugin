---
name: dough-authoring
description: How to author Toast doughs (compositions) and user agent flours. Use when the user's request can be served by wiring existing flours together, or by LLM reasoning over data the dough already holds (a "reasoning gap").
---

# Authoring doughs and agent flours

**The grammar lives in Toast, not here.** Before writing any YAML, fetch the
live build guide and apply it as your own reasoning — **when the backend is
up**:

```
peel dough_spec(ids=["thinking.guide_build"])
```

**Offline (standalone tier — backend down):** peel and the live guide are
unreachable; SKIP the fetch and author from this skill's rules + the engine
ground truths below (the offline loop is spelled out in "The loop", step 1).

Its `action.agent` text is the full authoring contract — composition rules
(R1–R15), ref resolution, box.yaml requirements, the basic.* control-flow
flours, validator-error handling. This skill carries only what the guide
assumes you know PLUS the engine ground truths the guide gets wrong or omits
(verified against the engine 2026-06-11 — trust these over the guide on
conflict).

## Where files go

Author in the SESSION CWD, never in a Toast profile directory:
`./<automation_slug>/doughs/<dough_slug>/` holding `dough.yaml` + a sibling
`box.yaml` (engine file format). The cwd is the source of truth — visible
and versionable by the user. Id is exactly `user.<slug>`, two segments, no
nesting.

Publishing goes through the API, not the filesystem:

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/dough_publish.py publish <dough_dir> [--draft]
```

POST for new ids, PUT for existing (the script checks). A 422 response
carries the validator's issues — fix the YAML in cwd and republish;
publishing IS validation. `--draft` parks a half-wired state. The modify
flow is `pull <dough_id> <dest_dir>` → edit → `publish` — never edit or
write files under a profile directly. Prefer the original cwd source when it
exists: pull is lossy on labels (the backend persists only en name/about;
per-key descriptions and other locales come back regenerated).

## The two shapes you may author

- **Composition (`steps:`)** — wires existing flours/doughs. Steps allow only
  `dough:` / `each:` / `all:`. No inline `tool:`/`agent:`/`if:` — lift into a
  flour first; branching logic uses `basic.condition` and friends.
- **User agent flour (`action.agent:`)** — LLM reasoning over declared inputs
  and prior step outputs ONLY. Never an agent prompt that claims to fetch,
  browse, or call anything — that is a reach gap, which means a kit
  (see the kit-authoring skill).

`user.*` with `action: tool:` or `action: web:` is validator-rejected. If the
request needs to reach outside the workflow, do not bend an agent prompt —
author a kit.

**Exception — a reach gap against a WEBSITE is a capture, not a kit.** When the
data lives behind a logged-in site (esp. one whose official API is paywalled or
absent — X, internal dashboards), don't author an httpx kit that would need the
user's cookies/tokens. Bracket a `browse` with `start_api_capture` →
`promote_api`: it finds the page's own data API and caches a secret-free
in-browser `fetch` (the browser attaches the origin's cookies). Emits a
reusable `user.webapi_*` dough. Fall back to `promote_web_task` (DOM cache) when
`promote_api` returns `ok:false` (server-rendered page, no JSON API).

## Engine ground truths (verified — the guide's prose drifts on these)

1. **Always ref with the bare-step-id drill: `${<step>.<key>}`.** The save
   validator registers ONLY bare step ids in scope (`${fetch_docs.documents}`
   resolves; `${documents}` alone FAILS validation/save even though the runtime
   would resolve it). Use `${step.key}` everywhere, including `return:`.
2. **`publish:` does not exist.** If the build guide mentions an optional
   `publish:` on `each:`/`all:`, it is stale prose — the key parses silently
   and is IGNORED.
3. **A fan-out collects only the LAST body step's output**, one entry per item
   in input order, published under the bare last segment of the body's last
   `dough:` id. Need two reads per item (e.g. summarize + classify)? The kit must
   ship a combined flour — you cannot collect two body steps.
4. **Collected entries are envelopes.** Each item is the step's full output
   dict — `${summarize_doc}` is `[{"summary": {...}}, ...]`, not `[summary, ...]`. A
   flour consuming the collection must expect that envelope shape (check its
   spec/description; kit-authoring rule 9 is the producer side).
5. **DUP_PUBLISH:** two steps calling the same flour in one scope is a
   save-time error for user doughs. Wrap one call in a sub-dough or use an
   adapter flour.
6. **`each:` vs `all:`** — `all:` only helps when the body is async I/O
   (HTTP fetches). For sync CPU-bound tools use `each:` — concurrency buys
   nothing and `all:` still serializes on the event loop. An empty list is
   fine for both (zero items, no error); `None` is an error.

## Agent flours — keep the input compact

Feed an agent flour **compact structured data, never raw series**. A prompt
that inlines hundreds of data points (raw candles, full logs) blows past the
structured-emit ceiling and stalls the bake in 180s-retry loops. Pass the
*derived* shape instead (pivots, summary stats, the report object) — if the
input feels big, add a kit tool that condenses it first. Outputs: an
`object`/`list` agent output needs an inline `schema:` to come back
structured; keep it small; plain `string` needs none.

## The loop (this skill is the BUILD step — authoring only)

1. Discover: when the backend is up, `find_doughs` (by namespace when the
   vendor is known, by verb otherwise) → `dough_spec` every flour you will
   call; wire against the real `inputs:`/`outputs:`, never from memory, copy
   ids verbatim. When the backend is down, the live build guide and peel are
   unreachable — author from this skill's rules + ground truths, compose
   against workspace artifacts + floor capabilities (`basic.*`,
   `webengine.browser.*`, `thinking.*`), and flag every external-capability
   assumption as a warning for the report.
2. Write `dough.yaml` + `box.yaml` under
   `./<automation_slug>/doughs/<dough_slug>/`.
3. Static-validate:
   `python ${CLAUDE_PLUGIN_ROOT}/scripts/offline_validate.py <dough_dir>` —
   the same engine validator, vendored, no backend needed. Every issue's
   `hint` is a directive; fix in cwd and re-run. Two semantics: a dough that
   fails to PARSE is reported as parse errors (never read an unparseable
   dough as "0 issues"), and refs to flours outside the workspace come back
   as WARNINGS — carry them into the report.

That is the authoring bar. **Running it on the real engine — the test-bake,
the repair loop, "done = a real bake ran green" — is `/dough-creator:test`,
not this step.** Author so it WILL bake; do not bake here.
