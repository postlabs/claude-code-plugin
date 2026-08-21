"""The ``$``-anchor resolver + data-path parser — the NET-NEW piece with no
spread analog (design §9).

Two jobs:

- **Anchor** (``$rowList.row``): resolve a view anchor to a real block in the
  dough's frozen ``spread`` layout AND the iteration scope it attaches to (the
  block role holding that level's list). Nesting-capable in SHAPE — the descent
  tree (``_DESCENT``) is a per-block-kind nested map — though every populated
  kind is still FLAT (one row scope over the block's own list).
- **Data-path** (``$.email``): the runtime field path an ``act`` interaction
  reads off the clicked datum to fill a target input.

Reuses the ``$``-strip + dotted-split convention of ``app/spreads/boxref.py``
(the ``resolve_ref`` head/split at ``boxref.py:141-142``) — inlined here with a
one-line note rather than importing, to keep the spread files untouched. This
module imports NOTHING from ``app.doughs``/``app.memo``; the ``spread_blocks`` it
walks are threaded in by the caller (never read off a dough here).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.spreads import viewops


# The nesting-capable descent tree. Head ``$<kind>`` picks the block; each dotted
# segment descends one iteration scope whose ``list_role`` names the block role
# binding that level's list, ``children`` the scopes reachable below it.
#
# A row scope is still HALF a contract — it makes an anchor RESOLVE, while the
# frontend compiler must wrap that block's per-item body in an ``effectRow``
# (``blocks/sparkWrap.ts``) or the anchor validates and then renders dead. What
# changed is WHERE the halves live: both are now declared in ``defs.ts``
# (``afforded`` + ``rowScope``, beside the compiler that backs them) and ride one
# ``catalog.json``, so they cannot drift apart across a language boundary. Adding a
# press host is a frontend-only edit; this file learns it for free.
@lru_cache(maxsize=1)
def _descent() -> dict[str, dict[str, Any]]:
    """The row-scope tree, DERIVED from the block catalog.

    It was a hand-written map of kind → scope name → ``{list_role, children}``,
    kept level with the frontend's ``afforded``/``sparkWrap`` wiring by a lockstep
    test. That made it a SECOND declaration of a fact the catalog already carried,
    which is the shape this codebase removes on sight (``provides:`` is the
    precedent): the kind is ``afforded``, the list is ``listRole``, and the only
    thing missing was the SEGMENT NAME — so the name moved into ``defs.ts`` as
    ``rowScope`` and this walks it.

    ``rowScope`` cannot itself be derived, and that is the declared-vs-derived rule
    working rather than an exception to it: ``rowList``→``row`` singularizes, but
    ``positionsLedger``→``position`` and ``optionFeed``→``option`` do not. A name is
    a choice; guessing author-facing vocabulary is the heuristic this codebase
    refuses.

    NESTED descent stays expressible in the SHAPE (``children``) and is empty for
    every kind — no block anchors through a sub-scope yet. When one does, the
    catalog grows the nesting, not this function.
    """
    from app.spreads import catalog

    out: dict[str, dict[str, Any]] = {}
    for kind in catalog.block_kinds():
        scope = (catalog.BLOCK_DEFS.get(kind) or {}).get("rowScope")
        if not scope:
            continue
        # `list_role` is carried for the shape only — `ResolvedAnchor.list_role`
        # has no reader today, so a kind that declares no `listRole` (a press host
        # that never earned view ops) is None here rather than a fabricated default.
        out[kind] = {
            str(scope): {"list_role": catalog.list_role_for(kind), "children": {}}
        }
    return out


def row_scopes(kind: str) -> tuple[str, ...]:
    """The row-scope SEGMENT names ``kind`` anchors by (``('row',)`` for
    ``rowList``) — empty for a kind that renders no pressable row. The one
    accessor over ``_DESCENT``'s keys, so no gate or teaching payload ever
    spells a segment name by hand."""
    return tuple(sorted(_descent().get(kind) or ()))


def anchorable_kinds() -> tuple[str, ...]:
    """Every block kind a row-scoped anchor can land on — ``_DESCENT``'s keys.
    The derived legal set every capability refusal and teaching payload reads;
    a kind wired into ``_DESCENT`` joins them all with no second edit."""
    return tuple(sorted(_descent()))


@dataclass(frozen=True)
class Anchor:
    """A parsed anchor: the head block kind + the ordered descent segments."""

    block_kind: str
    descent: tuple[str, ...]

    @property
    def scope(self) -> str:
        """``block`` when the anchor names a block ALONE (``$rowList`` — a
        block-level control / whole-list landing), ``row`` when it descends into an
        iteration scope (``$rowList.row`` — a per-item press). Derived at PARSE
        time from descent emptiness, so the field-sensitive guards (``act`` must be
        row-scoped; ``read`` must be block-scoped) run WITHOUT resolving against a
        spread — they hold storeless (the memo host, the load-time loader)."""
        return "row" if self.descent else "block"


@dataclass(frozen=True)
class BlockHit:
    """One block found by a containment walk: its PATH and the block itself.

    The path alternates index and role name — ``(1, 'blocks', 0)`` is "layout[1],
    into its ``blocks`` role, item 0". It replaces a bare top-level index because a
    block can now be nested, and the frontend binder needs to WRITE a role onto it
    (``features/spark/Spark.tsx``), which an index into the wrong list cannot do."""

    path: tuple[int | str, ...]
    block: dict[str, Any]


@dataclass(frozen=True, eq=False)
class AnchorMiss:
    """WHY an anchor failed to resolve — a typed miss, not a bare ``None``.

    ``resolve_anchor`` used to collapse four distinct failures into ``None`` and
    the gate re-derived ONE of them (ambiguity) by re-searching, reporting the
    other two as "no such block in the spread" — false whenever the block was
    rendering and merely could not host the scope. Measured live 2026-08-13:
    an agent burned 6 anchor guesses (5 refusals, 57.1s) on ``entityCards``,
    which renders fine but has no row scope. The reasons:

    - ``absent``          — no block answers to the head (name or kind)
    - ``ambiguous``       — several blocks answer, and naming one would help
    - ``no_row_scope``    — the block exists but its KIND renders no pressable
                            row (not in ``_DESCENT``); naming it cannot help,
                            so this outranks ``ambiguous`` (resolution order)
    - ``unknown_segment`` — the kind has row scope, but not under this segment
                            name (``$cardList.row`` — its scope is ``card``)

    ``kind`` is the real block kind when a block was found (a head may be an
    author name), else the anchor head. ``segment``/``legal`` are populated for
    ``unknown_segment`` only."""

    reason: str
    kind: str
    hits: tuple[BlockHit, ...] = ()
    segment: str = ""
    legal: tuple[str, ...] = ()


@dataclass(frozen=True)
class ControlMiss:
    """WHY a ``$control.<name>`` ref failed to resolve. ``no_control_block`` =
    the spread renders no control block at all (add one); ``name_not_found`` =
    controls exist under OTHER names (``present`` — use one of those). The
    split exists because the two want opposite fixes, and the old single
    message sent a typo hunting for a missing block."""

    reason: str
    present: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class ResolvedAnchor:
    """A resolved anchor: the matched block's kind + its PATH in the layout tree +
    the block itself + the leaf iteration scope's ``list_role`` (``None`` at block
    scope — the whole block is the target, no iteration) + the ``scope`` tag
    (``block`` | ``row``).

    ``eq=False`` because ``block`` is a dict: a generated ``__eq__``/``__hash__``
    over it would be a hashability landmine for a value nothing compares."""

    block_kind: str
    path: tuple[int | str, ...]
    block: dict[str, Any]
    list_role: str | None
    scope: str

    @property
    def block_index(self) -> int | str:
        """The FIRST path segment — the top-level layout index the anchored block
        sits under (itself, when the anchor resolved at top level). Kept as a
        convenience for callers that only need to name a location in a message."""
        return self.path[0] if self.path else -1


def _split_ref(ref: str) -> list[str]:
    """``$rowList.row`` → ``['rowList', 'row']`` (mirrors ``boxref.resolve_ref``'s
    ``$``-strip + ``.split('.')``, boxref.py:141-142)."""
    path = ref[1:] if ref.startswith("$") else ref
    return path.split(".")


def parse_anchor(anchor: str) -> Anchor | None:
    """Parse ``$rowList.row`` → ``Anchor('rowList', ('row',))`` (row scope) and
    ``$rowList`` → ``Anchor('rowList', ())`` (block scope — a block-level control /
    whole-list landing). ``None`` when not a ``$<kind>[.<descent...>]`` ref (no
    ``$`` head, or an empty segment — ``$``/``$.email`` reject, leaving the ``$.``
    data-path grammar to ``parse_data_path``)."""
    if not anchor.startswith("$"):
        return None
    parts = _split_ref(anchor)
    if not parts or not all(parts):
        return None
    return Anchor(block_kind=parts[0], descent=tuple(parts[1:]))


def _is_subdoc(val: Any) -> bool:
    """Is this role value a nested BLOCK LIST rather than a data binding?

    Structural, not a table of container kinds — and deliberately so. The renderer
    asks exactly this question and in exactly this way: ``section.ts`` does
    ``Array.isArray(roles.blocks)`` then reads ``b.block`` off each entry, and
    ``expandable`` mirrors it. Neither consults the catalog, which does not mark
    which role holds children anyway (``section``/``columns`` call it ``blocks``,
    ``tabs``/``overviewPager`` call it ``pages``).

    So this needs no ``app.spreads`` change and no second source of truth, and a
    container added later works on both sides with no edit to either. It is safe
    because a non-container role value is a field KEY, a literal or a ``$``-ref — a
    string — never a list of ``{block: ...}`` dicts."""
    return (
        isinstance(val, list)
        and bool(val)
        and all(
            isinstance(x, dict) and isinstance(x.get("block"), str) for x in val
        )
    )


def walk_blocks(
    spread_blocks: list[dict[str, Any]], _path: tuple[int | str, ...] = ()
) -> Iterator[BlockHit]:
    """Every block in the layout TREE, pre-order, each with its path.

    Containment is the composition's only inter-block relation, so this is the whole
    address space. Descending matters because the design system tells authors to use
    containers — ``block_guide``'s ``interactive`` family says "Structure a
    multi-part result with these; **never stack many blocks flat**" — and until this
    walk existed a spark could not reach a block the author had been instructed to
    nest. A sectioned app's searchBox and rowList both live one level down."""
    for i, block in enumerate(spread_blocks):
        if not isinstance(block, dict):
            continue
        yield BlockHit(path=(*_path, i), block=block)
        for role, val in (block.get("roles") or {}).items():
            if _is_subdoc(val):
                yield from walk_blocks(val, (*_path, i, role))


