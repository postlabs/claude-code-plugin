"""Constants and id-shape predicates for the dough engine.

Step-shape constraints (FORBIDDEN_STEP_KEYS, ALLOWED_STEP_KEYS,
FORBIDDEN_FIELDS, FORBIDDEN_PRE_PARSE_KEYS, MODEL_REQUIRED_TYPES) are
consumed by validation.py. Id-shape predicates (is_custom, is_fixed,
is_kit_dough) are consumed by validation.py + store.py
to route doughs by class.

Note: ``is_custom`` is now a PERMISSIONS / reserved-root predicate only (who
may edit a dough + the reserved 'user' root), NOT a path-resolution signal —
custom ids mirror their on-disk path 1:1 like fixed ids (the id IS the path).
``custom_root()`` resolves the reserved author root per profile.

The constraint catalogue these enforce is mirrored in prose for the agent in
``kits/thinking/guide_build/dough.yaml`` (the build guide the OVEN agent fetches
when authoring), section "Composition rules".
"""

from __future__ import annotations

import re

from app.utils import idpath

FORBIDDEN_STEP_KEYS: frozenset[str] = frozenset({"tool", "llm", "web", "agent"})
ALLOWED_STEP_KEYS: frozenset[str] = frozenset({"dough", "each", "all"})
FORBIDDEN_FIELDS: frozenset[str] = frozenset({"save", "when", "on_error"})

FORBIDDEN_PRE_PARSE_KEYS: dict[str, str] = {
    "id": (
        "a dough's id IS its `path:` — one key, not two. Every other species "
        "(kit, jar, basket, spread) is `extra='forbid'`, so a stale `id:` fails "
        "their parse loudly; Dough is `extra='allow'`, which made it the one "
        "place a dangling id could ride along being read by nothing."
    ),
    "kind": (
        "kind is inferred from shape. Presence of `action:` means flour; "
        "presence of `steps:` means dough. The two are mutually exclusive."
    ),
    "triggers": (
        "triggers do not live on dough.yaml — the model absorbs the key "
        "silently and it never wires anything. Put the trigger phrasings in the "
        "`search.yaml` sidecar (top-level `en:`/`ko:` lists) instead."
    ),
    "default_view": (
        "the view species is gone — a dough designates a SPREAD. Rename the "
        "key to `default_spread:`; the id it points at is unchanged. Refused "
        "rather than absorbed because the model is `extra='allow'`, so a stale "
        "key would parse clean and the card would quietly stop painting."
    ),
}
"""Shape-inferred YAML keys rejected before Pydantic parses. Dict values
are consumed verbatim as ``ValidationIssue.hint`` — extend cautiously."""

MODEL_REQUIRED_TYPES: frozenset[str] = frozenset({"object", "list"})

def custom_root() -> str:
    """The folder a person's own doughs are rooted at — their account handle.

    Was the constant ``"user"``. It is now per-profile
    (``{profile}/owner.yaml``), so it must be CALLED, never imported as a value:
    ``from … import CUSTOM_ROOT_FOLDER`` binds once at import and would pin
    whichever profile happened to be active first.

    ``local`` when no account has signed in — a disposable root, wiped rather
    than migrated.
    """
    from app.utils.profile.owner import active_handle

    return active_handle()


def custom_prefix() -> str:
    """``custom_root()`` as an id prefix — ``junkwon@gmail_com.``"""
    return custom_root() + "."

# Max nesting depth — applied to both dough-id segment count and folder paths.
# Prevents pathological paths from breaking UI indent / filesystem limits.
MAX_DEPTH = 10

# The grammar lives in `app.utils.idpath` — shared with the KIT id validator,
# because a kit id segment and a dough id segment are the same directory name.
SEGMENT_GRAMMAR_HINT = idpath.SEGMENT_GRAMMAR
is_valid_segment = idpath.is_valid_segment


# ── Id-shape predicates (pure string ops; no disk I/O) ──

def is_custom(dough_path: str) -> bool:
    """True if the id denotes a custom (author-rooted) dough."""
    return dough_path.startswith(custom_prefix())


def is_fixed(dough_path: str) -> bool:
    """True if the id denotes a fixed (path-encoded) dough."""
    return bool(dough_path) and not is_custom(dough_path)


def is_kit_dough(dough_path: str) -> bool:
    """True if the id denotes a kit-shipped flour or dough.

    The exact complement of :func:`is_custom`: a dough is either rooted at the
    account that owns the profile or shipped by a kit. There is no third class.
    """
    return is_fixed(dough_path)
