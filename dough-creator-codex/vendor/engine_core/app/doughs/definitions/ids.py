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
    CUSTOM_ROOT_FOLDER,
    MAX_DEPTH,
    WEB_DOUGHS_ROOT,
    is_valid_segment,
)

if TYPE_CHECKING:
    from app.doughs.definitions.service import DoughStore


def bare_dough_id(dough_ref: str) -> str:
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
            return bare_dough_id(raw["dough"])
    return None


def slugify_dough_id(name: str) -> str:
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
#
# `user` is the custom-dough root (no kit ships it). `web` is the web-dough
# emit root — web doughs come from `web_recorder` / `web_sprint`, not a kit.
_NON_KIT_RESERVED_ROOTS = frozenset({
    CUSTOM_ROOT_FOLDER,
    WEB_DOUGHS_ROOT,
})


# Bundled kit FAMILIES are reserved statically, not only once their wave has
# loaded. Kits install in topo order, and a dough walk during startup (e.g.
# `GET /api/v1/kits` firing before the last wave finishes) must not reject a
# bundled kit's doughs for a load-timing reason. Mirrors the family roots in
# `app.kits.manifest.manifest.VENDOR_BUNDLED_ONLY`; keep the two in sync.
_BUNDLED_FAMILY_ROOTS = frozenset({
    "postlab", "advanced", "basic", "thinking", "mcpkits", "webengine",
})


def reserved_top_levels() -> frozenset[str]:
    """Compute the set of reserved dough-id top-level segments.

    For each loaded kit, the FIRST segment of its emit path is reserved.
    `postlab.kakaotalk` → `kakaotalk/` → reserves `kakaotalk`. Resolved on
    every call so newly-loaded kits are picked up without a process restart.
    Non-kit roots are `user` (custom doughs) and `web` (web dough emit root);
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
    return _NON_KIT_RESERVED_ROOTS | _BUNDLED_FAMILY_ROOTS | frozenset(kit_roots)


def validate_dough_id(dough_id: str) -> str | None:
    """Return an error message if dough_id is not well-formed, else None.

    Canonical dough ids are dot-joined lowercase segments that mirror the
    on-disk path 1:1 (``.`` ↔ ``/``) for *every* class — custom ids included
    (``user.work.triage`` ↔ ``doughs/user/work/triage``). Every segment
    matches [a-z0-9_]; depth (segment count) is capped at ``MAX_DEPTH``. The
    first segment MUST be a reserved top-level (see `reserved_top_levels`) —
    for custom doughs that root is always ``user``.
    """
    if not dough_id:
        return "dough id cannot be empty"
    segments = [s for s in dough_id.split(".") if s]
    if not segments or len(segments) > MAX_DEPTH:
        return f"'{dough_id}' has an invalid depth"
    for seg in segments:
        if not is_valid_segment(seg):
            return (
                f"segment '{seg}' in '{dough_id}' is not well-formed: use "
                f"lowercase letters, digits, and underscore only (1-50 chars)"
            )
    reserved = reserved_top_levels()
    if segments[0] not in reserved:
        return (
            f"top-level '{segments[0]}' is not a reserved root "
            f"(expected one of {sorted(reserved)})"
        )
    return None


def prepare_unique_dough_id(
    store: "DoughStore",
    name: str,
    *,
    current_path_id: str | None = None,
    folder: str | None = None,
) -> tuple[str, str | None]:
    """Compose a canonical custom dough id from ``name`` + ``folder``,
    auto-suffix on a same-path collision.

    Now that a custom dough's id IS its folder path, the id is composed from
    the target ``folder`` (slash- or dot-form, rooted at ``user``) plus the
    slugified leaf: ``folder='user/work'`` + ``name='Triage'`` →
    ``user.work.triage``. The folder defaults to the custom root (``user``)
    when omitted, and is prefixed with ``user.`` if a bare relative folder is
    passed.

    Returns ``(dough_id, error)``. Error is non-None only when ``name`` has no
    slug-safe characters or composes to an invalid id. Collisions do not error
    — the function appends ``_2``, ``_3``, … to the LEAF until it finds a free
    id. ``current_path_id`` is excluded from the uniqueness check so renaming
    back to the original slug is allowed.
    """
    slug = slugify_dough_id(name)
    if not slug:
        return "", (
            f"name '{name}' has no slug-safe characters. "
            f"Use lowercase letters, digits, and underscores."
        )
    norm_folder = (folder or CUSTOM_ROOT_FOLDER).replace("/", ".").strip(".")
    if not norm_folder:
        norm_folder = CUSTOM_ROOT_FOLDER
    if norm_folder.split(".")[0] != CUSTOM_ROOT_FOLDER:
        norm_folder = f"{CUSTOM_ROOT_FOLDER}.{norm_folder}"
    base = f"{norm_folder}.{slug}"
    id_err = validate_dough_id(base)
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


def id_from_path(rel_path: str) -> str:
    """Convert a disk-relative path under `doughs/` to the canonical dot-form id.

    One uniform mapping for every class: join every path segment with `.`.
    ``user/work/triage`` → ``user.work.triage``;
    ``google/gmail/search`` → ``google.gmail.search``.
    """
    segments = [s for s in rel_path.replace("\\", "/").split("/") if s]
    if not segments:
        return ""
    return ".".join(segments)


def path_from_id(dough_id: str) -> tuple[str, ...]:
    """Convert a canonical dot-form id to disk path segments.

    One uniform mapping for every class: split on `.`. The id IS the path, so
    ``user.work.triage`` → ``(user, work, triage)``.
    """
    return tuple(dough_id.split("."))
