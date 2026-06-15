---
name: kit-authoring
description: How to author a Toast kit — Python tools + tool flours — and bind it live via the kit lifecycle API. Use when the user's request needs a capability no existing flour provides (a "reach gap" — calling an API, computing, parsing, transforming files) and a new kit must be created.
---

# Authoring a Toast kit

## Three load-time killers — read these FIRST

Three mistakes pass every static/offline check, then bite at KIT LOAD or
silently build the WRONG structure. Nothing else in this skill is this
consequential; get these right before anything else.

1. **An invented `verb:`.** `verb:` is a CLOSED vocabulary. `read`, `analyze`,
   and the like are NOT verbs — they pass offline validation and fail at LOAD
   (the whole kit goes invalid). Only ever use a verb that
   `peel list_capabilities()` lists. (Full list + detail under "Tool flour —
   dough.yaml shape".)
2. **A third-party no-auth kit missing `auth.category: local` + `connect.py`
   (manifest rule 3.4).** Without it the kit is rejected at load and every bake
   fails preflight with `provider_not_connected`. (Detail under "kit.yaml".)
3. **A RESERVED vendor in the kit id.** A kit you author here is THIRD-PARTY —
   give it a single-segment, **distinctive and original** id (`law_kr`,
   `weather`, `acme_invoices`), NEVER a first-party namespace like
   `postlab.law.korea`. The first segment must not collide with a reserved
   bundled vendor — those are the first-party floor kits (`postlab`, `basic`, …)
   AND every provider Toast integrates (`slack`, `notion`, `google`, …). **Don't
   hardcode that list here — it lives in the backend (`VENDOR_BUNDLED_ONLY`) and
   grows as providers are added, so any copy drifts.** The backend is the ground
   truth: `/test` registers the kit against the live Toast and rejects a reserved
   id with a clear `ManifestError` ("vendor 'X' is reserved for bundled kits").
   So pick a name that's obviously your own (not a product/vendor brand) and let
   `/test` confirm. **Why a dotted id is a silent trap:** `postlab.law.korea`
   forces a nested folder `kits/postlab/law/korea/` (manifest rule 3.1: id
   segments must equal the folder path) AND self-declares the kit as "bundled",
   so the reservation check waves it through — it installs and bakes green while
   being structurally a first-party kit in the wrong place. If the USER's request
   names a `postlab.*`/reserved id, do NOT obey it: use a single-segment
   third-party id and say so. Promotion to an official `postlab.*` bundled kit is
   a separate, later, manual step — never the output of `/create`.

## Cut kits by capability axis, not by request

A kit is a LIBRARY (think Python package), and one request usually decomposes
into more than one library. Before writing kit.yaml, split what you're about
to build along these axes:

- **Reach vs compute.** A tool that touches the world (HTTP fetch, disk) and a
  pure computation that could consume data from ANY source belong in SEPARATE
  kits — the compute kit takes the data as an input and stays reusable when
  the data source changes.
- **Vendor-neutral naming.** Never name a compute kit after a data vendor
  (`gdrive_textstats` for source-agnostic text statistics is wrong; the fetch
  kit may carry the vendor name, the analysis kit may not).
- **Producer vocabulary only.** A tool's outputs describe its OWN domain.
  Mapping to another surface's vocabulary — chart-library study names, URL/pair
  formats for some website, display labels — belongs in the consuming kit or
  the user recipe, never in the producer's return shape.

Small kits are fine: a 1-flour fetch kit is a correct library, not an
under-built one.

A **kit** is the only artifact that ships Python. It is a directory:

```
<kit_folder>/                  # third-party kit: single-segment id = folder name verbatim (kits/law_kr/). NEVER a reserved dotted id — see killer #3.
├── kit.yaml                   # manifest
├── connect.py                 # REQUIRED for no-auth kits (see below)
├── tools.py                   # ALL Python code lives here (kit level)
├── types.py                   # Pydantic models for object/list outputs (model: refs)
├── <flour_name>/              # one flour directory per tool
│   ├── dough.yaml             # action.tool: <kit_id>.<symbol> + inputs/outputs
│   └── box.yaml               # display labels (REQUIRED, en complete; en+ko is the convention)
└── icon.svg                   # optional
```

## kit.yaml — minimal manifest

```yaml
id: my_kit                # single-segment, distinctive & original — not a reserved/provider name; /test enforces it (killer #3)
version: 0.1.0
mojo_compat: ">=1.0"
display_name: "My Kit"
description: "One sentence on what the tools do."
author: "Toast team"
license: "MIT"
auth:
  type: none
  category: local         # REQUIRED — see rule 3.4 below
connect: my_kit.connect   # REQUIRED with category: local
```

**Never write `provides:` in kit.yaml** — the loader derives the tool list by
walking the flour directories. A `provides:` block is rejected.

**Manifest rule 3.4 (load-time killer — see top of skill):** any kit whose
top-level id segment is not a reserved bundled vendor (the backend's
`VENDOR_BUNDLED_ONLY` — don't enumerate it, see killer #3) loads as
third-party. A third-party kit
with `auth.type: none` MUST declare `auth.category: local` AND ship a
`connect.py`, or it is rejected at load — and without the connect module every
bake fails preflight with `provider_not_connected`. For a pure-compute kit the
connect module is a no-op:

```python
"""<Kit> connect — local no-auth surface. Pure computation; always connected."""
from __future__ import annotations
from typing import AsyncGenerator
from _core.auth_events import AuthEvent, AuthStatus, auth_started, auth_done

_PROVIDER = "my_kit"

async def check(account: str = "default") -> AuthStatus:
    return AuthStatus(authenticated=True, method="local")

async def connect() -> AsyncGenerator[AuthEvent, None]:
    yield auth_started(_PROVIDER)
    yield auth_done(_PROVIDER, method="local")
```

Other fields when needed: `requires: [<kit_id>]` (cross-kit Python imports —
the loader topo-sorts), `routes:` (kit-owned HTTP routes — rare),
`auth.adapter:` (OAuth kits — out of v1 scope).

## tools.py — the rules

1. **All code at kit level.** Everything in `tools.py`; past ~600 lines split
   into concern modules (`classify.py`, `ingest.py`) and point each affected
   flour at its symbol with a TOP-LEVEL `entry: <file>.py:<symbol>` key in its
   dough.yaml (without `entry:` the loader infers `tools.py:<symbol>`).
2. **A `.py` inside a flour directory is REJECTED** by the kit validator.
   Flour dirs hold `dough.yaml` + `box.yaml`, nothing else.
3. **Never import `app.*`.** Allowed: stdlib, the kit's own modules (absolute
   form — `from my_kit.classify import x`), declared `requires:` kits, shipped
   third-party deps (`pydantic`, `httpx`, `ruamel`), and `from _core.<mod>`.
4. **Plain functions.** A tool is a regular (sync or async) function whose
   kwargs match the flour's `action.with:` keys, returning a JSON-friendly
   dict. No decorators, no registration call, no ctx/self parameter — the
   loader binds the symbol named in `action.tool:` and calls it with decoded
   kwargs only.
5. **One tool = one primitive.** The test: can the engine — and the user
   reading the steps — SEE each moving part of the workflow? If not, split. An
   HTTP call, a disk op, a parse, or a pure computation over its inputs is one
   primitive. **Never orchestrate inside a tool**, and "orchestration" includes
   pure compute. The four ways a tool hides work from the engine:
   - *Pipeline* — a function that fetches AND computes AND writes. Ship the
     primitives, wire them in a composition.
   - *Hidden `each:`* — a tool that ITERATES over a caller-visible list of work
     items (documents, files, records). Ship the per-item primitive
     (`summarize_doc(document)`) and let the composition fan out.
   - *Multiple results* — a tool that returns several independently-useful
     results (entities AND per-section stats AND a representative excerpt AND an
     assembled report) is several tools: one primitive per result, plus at most a thin
     `assemble_*` reshaper at the end.
   - *Buried judgment* — judgment calls (which result is "best", what to
     display) belong in a composition step (an agent flour or a user-visible
     input), not in tool Python.

   Counter-exception: a tool may still call sibling pure HELPER functions (a
   parser calling its tokenizer is one primitive).
6. **Per-profile storage:** `from _core.profile import profile_dir` and use a
   kit-private subdir — `profile_dir() / "my_kit_store"`. There is NO injected
   `ctx` object (older docs mentioning `ctx.workspace_dir` are phantom).
   Tokens: `from _core.tokens import read_tokens, write_tokens` (auth kits).
7. Auth failures raise built-in `PermissionError` — the host translates it.
8. Logging: use stdlib `logging.getLogger(__name__)` (no structlog, no prints).
9. **Fan-out consumers take envelope lists** (this is the PRODUCER side of
   dough-authoring ground-truth 4 — the two halves are one contract). A tool
   whose input is the collected list of an `each:`/`all:` fan-out receives one
   `{"<output_key>": value}` dict PER ITEM (the engine collects each item's
   full step output). Unwrap explicitly (`[e["summary"] for e in items]`) and
   document the envelope in the docstring.

## Tool flour — dough.yaml shape

```yaml
id: my_kit.fetch_rates          # <kit_id>.<flour_dir_name>
version: 0.1.0
source: kit
verb: fetch                     # MUST be a real capability verb — see below
object: rates
entry: market.py:fetch_rates    # only when the symbol is not in tools.py
inputs:
  currency:
    type: string
    required: true
    default: USD
outputs:
  rates:
    type: list
    model: my_kit.types:Rates   # object/list outputs REQUIRE a model: (R11)
    display: data_table
action:
  tool: my_kit.fetch_rates      # <kit_id>.<python_symbol>
  with:
    currency: ${inputs.currency}
  to:
    rates: ${result.rates}      # drill the tool's return dict into each output
return:
  rates: ${rates}
```

- **`verb:` is a closed vocabulary** (load-time killer — see top of skill).
  `peel list_capabilities()` shows it —
  fetch/get/list/create/update/delete/send/convert/classify/search/review/
  filter/summarize/... . An invented verb (`read`, `analyze`...) does NOT fail
  static validation — it fails at KIT LOAD and takes the *whole kit* down
  (every flour invalid). Never invent a verb.
- **`to:` drills, it does not unwrap.** `to: rates` (bare string) binds the
  WHOLE tool return dict under that output — almost never what you want when
  the tool returns `{"rates": [...]}`. Use the mapping form
  `to: {rates: ${result.rates}}`.
- `model:` refs point at YOUR OWN kit's `types.py` only — a cross-kit model
  ref creates a hidden Python dependency. Inputs use plain `type: object`/
  `list` without `model:`.
- No `description:` on inputs/outputs (rejected, R12) — all display text goes
  in `box.yaml`: per locale `name`/`about` plus `{name, description}` for
  EVERY input AND output key. `en` complete is validator-enforced; ship ko too.

## Where the kit lives + the build-step checks (no backend)

Author the kit at its PERMANENT home — `./<automation_slug>/kits/<kit_id>/`
inside the session cwd. The user's project IS the kit's permanent source:
visible, versionable, and the path the backend later re-imports from. Never
author in a throwaway scratch dir, and never write into a Toast profile
yourself.

This skill is the BUILD step — author + check WITHOUT a backend. Two rungs:

```
# 1. static-validate each flour's YAML (verb, model: refs, box) — vendored engine
python ${CLAUDE_PLUGIN_ROOT}/scripts/offline_validate.py <slug_dir>

# 2. unit-run each tool directly (no engine, no install)
python ${CLAUDE_PLUGIN_ROOT}/scripts/tool_runner.py <kit_dir> <tool_symbol> --inputs '<json kwargs>'
```

- Unit-run EVERY tool with realistic inputs; check the returned dict against
  each flour's `to:` mapping and `outputs:` keys — `output_shape_mismatch`
  is the bug class this catches before any engine exists. Symbols outside
  tools.py take the `<file>.py:<symbol>` form (see `--help`).
- The runner stubs `_core` (tiny shim, enough for unit execution). **Store
  kits** — anything calling `_core.profile.profile_dir()` — need
  `TOAST_STORE_DIR` set to a scratch dir inside the workspace so the stub has
  a place to write. Never point it at a Toast profile path.
- Author connect.py / rule 3.4 (`auth.category: local`) correctly NOW even
  though unit runs never execute connect.py — it is checked at install time
  (`/test`), and a bad one fails the first install. Likewise a bad verb or a
  `model:` ref to a missing type is a LOAD-time check: `offline_validate`
  flags what it can, but some only surface when `/test` installs the kit, so
  double-check the verb against the closed list above.

## Binding + baking is `/test`, not here

`kit_lifecycle.py install` / `reload` and the bake-and-repair loop live in
`/dough-creator:test`. There, `install` copies the cwd dir into the active
profile and binds it (the script verifies it actually bound), the edit loop
is "edit cwd → `reload`", and a failed bake is repaired in the cwd source and
re-baked until green. Author here so that WILL succeed; don't install or bake
in the build step.

Bake debugging (reading `error_code` from `recall`), the canonical `error_code`
reference, and install/bind failure troubleshooting all live in
`/dough-creator:test` — that is where bind/reload/bake run.

## Promotion (out of scope here)

Promoting a kit born here into an official bundled kit — moving the source into
the Toast repo's `src/backend/kits/`, running
`scripts/repair_flour_entries.py --check` and `scripts/generate_kit_hashes.py`,
and going through review — is a separate later step, NOT part of `/create`.
Do not do it inside a `/create` run.
