"""The VIEW-OP catalog — the closed set of pure reshapes a block may declare.

A view op reshapes the block's OWN list, at render time, over data already in
``value``: no bake, no host, no controller. It is the declarative half of the
vision's "Tier 1" (local state over data already fetched) — the half that needs
no state at all, because this slice takes only LITERAL arguments.

Inline dict, not a ``catalog.json`` reader, for the same reason
``sparks.interaction_defs`` is: a closed 3-member backend set with no ``defs.ts``
upstream. The frontend twin (``layout/viewops.ts``) applies them; this half only
gates what an author may write.

**What a view op is NOT.** It cannot re-fetch, and it cannot see beyond the
value it was handed. A ``sort`` over a truncated fetch is confidently wrong. The
rule the block guide teaches: *a view op reshapes what is on screen; any question
whose answer depends on the full set is a spark ``read``.*
"""

from __future__ import annotations

from typing import TypedDict


class OpDef(TypedDict):
    required: tuple[str, ...]
    optional: tuple[str, ...]


# op name -> which argument keys it takes. Per-item FIELD names inside those args
# (``sort.by``, ``filter.where``) are deliberately NOT gated here: the backend
# only knows a dough's TOP-LEVEL output fields (``drill.output_fields``), so
# checking a per-item key against them would false-reject every valid op. That
# check belongs in the non-blocking design lint, which receives the value.
OP_DEFS: dict[str, OpDef] = {
    # Keep only the items whose `where` field equals `eq` (or, with `ne`, differs).
    "filter": {"required": ("where",), "optional": ("eq", "ne")},
    # Order by a per-item field. `dir` is asc (default) or desc.
    "sort": {"required": ("by",), "optional": ("dir",)},
    # Keep the first N. The "show a head, not the whole list" case.
    "limit": {"required": ("n",), "optional": ()},
    # Case-folded SUBSTRING match of `q` across the fields named in `in`. `q` is
    # normally a `$view.<cell>` ref (the live text in a searchBox) — an empty q
    # matches everything, so an untouched box shows the whole list.
    #
    # Say the limits out loud, because "search" promises more than this delivers:
    # substring only. No tokenizer, no stemming, no ranking, and NO CJK
    # segmentation — Korean is a first-class surface here, and a substring match
    # over Korean text finds only literal runs. If a real search is wanted, the
    # source dough does it and a spark `read` fetches the answer.
    "search": {"required": ("in", "q"), "optional": ()},
}

# Enum-valued op args, gated like a block knob.
OP_KNOBS: dict[str, dict[str, tuple[str, ...]]] = {
    "sort": {"dir": ("asc", "desc")},
}


def op_names() -> tuple[str, ...]:
    """The op names an author may write (sorted, for enumerating gate messages)."""
    return tuple(sorted(OP_DEFS))


# The spread block kinds that are VIEW CONTROLS — blocks holding frontend-local
# cell state that a `$view.<cell>` op arg (or a spark `$control.<name>` read param)
# reads by name. A control names itself via its `name` role.
#
# It lives HERE, not in `app/sparks/interaction_defs.py`, because a control is a
# SPREAD concept: a plain spread filters with one and never loads a controller.
# Sparks imports it downward (the sanctioned app.spreads.spark -> app.spreads edge). Two
# copies would be worse than one in the wrong place: a kind added to only one list
# is wired by the binder and refused by the gate, or the reverse.
CONTROL_BLOCKS: frozenset[str] = frozenset({"searchBox", "viewControl"})

# DECLARED, not derived from the catalog's `controlEffect` role — and the gap is
# recorded rather than rediscovered: deriving would admit every declarer, and
# `inputRequest` declares the role while no binder override reads its effectId
# (`blocks/inputRequest.ts` cites a `Spark.tsx` override that does not exist),
# so a derived set would recommend a form that renders and never submits.
# `tests/e2e/test_spread_capability_contract.py` pins CONTROL_BLOCKS ==
# {controlEffect declarers} - _NOT_WIRED, so the divergence is a red test the
# day the binder learns to read it (delete the entry here) or a new declarer
# lands unwired (add one).
_NOT_WIRED: dict[str, str] = {
    "inputRequest": "declares controlEffect; no binder override reads its effectId",
}


def resolve_cell(name: str, spread_blocks: list[dict]) -> int | None:
    """Index of the control block DECLARING view cell ``name`` (its ``name`` role),
    or ``None``. A `$view.<cell>` arg naming a control the view does not render
    would leave the op reading an argument nothing can ever fill."""
    for i, block in enumerate(spread_blocks):
        if not isinstance(block, dict):
            continue
        if block.get("block") not in CONTROL_BLOCKS:
            continue
        roles = block.get("roles")
        if isinstance(roles, dict) and roles.get("name") == name:
            return i
    return None
