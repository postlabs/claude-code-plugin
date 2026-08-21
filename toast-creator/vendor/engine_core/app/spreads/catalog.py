"""Block catalog reader — the backend view of the skin-kit's shipped catalog.

Replaces the old hand-copied backend mirror of the frontend catalog. The Tier-3
``BLOCK_DEFS`` + ``FIELD_ROLES`` (``layout/blocks/defs.ts``) are captured at
skin-kit BUILD time into a plain-data ``catalog.json`` (emitted from
``defs.ts`` by ``src/scripts/emit_spread_catalog.py``, pinned to the frontend
source by ``tests/e2e/test_design_catalog_sync.py``). This module reads that JSON
as DATA and shapes it into the exact surface the composition validator consumes —
block kind ∈ catalog, required/optional roles, enum knobs, and the donut-snapshot
FIELD-path roles. The old regex-mirror discipline (a hand copy + its ``.ts``
sync test + parser) is retired: there is no hand copy to drift, so no CI pin
re-deriving it from the ``.ts``.

``app/spreads`` is a strict leaf: this reads ``catalog.json`` as JSON via path
math — the installed profile copy first (``{profile}/skins/classic/dist/
catalog.json``), the bundled skin source as fallback — and NEVER
``import kits.*`` (the shippability barrier), exactly as
``app.memo.spreads.kit_mirror`` reads generated manifest data. The skin kit
that ships the catalog is ``classic`` (``src/skins/classic`` in-repo,
installed to ``{profile}/skins/classic/``).

The exposed surface (``BLOCK_DEFS`` / ``FIELD_ROLES`` / ``BlockDef`` /
``block_kinds`` / ``roles_for`` / ``field_roles_for``) is byte-for-type identical
to the retired hand mirror — required/optional are tuples, knob values are
tuples, ``FIELD_ROLES`` values are frozensets — so consumers repoint by import
line only.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import NotRequired, TypedDict


class BlockDef(TypedDict):
    required: tuple[str, ...]
    optional: tuple[str, ...]
    knobs: dict[str, tuple[str, ...]]
    # The block's afforded spark GESTURES (Spark §13.2) — the set a spark `on:`
    # discriminator may name when anchored here. Empty for a block that affords none.
    afforded: tuple[str, ...]
    # The role naming THIS block's own list — the seam a `view:` op reshapes.
    # Read with `.get()` everywhere (NotRequired): a catalog.json installed before
    # view ops existed simply has no `listRole`, and must degrade to "this block
    # refuses view ops" rather than a KeyError at boot.
    listRole: NotRequired[str]
    # The SEGMENT a row-scoped spark anchor descends by (`$rowList.row`). The one
    # fact about a pressable block that cannot be walked, so `spark.anchor._descent`
    # derives the whole row-scope tree from it instead of keeping a second table.
    # NotRequired for the same reason as `listRole`: an older catalog simply says
    # nothing, and the kind then hosts no row-scoped anchor.
    rowScope: NotRequired[str]
    # The role carrying a literal CHILD-BLOCK list, and whether the child is stamped
    # once (a container: ``section``/``columns``/``tabs``) or PER RECORD (a list block
    # stamping an authored sub-document per row: ``entityCards``/``cardList``). The
    # one fact about a role an author cannot read off its name — ``blocks`` looks the
    # same on a block that renders it and on one that never had it. NotRequired for
    # the same reason as ``listRole``: an older catalog simply says nothing.
    nests: NotRequired[dict]


# The bundled/default skin kit id + its catalog location within the kit dir.
_KIT_ID = "classic"
_CATALOG_REL = Path("dist") / "catalog.json"


def _bundled_catalog_path() -> Path:
    """The in-repo skin-kit SOURCE catalog (dev / test / frozen seed)."""
    from app.config.settings import get_settings

    return get_settings().bundled_skins_dir / _KIT_ID / _CATALOG_REL


def _profile_catalog_path() -> Path | None:
    """The installed profile copy at ``{profile}/skins/classic/dist/
    catalog.json`` — the runtime source of truth. ``None`` when no profile is
    resolvable yet (test collection, early boot)."""
    try:
        from app.config.profile_paths import ProfilePaths
        from app.utils.profile.profile_resolver import resolve_active_profile_key

        pp = ProfilePaths.from_settings(resolve_active_profile_key())
        return Path(pp.skins.path) / _KIT_ID / _CATALOG_REL
    except Exception:  # no active profile / resolver not ready — bundled fallback
        return None


def catalog_path() -> Path:
    """Resolve the shipped ``catalog.json``. The installed profile copy is
    authoritative at runtime (so a stale copy is what the doctor probe catches);
    the bundled skin-kit source is the dev/test/seed fallback."""
    profile = _profile_catalog_path()
    if profile is not None and profile.is_file():
        return profile
    return _bundled_catalog_path()


def read_catalog() -> dict:
    """Read + parse the shipped ``catalog.json`` (raises if it moved/missing)."""
    return json.loads(catalog_path().read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, BlockDef], dict[str, frozenset[str]], dict[str, dict[str, dict]]]:
    """Shape ``catalog.json`` into the validator surface (tuples + frozensets)."""
    data = read_catalog()
    blocks: dict[str, BlockDef] = {
        kind: {
            "required": tuple(d.get("required", ())),
            "optional": tuple(d.get("optional", ())),
            "knobs": {kn: tuple(vals) for kn, vals in (d.get("knobs") or {}).items()},
            "afforded": tuple(d.get("afforded", ())),
            **({"listRole": d["listRole"]} if d.get("listRole") else {}),
            **({"rowScope": d["rowScope"]} if d.get("rowScope") else {}),
            **({"nests": d["nests"]} if d.get("nests") else {}),
        }
        for kind, d in data.get("blocks", {}).items()
    }
    field_roles: dict[str, frozenset[str]] = {
        block: frozenset(roles) for block, roles in data.get("fieldRoles", {}).items()
    }
    # `roleKinds` is DERIVED from the compilers + primitive interfaces, so it answers
    # the question `blocks` cannot: what a role's VALUE must be. Absent on a catalog
    # installed before it existed — `.get()` everywhere, and every dependent check
    # then simply does not fire.
    role_kinds: dict[str, dict[str, dict]] = data.get("roleKinds", {}) or {}
    return blocks, field_roles, role_kinds


def __getattr__(name: str):
    """Lazily expose ``BLOCK_DEFS`` / ``FIELD_ROLES`` as module attributes so the
    catalog file is read on first ACCESS (after boot + kit install), not at
    import — the profile copy may not exist until the loader has run."""
    if name == "BLOCK_DEFS":
        return _load()[0]
    if name == "FIELD_ROLES":
        return _load()[1]
    if name == "ROLE_KINDS":
        return _load()[2]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def block_kinds() -> frozenset[str]:
    """The block kinds a composition spread may name."""
    return frozenset(_load()[0].keys())


def required_for(block: str) -> frozenset[str]:
    """The roles a block REQUIRES (empty if unknown)."""
    d = _load()[0].get(block)
    return frozenset(d["required"]) if d else frozenset()


def roles_for(block: str) -> frozenset[str]:
    """Every role (required ∪ optional) a block accepts (empty if unknown)."""
    d = _load()[0].get(block)
    if d is None:
        return frozenset()
    return frozenset(d["required"]) | frozenset(d["optional"])


def field_roles_for(block: str) -> frozenset[str]:
    """The donut-snapshot FIELD-path roles of a block (empty when not scoped)."""
    return _load()[1].get(block, frozenset())


def path_roles_for(block: str) -> frozenset[str]:
    """The roles of one block that read a PATH off the value — a field role, or
    one the derived contract types ``rootPath``. Fixed text cannot go in any of
    them: the block roots the role through ``rootKey()``, which turns a bare
    string into ``$.<string>``, so a literal is read as a path and comes back
    empty (see the ``roleKinds`` note in ``CLAUDE.md``).

    ★ ONE DEFINITION, TWO CONSUMERS, AND THEY MUST BE THE SAME SET.
    ``validate._field_path_issues`` REFUSES a path role bound to text;
    ``block_guide.grouped`` — the payload ``find_blocks`` teaches the language
    with — says which roles those are. The union was computed inline in the
    gate and taught nowhere, so the catalogue withheld the one rule its own gate
    enforces: measured, an agent composing a card learned ``section.title`` reads
    a path by being rejected for it, mid-turn, in front of the user.
    """
    return frozenset(field_roles_for(block)) | frozenset(
        r for r in roles_for(block)
        if (role_kind(block, r) or {}).get("kind") == "rootPath"
    )


def viewable_kinds() -> frozenset[str]:
    """Block kinds declaring a ``listRole`` — the ones that accept ``view:`` ops.
    Empty on a catalog installed before view ops existed, which is the intended
    degradation: every ``view:`` is then refused with a message naming the (empty)
    legal set, rather than the loader dying."""
    return frozenset(k for k, d in _load()[0].items() if d.get("listRole"))


def list_role_for(block: str) -> str | None:
    """The block's own list role, or ``None`` if it has no list to reshape."""
    return _load()[0].get(block, {}).get("listRole")