def find_blocks(
    head: str, spread_blocks: list[dict[str, Any]]
) -> list[BlockHit]:
    """Every block ``head`` addresses, in document order.

    ``head`` is matched as a NAME first and as a block KIND only if no block
    claims that name. Name wins because it is the specific reference: a spread
    that bothered to name a block meant that one, and a kind that happens to
    collide with someone's name must not shadow it.

    Returns the FULL list rather than the first match on purpose. By KIND an
    anchor is not an address, so two blocks of one kind make ``$rowList``
    genuinely ambiguous and the caller must be able to REFUSE rather than
    silently take the first — nesting makes that the normal case, since a
    two-section app naturally holds two lists. By NAME the list is how a
    DUPLICATE name is caught: two blocks answering to one handle is an authoring
    mistake, and the same refusal reports it.
    """
    # LIST, not the generator: two passes read it, and a generator would be
    # spent by the first — leaving every kind-addressed anchor resolving to
    # nothing at all.
    hits = list(walk_blocks(spread_blocks))
    named = [h for h in hits if h.block.get("name") == head]
    return named or [h for h in hits if h.block.get("block") == head]


def resolve_anchor(
    anchor: Anchor, spread_blocks: list[dict[str, Any]]
) -> ResolvedAnchor | AnchorMiss:
    """Resolve ``anchor`` against a dough's frozen ``spread`` blocks (each a
    ``{block, roles, knobs}`` dict). Find the UNIQUE block of the anchor's kind
    anywhere in the containment tree; at BLOCK scope (no descent) the whole block is
    the target (``list_role=None``); at ROW scope walk the descent through
    ``_DESCENT`` to the leaf scope's ``list_role``.

    A failure returns a typed ``AnchorMiss`` naming WHICH way it failed — the
    gate turns each reason into its own message, so it never has to re-derive
    the cause (the old bare-``None`` contract made it re-search and misreport;
    see ``AnchorMiss``).

    ★ Ambiguity is refused rather than resolved to the first hit. An anchor
    names a KIND and blocks have no ``id``, so with two rowLists ``$rowList`` does
    not mean anything in particular — and picking one would bind the spark to a
    block the author did not choose, silently, which is the failure class every
    other gate in this kernel exists to refuse (``_gate_read_triggers``,
    ``_gate_row_gestures``).

    ★ CAPABILITY OUTRANKS AMBIGUITY, by construction. A row-scoped anchor on a
    kind with no row scope fails ``no_row_scope`` even when several such blocks
    render — the ambiguity remedy ("give one a `name:`") cannot help a kind
    that cannot host the scope at all, and handing it out anyway is measured to
    send the author down a dead end (the named block then "does not resolve")."""
    hits = find_blocks(anchor.block_kind, spread_blocks)
    if not hits:
        return AnchorMiss(reason="absent", kind=anchor.block_kind)
    if anchor.scope == "row":
        kinds = {str(h.block.get("block") or "") for h in hits}
        if all(not _descent().get(k) for k in kinds):
            kind = next(iter(kinds)) if len(kinds) == 1 else anchor.block_kind
            return AnchorMiss(
                reason="no_row_scope", kind=kind, hits=tuple(hits)
            )
    if len(hits) > 1:
        return AnchorMiss(
            reason="ambiguous", kind=anchor.block_kind, hits=tuple(hits)
        )
    hit = hits[0]
    # The head may be a NAME, so the block's real kind comes off the HIT — never
    # off the anchor string. Everything catalog-keyed downstream (the afforded
    # gesture set, the effect-host role check, `_DESCENT`) needs the kind, and a
    # name would silently miss every one of those lookups.
    kind = str(hit.block.get("block") or "")
    # Block scope: the block itself is the landing target (a read refresh/paginate
    # replaces/appends its value) — no iteration scope to walk.
    if anchor.scope == "block":
        return ResolvedAnchor(
            block_kind=kind,
            path=hit.path,
            block=hit.block,
            list_role=None,
            scope="block",
        )
    # Row scope: descend to the leaf iteration scope's list_role. The all-rowless
    # pre-check above already caught a kind with no _DESCENT entry, so `scopes`
    # is non-empty here unless the name-duplicate mixed-kind case slipped a
    # rowless single through — keep the guard for that shape.
    scopes = _descent().get(kind)
    if not scopes:
        return AnchorMiss(reason="no_row_scope", kind=kind, hits=(hit,))
    list_role: str | None = None
    for seg in anchor.descent:
        scope = scopes.get(seg)
        if scope is None:
            return AnchorMiss(
                reason="unknown_segment", kind=kind, hits=(hit,),
                segment=seg, legal=tuple(sorted(scopes)),
            )
        list_role = scope["list_role"]
        scopes = scope["children"]
    if list_role is None:
        # Unreachable in practice: scope=="row" ⟺ descent non-empty, so the loop
        # always assigns. Typed as unknown_segment so an impossible state still
        # answers with the legal vocabulary instead of a bare fallthrough.
        return AnchorMiss(
            reason="unknown_segment", kind=kind, hits=(hit,),
            legal=row_scopes(kind),
        )
    return ResolvedAnchor(
        block_kind=kind,
        path=hit.path,
        block=hit.block,
        list_role=list_role,
        scope="row",
    )


