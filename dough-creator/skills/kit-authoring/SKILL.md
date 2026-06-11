---
name: kit-authoring
description: How to author a Toast kit — Python tools + tool flours — and bind it live via the kit lifecycle API. Use when the user's request needs a capability no existing flour provides (a "reach gap" — calling an API, computing, parsing, transforming files) and a new kit must be created.
---

# Authoring a Toast kit

A **kit** is the only artifact that ships Python. It is a directory:

```
<kit_folder>/                  # folder name = kit id with dots → slashes (single-segment id = folder name verbatim)
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
id: my_kit
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

**Manifest rule 3.4 (will reject your kit at load if violated):** any kit whose
top-level id segment is not a reserved bundled vendor (`postlab`, `basic`,
`advanced`, `thinking`, `webengine`) loads as third-party. A third-party kit
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
5. **One tool = one primitive.** An HTTP call, a disk op, a parse, a pure
   computation over its inputs. **Never orchestrate inside a tool** — a
   function that fetches AND computes AND writes is a pipeline hiding from the
   engine; ship the primitives as separate tools and wire them in a
   composition dough instead. (Same-kit *computation* may compose — a tool may
   call sibling pure functions — but reach operations never stack.)
6. **Per-profile storage:** `from _core.profile import profile_dir` and use a
   kit-private subdir — `profile_dir() / "my_kit_store"`. There is NO injected
   `ctx` object (older docs mentioning `ctx.workspace_dir` are phantom).
   Tokens: `from _core.tokens import read_tokens, write_tokens` (auth kits).
7. **Auth failures raise built-in `PermissionError`** — the host translates it.
8. **Logging:** stdlib `logging.getLogger(__name__)`. No structlog, no prints.
9. **Fan-out consumers take envelope lists.** A tool whose input is the
   collected list of an `each:`/`all:` fan-out receives one
   `{"<output_key>": value}` dict PER ITEM (the engine collects each item's
   full step output). Unwrap explicitly (`[e["row"] for e in rows]`) and
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

- **`verb:` is a closed vocabulary** (`peel list_capabilities()` shows it —
  fetch/get/list/create/update/delete/send/convert/classify/search/review/
  filter/summarize/...). An invented verb (`read`, `analyze`...) does NOT fail
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

## The build loop (no backend restart, ever)

Work in a scratch directory OUTSIDE the Toast repo. Then drive the lifecycle
API via the plugin script:

```
python ${CLAUDE_PLUGIN_ROOT}/scripts/kit_lifecycle.py install <kit_dir>   # first bind
# → CONFIRM THE KIT ACTUALLY LOADED: install/reload response lists the kit;
#   a load failure (bad verb, bad model ref, import error) reports here —
#   "[kits] failed at load ValidationError" in logs means the WHOLE kit is out.
# → validate each flour:  peel validate_dough(dough_id="my_kit.fetch_rates")
# → test:                 peel bake(...) → peel recall(...) on failure
# edit Python, then:
python ${CLAUDE_PLUGIN_ROOT}/scripts/kit_lifecycle.py reload my_kit       # hot-reload
# → re-bake until green
```

- `install` copies the dir into `{profile}/doughs/<kit-id-as-path>/` and binds
  tools immediately. Re-installing an already-loaded id returns 409 — `reload`.
- `reload` re-imports from the kit's source dir. A failed reload leaves the
  kit UNLOADED — fix the import error and reload again.
- flour/box YAML edits inside `{profile}/doughs/` are picked up live; `reload`
  is only needed for Python changes.
- `uninstall` removes a non-bundled kit cleanly (bundled kits → 403).
- **Done = a real bake ran green**, not validation alone.

## Debugging a failed bake

`peel recall(dough_id=...)` returns the donut. Read `error_code` first:
`tool_failed` (your Python raised — fix, reload), `output_shape_mismatch`
(the `to:` mapping or return shape is wrong), `each_not_list`/`all_not_list`
(a ref didn't resolve to a list), `provider_not_connected` (missing
connect.py — see rule 3.4). Never guess from the prose message alone.

## Promotion (separate, later step — not part of /create)

A kit born here lands as a third-party kit under `{profile}/kits/`. Promoting
it to an official bundled kit means moving the source into the Toast repo's
`src/backend/kits/`, running `scripts/repair_flour_entries.py --check` and
`scripts/generate_kit_hashes.py`, and going through review. Do not do this
inside a /create run.
