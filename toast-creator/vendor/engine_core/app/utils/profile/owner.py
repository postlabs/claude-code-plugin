"""Vendored stub (sync_engine_core.py — do not edit).

``Dough.folder`` defaults to the signed-in account's handle, which the
real module reads out of the active profile on disk — through the
logger and the settings, the two things this slice exists to avoid.
Validation never reads the value back (``folder`` is re-derived from
the path at load and is not persisted), so offline it only has to be
a string.
"""

from __future__ import annotations


def active_handle() -> str:
    """The placeholder authoring root used when no profile is present."""
    return "user"