def parse_data_path(val: str) -> list[str] | None:
    """``$.email`` → ``['email']``; ``$.contact.email`` → ``['contact', 'email']``
    (nesting-capable). ``None`` when ``val`` is not a ``$.<path>`` datum ref — the
    only ``inputs`` value shape this slice accepts (a literal-constant input
    channel is out of scope)."""
    if not val.startswith("$."):
        return None
    parts = val[2:].split(".")
    if not all(parts):
        return None
    return parts


def parse_result_path(val: str) -> list[str] | None:
    """``$value.next_cursor`` → ``['next_cursor']`` — a path off the LAST OUTPUT, a
    ``read``'s re-call-arg source (e.g. a pagination cursor). ``None`` when not a
    ``$value.<path>`` ref. The result-scope sibling of ``parse_data_path`` (which
    owns the ``$.`` row-datum scope). Distinct roots so a block-scoped read (no
    pressed row) can name the current value but not a nonexistent row datum."""
    prefix = "$value."
    if not val.startswith(prefix):
        return None
    parts = val[len(prefix):].split(".")
    if not all(parts):
        return None
    return parts


def parse_selection_path(val: str) -> list[str] | None:
    """``$selection.id`` → ``['id']`` — a path off the SELECTED row (master-detail's
    dependency source; design §17). The selection-scope sibling of
    ``parse_data_path`` (``$.``, the clicked row) and ``parse_result_path``
    (``$value.``, the last output). An ``act`` reads its detail-fetch inputs off the
    frontend selection, so lifting the trigger from press to reactive never touches
    the artifact. ``None`` when not a ``$selection.<path>`` ref."""
    prefix = "$selection."
    if not val.startswith(prefix):
        return None
    parts = val[len(prefix):].split(".")
    if not all(parts):
        return None
    return parts


