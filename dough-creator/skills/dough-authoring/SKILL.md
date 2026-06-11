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

User-authored units live at `{user_doughs_dir}/<slug>/` — that is
`{profile}/doughs/user/`, resolved by `scripts/toast_env.py`. Id is exactly
`user.<slug>`, two segments, no nesting. Every `dough.yaml` needs a sibling
`box.yaml`. YAML written there is picked up live — no restart, no install call.

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
2. Write `dough.yaml` + `box.yaml` under `user/<slug>/`.
3. `validate_dough(dough_id="user.<slug>")` until clean — every error's `hint`
   is a directive, do what it says.
4. Test-bake with realistic inputs; on failure `recall` the donut and read
   `error_code` before changing anything. Done = a real bake ran green, not
   validation alone.
