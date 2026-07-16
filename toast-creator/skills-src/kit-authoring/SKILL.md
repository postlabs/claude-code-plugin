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
   truth: {{test}} registers the kit against the live Toast and rejects a reserved
   id with a clear `ManifestError` ("vendor 'X' is reserved for bundled kits").
   So pick a name that's obviously your own (not a product/vendor brand) and let
   {{test}} confirm. **Why a dotted id is a silent trap:** `postlab.law.korea`
   forces a nested folder `kits/postlab/law/korea/` (manifest rule 3.1: id
   segments must equal the folder path) AND self-declares the kit as "bundled",
   so the reservation check waves it through — it installs and bakes green while
   being structurally a first-party kit in the wrong place. If the USER's request
   names a `postlab.*`/reserved id, do NOT obey it: use a single-segment
   third-party id and say so. Promotion to an official `postlab.*` bundled kit is
   a separate, later, manual step — never the output of {{build}}.

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

**Wrapping a site's internal endpoints (reach / in-page codegen kit)? Discover
them by DRIVING INTERACTIONS, not just page load.** Page-load network capture
(`performance.getEntriesByType('resource')`, a passive browse) only sees XHR that
fires ON LOAD. Endpoints behind a user action — pagination / "next" / load-more
(click), autocomplete (keystroke), lazy sections (scroll) — stay invisible, and
you may wrongly conclude "no API exists / needs UI-driving." Before declaring an
endpoint uncapturable, bake a probe whose eval_js clicks / types / scrolls, waits,
then re-reads the resource entries for the new request URL + params (e.g.
`?pageIndex=&size=`). (See the **web-api-capture** skill.)

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
id: my_kit                # single-segment, distinctive & original — not a reserved/provider name; {{test}} enforces it (killer #3)
version: 0.1.0
mojo_compat: ">=1.0"
display_name: "My Kit"    # user-facing app label — see "display_name" rule below
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