def parse_control_path(val: str) -> str | None:
    """``$control.keyword`` → ``'keyword'`` — the NAME of a view control whose
    live value fills a ``read`` param (design §20). The fourth and last ref scope,
    beside ``$.`` (clicked row), ``$value.`` (last output) and ``$selection.``
    (selected row).

    Returns a bare NAME, not a path, because a control holds a SCALAR — the text in
    a search box, not a record — so ``$control.a.b`` has nothing to descend into and
    is rejected. That is the one asymmetry with its three siblings, and it is the
    honest one: depth would imply structure the control substrate does not have.

    The name is not free-form: it must match a control block's ``name`` role in the
    same spread, resolved by ``resolve_control`` — the same
    explicit-reference-replaces-lexical-scope rule the anchor obeys (design §8).
    ``None`` when not a ``$control.<name>`` ref."""
    prefix = "$control."
    if not val.startswith(prefix):
        return None
    name = val[len(prefix):]
    if not name or "." in name:
        return None
    return name


def resolve_control(
    name: str, spread_blocks: list[dict[str, Any]]
) -> BlockHit | ControlMiss:
    """The control block DECLARING ``name`` (its ``name`` role), or a typed
    ``ControlMiss`` saying which way it failed.

    The control-scope sibling of ``resolve_anchor``: a ``$control.<name>`` param must
    name a control the view actually renders, or the read fires with an argument
    nothing can ever fill. Walks the containment TREE for the same reason the anchor
    does — a searchBox lives inside its section in any app the design system would
    call well-structured.

    No ambiguity gate here, and that asymmetry is deliberate: a control is addressed
    by the NAME the author chose, not by kind, so two controls named ``keyword``
    is an authoring duplicate rather than an under-specified reference. First match
    wins the same way it always did."""
    present: list[str] = []
    n_controls = 0
    for hit in walk_blocks(spread_blocks):
        if hit.block.get("block") not in viewops.CONTROL_BLOCKS:
            continue
        n_controls += 1
        roles = hit.block.get("roles")
        declared = roles.get("name") if isinstance(roles, dict) else None
        if declared == name:
            return hit
        if isinstance(declared, str) and declared:
            present.append(declared)
    if n_controls == 0:
        return ControlMiss(reason="no_control_block")
    return ControlMiss(reason="name_not_found", present=tuple(present))
