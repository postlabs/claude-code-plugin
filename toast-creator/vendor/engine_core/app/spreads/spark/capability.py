"""The capability INDEX — which block KINDS hold which structural capability.

A capability is a property of the block KIND, not of a role an author binds —
no role can add one. The four keys are all DERIVED from the tables the gates
already read, so a kind gaining a capability joins every teaching payload and
every refusal's legal set with no edit here:

- ``rowPress``       — ``anchor._DESCENT`` (via ``anchorable_kinds``): the
                       compiler emits one pressable node per record, so the
                       block can carry ``on: {press|contextmenu: …}``
- ``readHost``       — ``'readTrigger' ∈ catalog.roles_for``: the block can
                       carry the refresh/load-more footer a ``read`` stamps
- ``control``        — ``CONTROL_BLOCKS``: a ``$control.<name>`` param can
                       read it (declared, not derived — see ``_NOT_WIRED`` in
                       ``app/spreads/viewops.py`` for why)
- ``nestsPerRecord`` — ``catalog.nests_for(k)['per'] == 'record'``: it stamps
                       an authored sub-document once per record

Consumed by ``GET /oven/blocks`` (the teaching side — ``app/oven/api.py``, the
one consumer that already imports both the kernel and this package, so the
kernel's ``block_guide`` never has to import upward) and by the capability
refusals in ``validate.py`` (the gate side). One source, both directions —
the split that produced the "gate knew, guide withheld" class is gone.
"""

from __future__ import annotations

from app.spreads import catalog, viewops
from app.spreads.spark import anchor

# The keystone note — stated ONCE at the payload root, it makes every
# present-only capability key self-describing, including ones added later.
CAPABILITY_NOTE = (
    "A CAPABILITY is a property of the block KIND, not of a role you bind — "
    "no role can add one. `rowPress`: the block renders one pressable node per "
    "record, so it can carry a per-row trigger — `on: {press|contextmenu: "
    "{act|nav|open: …}}` declared on the block itself. `readHost`: it "
    "can carry the refresh/load-more footer a `read` stamps. `control`: a "
    "`$control.<name>` param can read it. `nestsPerRecord`: it stamps an "
    "authored sub-document once per record. A block whose capability key is "
    "absent does not hold that capability, and anchoring there is refused."
)


def hosts_for(key: str) -> tuple[str, ...]:
    """The block kinds holding capability ``key`` — sorted, derived, never
    hand-listed. Unknown key → empty (a caller must not invent capabilities)."""
    if key == "rowPress":
        return anchor.anchorable_kinds()
    if key == "readHost":
        return tuple(sorted(
            k for k in catalog.block_kinds()
            if "readTrigger" in catalog.roles_for(k)
        ))
    if key == "control":
        return tuple(sorted(viewops.CONTROL_BLOCKS))
    if key == "nestsPerRecord":
        return tuple(sorted(
            k for k in catalog.block_kinds()
            if (catalog.nests_for(k) or {}).get("per") == "record"
        ))
    return ()


CAPABILITY_KEYS: tuple[str, ...] = (
    "rowPress", "readHost", "control", "nestsPerRecord",
)


def capability_index() -> dict[str, list[str]]:
    """capability → its hosts, the REVERSE index the payload root carries —
    O(4) to read against O(131) per-block scanning."""
    return {key: list(hosts_for(key)) for key in CAPABILITY_KEYS}


def hosts_for_role(role: str) -> tuple[str, ...]:
    """The legal set a capability REFUSAL should name, keyed by the stamped
    role. ``controlEffect`` maps to the WIRED control set rather than the
    role-declaring set — ``inputRequest`` declares the role but nothing reads
    its effectId (``viewops._NOT_WIRED``), and a refusal that recommends an
    inert block is the trap this module exists to close. Unknown role → empty,
    and the caller falls back to its roles_for derivation."""
    if role == "readTrigger":
        return hosts_for("readHost")
    if role == "controlEffect":
        return hosts_for("control")
    return ()


def enrich(entry: dict) -> dict:
    """Stamp the per-block capability keys onto one teaching-payload entry —
    today ``rowAnchor`` (present-only: its absence IS the "cannot press"
    signal, per ``CAPABILITY_NOTE``). Called by the route on both the bulk
    and the single-block branches, so `find_blocks(block=…)` — the deepest
    teaching call, and the one the measured incident actually made — carries
    the same facts as the catalog sweep."""
    kind = entry.get("block")
    if isinstance(kind, str):
        scopes = anchor.row_scopes(kind)
        if scopes:
            entry["rowAnchor"] = list(scopes)
    return entry
