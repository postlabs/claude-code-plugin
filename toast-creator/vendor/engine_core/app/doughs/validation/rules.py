"""Constants and id-shape predicates for the dough engine.

Step-shape constraints (FORBIDDEN_STEP_KEYS, ALLOWED_STEP_KEYS,
FORBIDDEN_FIELDS, FORBIDDEN_PRE_PARSE_KEYS, MODEL_REQUIRED_TYPES) are
consumed by validation.py. Id-shape predicates (is_custom, is_fixed,
is_web_dough, is_kit_dough) are consumed by validation.py + store.py
to route doughs by class.

Note: ``is_custom`` is now a PERMISSIONS / reserved-root predicate only (who
may edit a dough + the reserved 'user' root), NOT a path-resolution signal —
custom ids mirror their on-disk path 1:1 like fixed ids (the id IS the path).
``CUSTOM_ROOT_FOLDER`` stays the reserved custom root.

The constraint catalogue these enforce is mirrored in prose for the agent in
``kits/thinking/guide_build/dough.yaml`` (the build guide the OVEN agent fetches
when authoring), section "Composition rules".
"""

from __future__ import annotations

import re

FORBIDDEN_STEP_KEYS: frozenset[str] = frozenset({"tool", "llm", "web", "agent"})
ALLOWED_STEP_KEYS: frozenset[str] = frozenset({"dough", "each", "all"})
FORBIDDEN_FIELDS: frozenset[str] = frozenset({"save", "when", "on_error"})

FORBIDDEN_PRE_PARSE_KEYS: dict[str, str] = {
    "kind": (
        "kind is inferred from shape. Presence of `action:` means flour; "
        "presence of `steps:` means dough. The two are mutually exclusive."
    ),
}
"""Shape-inferred YAML keys rejected before Pydantic parses. Dict values
are consumed verbatim as ``ValidationIssue.hint`` — extend cautiously."""

MODEL_REQUIRED_TYPES: frozenset[str] = frozenset({"object", "list"})

CLASS_USER_PREFIX = "user."
CUSTOM_ROOT_FOLDER = "user"
WEB_DOUGHS_ROOT = "web"

# Max nesting depth — applied to both dough-id segment count and folder paths.
# Prevents pathological paths from breaking UI indent / filesystem limits.
MAX_DEPTH = 10

# Human-readable hint paired with ``_SEGMENT_RE`` — kept next to the
# regex so the two move together when the grammar changes.
SEGMENT_GRAMMAR_HINT = "[a-z0-9_]{1,50}"
_SEGMENT_RE = re.compile(rf"^{SEGMENT_GRAMMAR_HINT}$")


def is_valid_segment(seg: str) -> bool:
    """True if ``seg`` matches the segment grammar (lowercase [a-z0-9_], 1–50 chars)."""
    return bool(_SEGMENT_RE.match(seg))


# ── Id-shape predicates (pure string ops; no disk I/O) ──

def is_custom(dough_id: str) -> bool:
    """True if the id denotes a custom (user-root) dough."""
    return dough_id.startswith(CLASS_USER_PREFIX)


def is_fixed(dough_id: str) -> bool:
    """True if the id denotes a fixed (path-encoded) dough."""
    return bool(dough_id) and not is_custom(dough_id)


def is_web_dough(dough_id: str) -> bool:
    """True if the id denotes a web-automation dough (``web.<site>.<action>``)."""
    return dough_id.startswith("web.")


def is_kit_dough(dough_id: str) -> bool:
    """True if the id denotes a kit-shipped flour or dough (fixed and not web)."""
    return is_fixed(dough_id) and not is_web_dough(dough_id)
