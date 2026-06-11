---
name: dough-authoring
description: How to author Toast doughs (compositions) and user agent flours. Use when the user's request can be served by wiring existing flours together, or by LLM reasoning over data the dough already holds (a "reasoning gap").
---

# Authoring doughs and agent flours

**The grammar lives in Toast, not here.** Before writing any YAML, fetch the
live build guide and apply it as your own reasoning:

```
peel dough_spec(ids=["thinking.guide_build"])
```

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

## Engine ground truths (verified — the guide's prose drifts on these)

1. **Always ref with the bare-step-id drill: `${<step>.<key>}`.** The save
   validator registers ONLY bare step ids in scope (`${fetch_ohlcv.candles}`
   resolves; `${candles}` alone FAILS validation/save even though the runtime
   would resolve it). Use `${step.key}` everywhere, including `return:`.
2. **`publish:` does not exist.** If the build guide mentions an optional
   `publish:` on `each:`/`all:`, it is stale prose — the key parses silently
   and is IGNORED.
3. **A fan-out collects only the LAST body step's output**, one entry per item
   in input order, published under the bare last segment of the body's last
   `dough:` id. Need two reads per item (e.g. backtest + eval)? The kit must
   ship a combined flour — you cannot collect two body steps.
4. **Collected entries are envelopes.** Each item is the step's full output
   dict — `${run_strategy}` is `[{"row": {...}}, ...]`, not `[row, ...]`. A
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

## The loop

1. Discover first: `find_doughs` (by namespace when the vendor is known, by
   verb otherwise) → `dough_spec` every flour you will call. Wire against the
   real `inputs:`/`outputs:` — never from memory. Copy ids verbatim.
2. Write `dough.yaml` + `box.yaml` under `./<automation_slug>/doughs/<dough_slug>/`.
3. `dough_publish.py publish <dough_dir>` until it saves clean — a 422 returns
   the validator's issues and every issue's `hint` is a directive, do what it
   says. Fix in cwd, republish.
4. Test-bake with realistic inputs; on failure `recall` the donut and read
   `error_code` before changing anything. Done = a real bake ran green, not
   validation alone.

### Standalone (Tier 1 — no backend)

Same authoring, different gate. When `toast_env.py` reports
`tier: standalone`:

- peel is down, so the live build guide (`dough_spec` on
  `thinking.guide_build`) is unreachable — author from this skill's rules
  and ground truths alone.
- Steps 3–4 become
  `python ${CLAUDE_PLUGIN_ROOT}/scripts/offline_validate.py <dough_dir>` —
  the same engine validator, vendored. Two semantics to know: a dough that
  fails to PARSE is reported as parse errors (the wrapper surfaces pydantic
  issues itself — never read an unparseable dough as "0 issues"), and refs
  to flours not present in the workspace are downgraded to WARNINGS
  (there is no backend store to confirm them) — carry every such warning
  into the final report.
- No test-bake. The bar is the standalone verification ladder in `/create`;
  record the level reached per artifact in `./<slug>/provenance.yaml` —
  the dough stays engine-UNVERIFIED until a connected run publishes and
  bakes it green.