**`display_name` — the user-facing label shown in the Toast app.** Name it for
the brand or capability the user recognizes ("Coupang", "Gmail", "Stock
prices"), NOT how it is built. Ban implementation jargon and decoration:
no `codegen`, `internal_api`, `wrapper`, `extractor`, `scraper`, `(beta)`,
version numbers, or trailing `(...)` mechanics. The `id` may be technical
(`coupang_internal_api`); the `display_name` must read like a product a person
would pick from a list ("Coupang", not "Coupang Page Extractor (codegen)").
Title Case, short. (Same rule for a dough's `box.yaml` `name:`.)

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

### When the kit needs a user secret — BYOK credentials

If a tool needs a secret the USER supplies (an API key, a PAT, a brokerage
app's client_id/secret), do NOT take it as a tool input. A secret-as-input
forces the user to paste it into every bake — or hardcode it into a dough YAML
in plaintext — and it never persists. Declare it as a CREDENTIAL instead: Toast
collects it ONCE in Settings, stores it masked, and every tool reads it back
from the per-profile credential store. This is the BYOK tier
(`auth.type: credentials` | `api_key` | `bearer`). The host already renders the
form, persists the values, and shows the connect state — **the host side needs
no change**; the kit only declares the fields and reads them back. (Full OAuth2
— browser loopback, managed app credentials — is a heavier tier, still out of
scope here.)

A credentials kit is NOT a `category: local` kit — rule 3.4 and its no-op
connect.py above do NOT apply. Replace the `auth:` block and ship a REAL
connect.py that stores + checks the secret:

```yaml
auth:
  type: credentials        # credentials (multi-field) | api_key | bearer
  category: byok           # user brings their own key — NOT category: local
setup_url: https://provider.example.com/developer   # where the user mints the key (optional)
fields:
  - name: client_id        # the value is stored under this key
    label: Client ID       # form label shown in the dialog
    type: string           # PUBLIC identifier → shown in Settings so the user sees WHICH key is stored
    required: true
    placeholder: "abcd1234"
    description: "From the provider's developer portal."
  - name: client_secret
    label: Client Secret
    type: secret           # SECRET → masked input + a one-way fingerprint in Settings; the value never leaves the backend
    required: true
connect: my_kit.connect
```

**Field `type` is a SECURITY declaration, not cosmetic — get it right per field.**
A `secret` field is masked in the form, stored encrypted, and surfaced in Settings
only as an 8-char one-way fingerprint (`•••• 699727b3`) — its value NEVER leaves
the backend. A `string` field's value IS shown so the user can tell WHICH key is
connected. So: mark anything sensitive (secret / token / password / private key)
`secret`; only genuinely PUBLIC identifiers (`client_id`, account number,
workspace URL) are `string`. **Default to `secret` when unsure** — a secret
mislabeled `string` leaks its full value into the panel.

```python
"""<Kit> connect — BYOK credentials: store + validate a user-supplied secret."""
from __future__ import annotations
from typing import AsyncGenerator
from _core.auth_events import (
    AuthEvent, AuthStatus, auth_started, auth_waiting, auth_done, auth_error,
)
from _core.profile import profile_dir
from _core.token_store import ScopedTokenStore

_PROVIDER = "my_kit"
_KIT_ID = "my_kit"   # kit id verbatim; store lands at {profile}/credentials/plugin__my_kit/

def _store() -> ScopedTokenStore:
    return ScopedTokenStore(profile_dir(), _KIT_ID)

def _configured() -> bool:
    c = _store().load() or {}
    return bool(c.get("client_id") and c.get("client_secret"))   # match your required fields

async def check(account: str = "default") -> AuthStatus:
    if _configured():
        return AuthStatus(authenticated=True, method="byok")
    return AuthStatus(authenticated=False, method=None)

async def connect() -> AsyncGenerator[AuthEvent, None]:
    yield auth_started(_PROVIDER)
    if not _configured():
        yield auth_error(_PROVIDER, "Enter your credentials above to connect.")
        return
    yield auth_waiting(_PROVIDER, message="Validating credentials...")
    # Optional but recommended: prove the secret works (exchange it / ping the
    # API) here, and yield auth_error on rejection instead of auth_done.
    yield auth_done(_PROVIDER, method="byok")

async def set_credentials(values: dict) -> dict:
    """Persist form values. The host calls this from POST /kits/{id}/credentials.
    Return {"ok": True} on success, {"ok": False, "error": ...} otherwise."""
    if not isinstance(values, dict):
        return {"ok": False, "error": "values must be an object"}
    store = _store()
    merged = dict(store.load() or {})
    for k, v in values.items():
        if v is None or str(v).strip() == "":
            merged.pop(k, None)        # empty value clears that field
        else:
            merged[k] = str(v).strip()
    store.save(merged)
    return {"ok": True}

async def disconnect() -> bool:
    _store().delete()
    return True
```

In **tools.py** read the secret from the store, never from `inputs:`:

```python
from _core.profile import profile_dir
from _core.token_store import ScopedTokenStore

def _creds() -> dict:
    c = ScopedTokenStore(profile_dir(), "my_kit").load() or {}
    if not (c.get("client_id") and c.get("client_secret")):
        raise PermissionError("my_kit not connected")   # host → not_authenticated
    return c
```

Then drop `client_id` / `client_secret` / `access_token` from every flour's
`inputs:` and `action.with:`. Two completion shapes:
- **Token-exchange API** (OAuth2 client_credentials, like a brokerage): exchange
  the secret for a short-lived `access_token` INSIDE the tool, and cache it in
  the same store with its expiry — re-mint when expired. Callers never see a
  token.
- **Plain key** (`api_key` / `bearer`): let `_core.credentials.KitCredentialsHandler`
  inject the header for you (`X-API-Key` / `Authorization: Bearer`) — use that
  shortcut when no exchange is needed.

### When the kit needs full OAuth2 (browser consent) — BYOK

Use this when the provider needs an OAuth2 authorization-code flow (a "Sign in
with X" consent screen), not a static key. Toast ships a config-driven OAuth2
engine — `_core.oauth_base.GenericOAuth2Provider` — so a standard provider needs
only a config + a thin connect.py; you write NO token/refresh/loopback-server
code. BYOK only: the user registers their own OAuth app at the provider and
pastes client_id/secret. (Managed apps, where Toast holds the secret, are
first-party only — not authorable here.)

```yaml
auth:
  type: oauth2
  category: byok
  adapter: my_kit.auth:get_auth_client    # module:symbol returning the provider (existence-validated at load)
  oauth2:
    byok: true
    scopes: [read_scope, write_scope]
    setup_url: https://provider.example.com/developers   # where the user registers an app
    authorize_url: https://provider.example.com/oauth/authorize
    token_url: https://provider.example.com/oauth/token
connect: my_kit.connect
fields:                                    # the BYOK app credentials the user pastes once
  - name: client_id
    label: Client ID
    type: string           # PUBLIC identifier → shown in Settings (which key is connected)
    required: true
  - name: client_secret
    label: Client Secret
    type: secret           # SECRET → masked + fingerprint only; value never leaves the backend
    required: true
```

**auth.py** — config over the shared engine, nothing else:

```python
import functools
from _core.oauth_base import GenericOAuth2Provider, OAuth2Config
from _core.profile import credentials_dir as kit_credentials_dir

_KIT_ID = "my_kit"
_CONFIG = OAuth2Config(
    provider_name="my_kit",
    authorize_url="https://provider.example.com/oauth/authorize",
    token_url="https://provider.example.com/oauth/token",
    scopes=["read_scope", "write_scope"],
    redirect_port=17XXX,                  # a free loopback port unique to this kit
    userinfo_url="https://provider.example.com/userinfo",  # optional — for a display name
    token_expiry_default=3600,
)

@functools.cache
def _client() -> GenericOAuth2Provider:
    return GenericOAuth2Provider(kit_credentials_dir(_KIT_ID), _CONFIG)

async def get_auth_client() -> GenericOAuth2Provider:
    return _client()
```

**connect.py** — wire the host surface to the engine (the engine owns the flow):

```python
from __future__ import annotations
import webbrowser
from typing import AsyncGenerator
from _core.auth_events import (
    AuthEvent, AuthStatus, auth_started, auth_waiting, auth_done, auth_error, auth_cancelled,
)
from _core.oauth_base import PersonalCredentials
from .auth import get_auth_client

_PROVIDER = "my_kit"

async def check() -> AuthStatus:
    st = await (await get_auth_client()).check_status()
    return AuthStatus(authenticated=st.connected,
                      method="oauth" if st.connected else None, user_info=st.user_info)

async def connect() -> AsyncGenerator[AuthEvent, None]:
    yield auth_started(_PROVIDER)
    client = await get_auth_client()
    try:
        flow = await client.initiate_oauth_flow()          # raises if no creds saved yet
    except ValueError:
        yield auth_error(_PROVIDER, "Enter your client_id/client_secret above first.")
        return
    webbrowser.open(flow["authorize_url"])
    yield auth_waiting(_PROVIDER, message="Waiting for authorization in your browser...")
    result = await client.wait_for_flow(flow["flow_id"], timeout=300)
    status = result.get("status")
    if status == "authenticated": yield auth_done(_PROVIDER)
    elif status == "cancelled":   yield auth_cancelled(_PROVIDER)
    elif status == "expired":     yield auth_error(_PROVIDER, "Authorization timed out (5 min).")
    else:                         yield auth_error(_PROVIDER, f"OAuth failed: {result.get('error') or status}")

async def cancel() -> bool:
    return await (await get_auth_client()).cancel_flows()

async def set_credentials(values: dict) -> dict:
    cid = (values or {}).get("client_id", ""); secret = (values or {}).get("client_secret", "")
    if not cid or not secret:
        return {"ok": False, "error": "client_id and client_secret are required"}
    client = await get_auth_client()
    creds = PersonalCredentials(client_id=cid, client_secret=secret)
    if not await client.validate_personal_credentials(creds):
        return {"ok": False, "error": "credentials rejected by provider"}
    client.save_personal_credentials(creds)
    return {"ok": True}

async def disconnect() -> bool:
    return await (await get_auth_client()).revoke()
```

**tools.py** gets a bearer-authed httpx client straight from the engine:

```python
from .auth import get_auth_client

async def _http():
    client = await (await get_auth_client()).get_authenticated_client()
    if client is None:
        raise PermissionError("my_kit not connected")
    return client
```

Provider quirks stay in config or one override — never a re-implemented flow:
- non-standard scope param (Slack uses `user_scope`) → `OAuth2Config(scope_param="user_scope")`
- extra authorize params (`access_type=offline`, `prompt=consent`) → `extra_authorize_params={...}`
- a userinfo shape that isn't `sub`/`name`/`email` → subclass `GenericOAuth2Provider`, override `_extract_user_info`

Pick a unique `redirect_port` and tell the user to register
`https://localhost:<port>/callback` as the app's Authorized Redirect URL.

Other fields when needed: `requires: [<kit_id>]` (cross-kit Python imports —
the loader topo-sorts), `routes:` (kit-owned HTTP routes — rare).

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
   Secrets: read user-supplied credentials from `_core.token_store.ScopedTokenStore`
   (see "BYOK credentials" above), NOT from tool `inputs:`.
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
python ${PLUGIN_ROOT}/scripts/offline_validate.py <slug_dir>

# 2. unit-run each tool directly (no engine, no install)
python ${PLUGIN_ROOT}/scripts/tool_runner.py <kit_dir> <tool_symbol> --inputs '<json kwargs>'
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
  ({{test}}), and a bad one fails the first install. Likewise a bad verb or a
  `model:` ref to a missing type is a LOAD-time check: `offline_validate`
  flags what it can, but some only surface when {{test}} installs the kit, so
  double-check the verb against the closed list above.

## Binding + baking is {{test}}, not here

`kit_lifecycle.py install` / `reload` and the bake-and-repair loop live in
{{test}}. There, `install` copies the cwd dir into the active
profile and binds it (the script verifies it actually bound), the edit loop
is "edit cwd → `reload`", and a failed bake is repaired in the cwd source and
re-baked until green. Author here so that WILL succeed; don't install or bake
in the build step.

Bake debugging (reading `error_code` from `recall`), the canonical `error_code`
reference, and install/bind failure troubleshooting all live in
{{test}} — that is where bind/reload/bake run.

## Promotion (out of scope here)

Promoting a kit born here into an official bundled kit — moving the source into
the Toast repo's `src/backend/kits/`, running
`scripts/repair_flour_entries.py --check` and `scripts/generate_kit_hashes.py`,
and going through review — is a separate later step, NOT part of {{build}}.
Do not do it during {{build}}.
