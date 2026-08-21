"""Shared dough-id helpers — identity, validation, and path mapping.

All dough-id manipulation lives here so the rules can't drift: bare-id
extraction, slug derivation, well-formedness validation, the reserved-root
set, and the id ↔ on-disk-path mapping. The validator, the store, the baker,
and the creator all import from here.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.doughs.validation.rules import (
    custom_prefix,
    custom_root,
    MAX_DEPTH,
    is_valid_segment,
)
from app.utils import idpath

if TYPE_CHECKING:
    from pathlib import Path

    from app.doughs.definitions.service import DoughStore


def bare_dough_path(dough_ref: str) -> str:
    """Last segment of a dot-form id.

    ``a.b.c.z`` → ``z``; ``z`` → unchanged. Empty/None refs round-trip
    through unchanged.
    """
    return dough_ref.split(".")[-1] if dough_ref else dough_ref


def last_dough_id_in_steps(do_steps: list[dict[str, Any]]) -> str | None:
    """Bare id of the last ``dough:`` step in an iteration body (``each:`` /
    ``all:`` ``do:`` block).

    Returns None if no ``dough:`` step exists. Used to compute the
    auto-published list name when an ``each:`` / ``all:`` block strips its
    legacy ``save:`` field.
    """
    for raw in reversed(do_steps):
        if isinstance(raw, dict) and isinstance(raw.get("dough"), str):
            return bare_dough_path(raw["dough"])
    return None


def slugify_dough_path(name: str) -> str:
    """Derive a custom-dough slug from a display name.

    Lowercases, collapses whitespace to `_`, drops everything outside
    [a-z0-9_], and trims to 50 chars. Returns '' if nothing usable remains.
    Hyphens are dropped (our segment grammar excludes them).
    """
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return s[:50]


# Reserved roots that are NOT contributed by a kit. The full reserved set is
# the union of these plus the first segment of every loaded kit's emit path
# (see `reserved_top_levels`).
def _non_kit_reserved_roots() -> frozenset[str]:
    """Reserved roots no kit contributes.

    The author root is per-profile now (`custom_root()`), so this cannot be a
    module-level frozenset — one built at import would pin whichever profile was
    active first and then reject the real owner's own doughs.
    """
    return frozenset({custom_root()})


# Bundled kit FAMILIES are reserved statically, not only once their wave has
# loaded. Kits install in topo order, and a dough walk during startup (e.g.
# `GET /api/v1/kits` firing before the last wave finishes) must not reject a
# bundled kit's doughs for a load-timing reason.
#
# ★ THE INVARIANT IS "EVERY BUNDLED KIT'S INSTALL ROOT", and it is pinned by
# `tests/e2e/test_bundled_family_roots.py` rather than by the comment that used
# to sit here. That comment said "mirrors VENDOR_BUNDLED_ONLY; keep the two in
# sync" and nobody did: `utilities` was in that set and not in this one, so all
# four `utilities.image.*` doughs were rejected at load with "top-level
# 'utilities' is not a reserved root" whenever the walk beat the kit's wave.
#
# It was never only `utilities`. Measured when it was found: 23 bundled install
# roots against 8 reserved here — the other 14 (`naver`, `agoda`, `trip_com`, …)
# were one load-order shuffle away from the identical failure. `delivery`
# DEFAULTS to "bundled", so a new top-level kit joins this list by existing,
# which is exactly why a hand-kept list drifts and a test is the fix.
#
# Not derived at import: this module is imported on hot paths and the derivation
# is a walk of every `kit.yaml`. Explicit set + a test that recomputes it.
_BUNDLED_FAMILY_ROOTS = frozenset({
    # Floor + system families.
    "basic", "advanced", "thinking", "webengine", "manual", "taste",
    "postlab", "utilities",
})


def reserved_top_levels() -> frozenset[str]:
    """Compute the set of reserved dough-id top-level segments.

    For each loaded kit, the FIRST segment of its emit path is reserved.
    `postlab.kakaotalk` → `kakaotalk/` → reserves `kakaotalk`. Resolved on
    every call so newly-loaded kits are picked up without a process restart.
    The one non-kit root is the profile's author handle (`custom_root()`);
    bundled families (`_BUNDLED_FAMILY_ROOTS`) are reserved unconditionally so a
    mid-startup walk never rejects a not-yet-loaded bundled kit's doughs.
    """
    from app.kits.loading.loader import get_loaded_kits
    from app.kits.loading.paths import kit_id_to_install_path

    kit_roots: set[str] = set()
    for kit_id in get_loaded_kits():
        try:
            install_path = kit_id_to_install_path(kit_id)
        except ValueError:
            continue
        kit_roots.add(install_path.split("/", 1)[0])
    return _non_kit_reserved_roots() | _BUNDLED_FAMILY_ROOTS | frozenset(kit_roots)


def validate_dough_path(dough_path: str) -> str | None:
    """Return an error message if dough_path is not well-formed, else None.

    Canonical dough ids are dot-joined lowercase segments that mirror the
    on-disk path 1:1 (``.`` ↔ ``/``) for *every* class — custom ids included
    (``<handle>.work.triage`` ↔ ``doughs/<handle>/work/triage``). Depth is
    capped at ``MAX_DEPTH``. The first segment MUST be a reserved top-level
    (see `reserved_top_levels`) — for an authored dough that is the profile's
    own handle, which is why the set is resolved per call and not at import.
    """
    if not dough_path:
        return "dough id cannot be empty"
    segments = [s for s in dough_path.split(".") if s]
    if not segments or len(segments) > MAX_DEPTH:
        return f"'{dough_path}' has an invalid depth"
    for seg in segments:
        if not is_valid_segment(seg):
            return (
                f"segment '{seg}' in '{dough_path}' is not well-formed: use "
                f"lowercase letters, digits, and underscore only (1-50 chars)"
            )
        if idpath.is_uid_shaped(seg):
            return (
                f"segment '{seg}' in '{dough_path}' has the reserved uid shape "
                f"(do-/sp- + 32 hex) — a path segment may not be uid-shaped, or a "
                f"scoped id `<handle>.<uid>` could not be told from a path"
            )
    reserved = reserved_top_levels()
    if segments[0] not in reserved:
        return (
            f"top-level '{segments[0]}' is not a reserved root "
            f"(expected one of {sorted(reserved)})"
        )
    return None


def prepare_unique_dough_path(
    store: "DoughStore",
    name: str,
    *,
    current_path_id: str | None = None,
    folder: str | None = None,
) -> tuple[str, str | None]:
    """Compose a canonical custom dough id from ``name`` + ``folder``,
    auto-suffix on a same-path collision.

    Now that a custom dough's id IS its folder path, the id is composed from
    the target ``folder`` (slash- or dot-form, rooted at the profile's handle)
    plus the slugified leaf: ``folder='<handle>/work'`` + ``name='Triage'`` →
    ``<handle>.work.triage``. The folder defaults to ``custom_root()`` when
    omitted, and is prefixed with it if a bare relative folder is passed.

    Returns ``(dough_path, error)``. Error is non-None only when ``name`` has no
    slug-safe characters or composes to an invalid id. Collisions do not error
    — the function appends ``_2``, ``_3``, … to the LEAF until it finds a free
    id. ``current_path_id`` is excluded from the uniqueness check so renaming
    back to the original slug is allowed.
    """
    slug = slugify_dough_path(name)
    if not slug:
        return "", (
            f"name '{name}' has no slug-safe characters. "
            f"Use lowercase letters, digits, and underscores."
        )
    norm_folder = (folder or custom_root()).replace("/", ".").strip(".")
    if not norm_folder:
        norm_folder = custom_root()
    if norm_folder.split(".")[0] != custom_root():
        norm_folder = f"{custom_root()}.{norm_folder}"
    base = f"{norm_folder}.{slug}"
    id_err = validate_dough_path(base)
    if id_err:
        return "", f"cannot derive a valid id from '{name}': {id_err}"
    candidate = base
    counter = 2
    while candidate != current_path_id and store.dough_exists(candidate):
        candidate = f"{norm_folder}.{slug}_{counter}"
        counter += 1
        if counter > 999:
            return "", f"too many collisions for '{name}'"
    return candidate, None


# The `path IS the id` mapping is shared with the view and type trees.
id_from_path = idpath.id_from_path
path_from_id = idpath.path_from_id


def resolve_dough_dir(
    doughs_dir: "Path", dough_path: str, overlay_root: "Path | None" = None,
) -> "Path":
    """Where a dough's directory IS, given an optional session tray to look in first.

    ★ THE OVERLAY IS WHAT MAKES A DRAFT BAKEABLE, which is what makes NESTING
    work. A dough being authored lives on its session's tray, not in the served
    tree; without a second root it could not resolve, so it could not bake — and
    a parent draft could never be proved, because proving it means running its
    child drafts too. Publishing before proving was the alternative, and it
    inverts the order: it ships the whole set to the library on the strength of
    no evidence.

    ★ PRECEDENCE IS DRAFT-OVER-PUBLISHED, and only for the AUTHOR root. Kit ids never
    consult the overlay — nothing authors into a kit namespace, so letting a tray
    shadow a kit namespace would buy nothing and risk everything. Within it
    the only way both can exist is that the agent is EDITING a published dough,
    and there the draft is exactly what the caller means.

    ★ THE OVERLAY IS RESOLUTION-ONLY, never discovery. Listing and search walk
    ``doughs_dir`` directly and so never see a tray — which is what keeps a
    half-written dough out of the user's library while still letting the agent
    bake it by id.

    An absent ``overlay_root``, or an id with no draft behind it, falls through
    to the served tree, so every non-chat caller (the run panel, staff, memo
    atoms) behaves exactly as it did before this existed.

    ★ THIS ANSWERS A READ QUESTION, AND IT CANNOT CREATE. The existence check is
    what makes precedence meaningful — given an id that may live in two places,
    which one does the caller mean — but it means a dough being CREATED, which
    is in neither place, always resolves to the served tree. Routing a create
    through here (``DoughStore(overlay_root=…).save_dough`` on a fresh id)
    therefore publishes silently while reading as drafting; it cost the whole
    tray-drafting feature once, because ``finalize`` then refuses the id forever
    with "is not on this session's tray". Writing a draft is
    ``definitions/draft.py::write_draft``, which takes the tray as a destination
    rather than asking for one — and deliberately does NOT go through
    ``save_dough``, whose trailing discovery/doc2query/cloud-push acts all
    belong to the library. Pinned by ``tests/web/test_use_is_the_proof.py``.
    """
    # A uid ref resolves by IDENTITY, not path — the durable uid an inner dough is
    # referenced by, so a rename or move of the child never breaks the parent that
    # calls it. The uid is looked up whole. Tray first (a co-drafted child), then
    # the served tree's cached index. A uid never collides with a path id: no path
    # segment is uid-shaped (grammar reservation).
    parsed = idpath.parse_scoped(dough_path)
    if (parsed and parsed[1].startswith("do-")) or dough_path.startswith("do-"):
        if overlay_root is not None:
            # The overlay IS the tray; doughs live under its `doughs/` sibling
            # (the spread loader appends `spreads/` the same way).
            hit = _find_uid_dir(overlay_root / "doughs", dough_path)
            if hit is not None:
                return hit
        from app.doughs.definitions.identity import resolve_uid
        ref = resolve_uid(doughs_dir, dough_path)
        if ref is not None and ref.kind == "dough":
            return ref.dir
        # A uid that resolves nowhere returns a path that does not exist, so the
        # caller's missing-dough handling fires exactly as for a bad path id.
        return doughs_dir / dough_path

    if overlay_root is not None and dough_path.startswith(custom_prefix()):
        candidate = (overlay_root / "doughs").joinpath(*path_from_id(dough_path))
        if (candidate / "dough.yaml").is_file():
            return candidate
    return doughs_dir.joinpath(*path_from_id(dough_path))


def _find_uid_dir(root: "Path", uid: str) -> "Path | None":
    """Scan ``root`` for the dough.yaml carrying ``uid`` — the tray lookup a uid
    ref needs (the served tree uses the cached identity index instead). A tray
    holds a handful of drafts, so the walk is cheap, and nothing caches it: a
    draft's uid can be minted between two resolves."""
    if not root.is_dir():
        return None
    from app.doughs.definitions.identity import read_uid
    for p in root.rglob("dough.yaml"):
        try:
            if read_uid(p) == uid:
                return p.parent
        except OSError:
            continue
    return None
