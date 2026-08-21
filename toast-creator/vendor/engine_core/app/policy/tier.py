"""Author tiers and the artifact descriptor — pure leaf, stdlib only.

This module is the *input side* of the authoring policy: the ordered trust
tiers and the minimal bag of facts (an :class:`ArtifactDescriptor`) the
relocated authoring rules need to reach a decision.

Hard rule (see ``docs_sh/authoring_policy/02-architecture.md``): this package
imports **only stdlib**. No ``app.doughs`` / ``app.kits`` / engine imports.
Call-sites import directly from the submodules (``app.policy.tier`` /
``capabilities`` / ``decide``); never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

__all__ = ["AuthorTier", "ArtifactDescriptor", "derive_tier"]


class AuthorTier(IntEnum):
    """Additive trust tiers, ordered ``USER < THIRD_PARTY < OFFICIAL``.

    Additivity is baked into the ordering: a higher tier can do everything a
    lower tier can, plus more. Capabilities map to a *minimum* required tier
    (see :mod:`app.policy.capabilities`), so ``tier >= REQUIRES[cap]`` is the
    whole decision. ``IntEnum`` makes the comparison a plain integer compare.
    """

    USER = 0
    THIRD_PARTY = 1
    OFFICIAL = 2


@dataclass(frozen=True)
class ArtifactDescriptor:
    """The minimal, disk-derivable facts :func:`derive_tier` consults.

    Deliberately *not* a dough/kit model — it carries only the facts the leaf
    needs, so the policy never has to import (or know) the engine models.
    Call-sites at the boundary build one of these from whatever they hold (a
    ``Dough``, a kit manifest, an id string).

    Fields:
        id_is_custom: id is ``<handle>.*`` (the custom / user-owned class).
        kit_is_bundled: the kit actually ships bundled in the binary — the
            OFFICIAL signal for :func:`derive_tier` (``official ≡ bundled`` in
            v1; a signature check is added here when catalog kit-publish lands).
    """

    id_is_custom: bool = False
    kit_is_bundled: bool = False


def derive_tier(descriptor: ArtifactDescriptor) -> AuthorTier:
    """Compute the author tier from disk-derivable facts — never stored.

    Order matters (first match wins):

    - ``id_is_custom`` (``<handle>.*``)                 -> ``USER``
    - ``kit_is_bundled`` (ships in the binary)       -> ``OFFICIAL`` (official ≡ bundled)
    - otherwise (a non-custom, non-bundled artifact) -> ``THIRD_PARTY``

    The signing path (a future ``OFFICIAL`` branch for a verified non-bundled
    kit) is added here when catalog kit-publish lands.
    """

    if descriptor.id_is_custom:
        return AuthorTier.USER
    if descriptor.kit_is_bundled:
        return AuthorTier.OFFICIAL
    return AuthorTier.THIRD_PARTY
