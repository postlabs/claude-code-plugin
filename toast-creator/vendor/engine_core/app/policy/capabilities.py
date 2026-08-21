"""Capability -> minimum required tier — declarative data, stdlib only.

Adding a capability is one row. Additivity is enforced by the type: each
capability names the *minimum* tier that may perform it, and
``can(tier, cap) == tier >= REQUIRES[cap]``. A matrix of ``(tier × op)`` cells
is the wrong shape — it could express an additivity violation ("USER allow,
THIRD_PARTY deny"); a minimum-tier map cannot.

v1 scope: only the USER-tier capabilities are actually reached by relocated
call-sites. THIRD_PARTY / OFFICIAL rows exist as the seam for catalog kits and
signing; they are declared but unreachable until that infra lands.
"""

from __future__ import annotations

from .tier import AuthorTier

__all__ = ["REQUIRES", "CAPABILITIES"]

USER = AuthorTier.USER
THIRD_PARTY = AuthorTier.THIRD_PARTY
OFFICIAL = AuthorTier.OFFICIAL

# capability -> minimum AuthorTier permitted to perform it.
REQUIRES: dict[str, AuthorTier] = {
    # --- USER: allow-by-default authoring the local user owns ---
    "author_agent_flour": USER,   # <handle>.* flour wrapping `action: agent:`
    "author_composition": USER,   # <handle>.* dough (steps:)
    "save_custom": USER,          # persist a <handle>.* artifact
    "publish_dough": USER,        # share a custom dough to the catalog
    # --- THIRD_PARTY: needs a kit (Python the user didn't write) ---
    "author_tool_flour": THIRD_PARTY,  # flour wrapping `action: tool:`
    "author_tool": THIRD_PARTY,        # ship a Python tool symbol
    "author_kit": THIRD_PARTY,         # author a kit manifest
    "save_fixed": THIRD_PARTY,         # persist a non-custom (kit) artifact
    "publish_kit": THIRD_PARTY,        # publish a kit
    # --- OFFICIAL: reserved-vendor + signing (v1 unreachable) ---
    "use_reserved_vendor": OFFICIAL,   # claim a VENDOR_BUNDLED_ONLY segment
    "sign": OFFICIAL,                  # sign an artifact
}

# Frozen view of the declared capability keys (stable iteration for tests/UI).
CAPABILITIES: frozenset[str] = frozenset(REQUIRES)