def role_kind(block: str, role: str) -> dict | None:
    """The derived VALUE contract for one ``(block, role)`` pair, or ``None``.

    Per PAIR, never per role name — the same role name means different things on
    different blocks (``actions`` is an inline literal on ``actionBar`` and a rooted
    field path on ``runPanel``), so a name-keyed lookup produces false positives.

    ``None`` means "not classified", which is the SAFE answer: a caller must treat an
    unclassified role as unconstrained rather than guessing. Coverage is deliberately
    partial (285 of ~651 pairs) and under-coverage costs only a missing hint."""
    return _load()[2].get(block, {}).get(role)


def role_enums_for(block: str) -> dict[str, list[str]]:
    """Role-level ENUM values for ``block`` — the ``roleKinds`` pairs typed
    ``enum`` (16 pairs on 10 blocks today, all charts: ``trendChart.mode`` →
    ``['bars','line','area']``). Distinct from KNOB enums, which ``BlockDef``
    carries and the gate refuses on: a wrong role enum only draws the default
    mode via a non-blocking ``design_lint`` note, which is exactly why the
    values must be TAUGHT — nothing louder will ever correct them."""
    per = _load()[2].get(block) or {}
    return {
        role: list(k["values"])
        for role, k in per.items()
        if isinstance(k, dict) and k.get("kind") == "enum" and k.get("values")
    }


def afforded_for(block: str) -> frozenset[str]:
    """The spark GESTURES a block affords (Spark §13.2) — the set a spark `on:`
    discriminator may name when anchored to this block. Empty for an unknown
    block or one that affords no gesture (so any `on:` on it is rejected). Read
    by `app.spreads.spark.validate.spark_spec` over the one sanctioned sideways edge."""
    d = _load()[0].get(block)
    return frozenset(d.get("afforded", ())) if d else frozenset()


def nests_for(block: str) -> dict | None:
    """How this block holds a sub-document — ``{role, per?}`` — or None if it holds
    none. ``per == 'record'`` means the child is stamped once per row of the block's
    own list, so its roles bind ``$item.…`` rather than the root.

    The read side of ``defs.ts::nests``. It exists so an agent can be TOLD which
    blocks compose: the frontend gate is structural (a role value that is a list of
    ``{block: …}`` dicts is a sub-document, wherever it appears), which is right for
    validation and says nothing to whoever is choosing a block."""
    d = _load()[0].get(block)
    return d.get("nests") if d else None
