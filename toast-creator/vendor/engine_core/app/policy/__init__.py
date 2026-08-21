"""Authoring policy — the pure leaf (capability × tier authorization).

Import directly from the submodules (no barrel re-export):

    from app.policy.tier import AuthorTier, ArtifactDescriptor, derive_tier
    from app.policy.capabilities import CAPABILITIES, REQUIRES
    from app.policy.decide import Decision, authorize, can

Surface:

    AuthorTier          ordered tiers USER < THIRD_PARTY < OFFICIAL  (tier)
    ArtifactDescriptor  minimal disk-derivable facts the rules consult (tier)
    derive_tier         descriptor -> AuthorTier  (tier)
    REQUIRES            capability -> minimum tier (declarative data) (capabilities)
    CAPABILITIES        frozenset of declared capability keys (capabilities)
    can                 tier >= REQUIRES[cap]  (the whole rule) (decide)
    authorize           explained decision (allow/reason/hint) (decide)
    Decision            authorize result (decide)

Dependency rule: this package imports stdlib ONLY. Engine packages
(``doughs`` / ``kits`` / ``sharing``) import *this*, never the reverse.
"""
