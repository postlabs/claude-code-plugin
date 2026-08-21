"""The decision: ``can`` (bool) and ``authorize`` (explained) — stdlib only.

``can`` is the whole rule: ``tier >= REQUIRES[cap]``. ``authorize`` wraps it in
a :class:`Decision` carrying a human ``reason`` and an actionable ``hint`` so a
denial explains itself. The call-site still emits its own ``ValidationCode`` /
exception; the leaf only decides allow/deny + why.
"""

from __future__ import annotations

from dataclasses import dataclass

from .capabilities import REQUIRES
from .tier import AuthorTier

__all__ = ["Decision", "can", "authorize"]


# Per-capability deny hint. Kept terse — call-sites that already own a richer
# message (e.g. checks.py) keep theirs; this is the fallback explanation.
_DENY_HINT: dict[str, str] = {
    "author_tool_flour": (
        "tool flours are kit-shipped only — author `action: agent:` reasoning, "
        "or compose a shipped flour via `- dough: <kit_flour_id>`."
    ),
    "author_tool": "tools are Python symbols shipped by a kit, not user-authored.",
    "author_kit": "authoring a kit requires kit-author trust.",
    "save_fixed": "users can only save custom (user.*) artifacts.",
    "publish_kit": "publishing a kit requires kit-author trust.",
    "use_reserved_vendor": (
        "this vendor segment is reserved for bundled kits; an unsigned kit "
        "cannot claim it."
    ),
    "sign": "signing requires the official tier.",
}


@dataclass(frozen=True)
class Decision:
    """Outcome of an authorization check.

    allow: whether the principal may perform the capability.
    reason: human-readable why (always set).
    hint: actionable next step (empty string when allowed / none applies).
    """

    allow: bool
    reason: str
    hint: str = ""


def can(tier: AuthorTier, capability: str) -> bool:
    """True iff ``tier`` meets the minimum tier required for ``capability``.

    Raises ``KeyError`` for an unknown capability — an undeclared capability is
    a programming error, never a silent allow.
    """

    return tier >= REQUIRES[capability]


def authorize(principal_tier: AuthorTier, capability: str) -> Decision:
    """Decide whether ``principal_tier`` may perform ``capability``."""

    required = REQUIRES[capability]  # KeyError on unknown capability (by design)
    if can(principal_tier, capability):
        return Decision(
            allow=True,
            reason=f"{principal_tier.name} satisfies '{capability}' (>= {required.name})",
        )
    return Decision(
        allow=False,
        reason=(
            f"'{capability}' requires {required.name}; "
            f"principal is {principal_tier.name}"
        ),
        hint=_DENY_HINT.get(capability, ""),
    )
