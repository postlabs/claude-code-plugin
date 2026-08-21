"""Surface-agnostic spread validation — the block-catalog gate.

The neutral half of spread validation: gate a composition's block list against
the block catalog (``catalog.BLOCK_DEFS``) with NO surface / MemoStore /
registry binding. Two entry points share the one gate:

- :func:`composition` reads a parsed :class:`~app.spreads.model.Spread`
  (``spread.layout``) — the memo composition path.
- :func:`composition_spec` reads a dough's frozen ``{tier,blocks}`` render spec
  (``Dough.spread``) — the donut-snapshot path, plus a return-key FIELD-path
  gate.

Both lower to :func:`_gate_blocks` (block kind ∈ catalog, required roles bound,
bound roles known, knob values ∈ enum). This module depends ONLY on
``catalog`` + ``model`` — the neutral spread kernel — so both memo (the
surface-bound special case) and doughs (the donut base case) import it downward.
"""

from __future__ import annotations

import re
from typing import Any

from app.spreads import catalog, viewops
from app.spreads.model import Spread


# ── literal-label roles ───────────────────────────────────────────────────────
# The subset of each block's roles that render their bound value VERBATIM (a label /
# unit / caption / title-text), NOT as a field read. Binding one of these to a FIELD
# KEY prints the key name (the `caption:'channelCaption'` / `doneTitle:'doneTitle'`
# class of bug). Curated to the label roles an agent most often mis-binds — not
# exhaustive; a missing entry only means no lint, never a false reject.
LITERAL_ROLES: dict[str, frozenset[str]] = {
    "statBand": frozenset({"title"}),
    "dataGrid": frozenset({"caption"}),
    "taskList": frozenset({"doneTitle"}),
    "taskBoard": frozenset({"doneTitle"}),
    "reviewList": frozenset({"verifiedLabel", "helpfulLabel"}),
    "pollResults": frozenset({"voteLabel", "closedLabel", "openLabel", "unit"}),
    # `prosCons: {prosTitle, consTitle}` was here and was WRONG: `prosCons.ts` roots
    # both (`props[role] = rootKey(v)` inside a loop over the two names), so the trap
    # fired exactly when the author bound them CORRECTLY — and following its advice
    # produced the bug it claimed to prevent. Removed on evidence from the derived
    # `catalog.role_kind`, which now classifies both as `rootPath`.
    #
    # The rest of this table stays HAND-CURATED for now. The derived map cannot
    # replace it wholesale: it classifies a role only when the compiler's spelling is
    # recognisable, so it returns `None` for most entries here — and `None` means
    # "unknown", not "not literal". Retiring the table on that would trade a table
    # that is wrong in one place for a check that is silent in most.
    "leaderboard": frozenset({"unit", "currency"}),
}


# A `$` string that cannot resolve to a FIELD: bare ``$`` / ``$item`` (both return
# a whole object), or ``$`` opening on a character that cannot start an identifier
# (``$172`` → ``root['172']``). ``$.x``, ``$item.x``, ``$view.x`` and ``$foo`` are
# real binds and pass. Mirrors frontend B6 (``check-spread-grammar.mjs``).
_MALFORMED_PATH = re.compile(r"^\$(?:item)?$|^\$[^A-Za-z_.]")


def _normalize_knob(val: Any) -> Any:
    """Coerce a YAML/JSON boolean knob value to its catalog STRING form.

    Knob enums are strings by construction (``['false', 'true']``), but a spread
    is authored in YAML — where ``defaultOpen: false`` parses to a real ``bool``,
    not ``"false"``. That is the natural thing for an author (human or agent) to
    write, and refusing it refuses a spec that means exactly what it says.

    Twin of ``normalizeKnob`` in the frontend ``spread/layout/validate.ts`` and
    ``spread/layout/blocks/index.ts``. All three must agree on what a valid knob
    is: the frontend's ``knobValue`` reads the same value at COMPILE and falls
    back to the DEFAULT on a miss, so an uncoerced boolean ``true`` renders as
    ``false`` — silently inverted. Change one, change all three.
    """
    return str(val).lower() if isinstance(val, bool) else val


def composition(spread: Spread) -> list[str]:
    """Gate a Tier-3 ``layout:`` composition against the block-catalog mirror
    (``catalog.BLOCK_DEFS``) — the backend twin of the frontend
    ``validateCompositionSpec`` (R7/R8/R10):

    - block kind ∈ the catalog,
    - every REQUIRED role of the block is bound (present + non-empty),
    - every bound role is a known role of the block (required ∪ optional) — the
      block analog of ``bind ⊆ slots``,
    - every knob value ∈ the knob's enum.

    The per-block FIELD check (role value ∈ the surface's record schema) is NOT
    gated here — no memo composition currently gates block roles against a record
    schema (calendar, the first composition, has no record model, and the rest
    followed it). Re-introducing a record-field gate on the composition path would
    walk each block's FIELD roles against ``memo.spreads.manifest``.
    """
    blocks = [
        (blk.block, blk.roles, blk.knobs, blk.view)
        for blk in (spread.layout or [])
    ]
    return _gate_blocks(blocks, spread.path)


def composition_spec(
    spec: dict[str, Any],
    ref_id: str,
    *,
    return_keys: frozenset[str] | None = None,
    output_fields: dict[str, set[str] | None] | None = None,
) -> list[str]:
    """Gate a FROZEN composition render spec — the donut-SNAPSHOT twin of
    :func:`composition`. Where :func:`composition` reads a parsed :class:`Spread`
    (``spread.layout``), this reads the raw ``{tier:'composition', blocks:[…]}``
    dict a dough carries on ``Dough.spread`` (the render spec painted at
    bake-complete). Same surface-agnostic block-catalog gate (block kind ∈
    catalog, required roles bound, bound roles known, knob values ∈ enum), no
    surface binding — a donut has no registry surface, so the surface FIELD /
    collection gates are moot exactly as for the calendar composition.

    ``return_keys`` / ``output_fields`` (the dough's return-block keys + each
    object output's known field set) enable the donut-snapshot FIELD-path gate
    (:func:`_field_path_issues`): a block role that reads a value off
    ``donut.output`` whose HEAD segment is not a return key paints a blank card.
    The caller (``app.doughs.validation.engine._spread_issues``) computes them
    with ``drill.output_fields``; omitted → the path check is skipped.

    Called from the dough save/validate path (``app.doughs.validation.engine``)
    as a normal top-level import: ``app.spreads`` is the neutral spread kernel (it
    imports nothing from ``app.doughs`` or ``app.memo``), so there is no cycle —
    it reuses ``catalog`` as the single block-catalog source of truth."""
    tier = spec.get("tier")
    if tier != "composition":
        return [
            f"spread '{ref_id}' render spec has tier '{tier}' — a donut-snapshot "
            f"spread must be a composition (tier 'composition')"
        ]
    raw = spec.get("blocks")
    if not isinstance(raw, list):
        return [f"spread '{ref_id}' composition spec has no 'blocks' list"]
    blocks = [
        (b.get("block", ""), b.get("roles") or {}, b.get("knobs") or {}, b.get("view") or [])
        for b in raw
        if isinstance(b, dict)
    ]
    return _gate_blocks(
        blocks, ref_id, return_keys=return_keys, output_fields=output_fields,
    )


def _is_subdoc(val: Any) -> bool:
    """Is this role value a nested BLOCK LIST rather than a data binding?

    Structural, not a table of container kinds. The renderer asks exactly this
    question and in exactly this way — ``section.ts`` does
    ``Array.isArray(roles.blocks)`` then reads ``b.block`` off each entry — and the
    catalog does not mark container roles at all (``section``/``columns``/
    ``expandable`` call the list ``blocks``, ``tabs``/``overviewPager`` call it
    ``pages``). So there is no table to keep in step and a container added later is
    gated with no edit here.

    Safe because a non-container role value is a field KEY, a literal or a
    ``$``-ref — a string, never a list of ``{block: ...}`` dicts.

    ★ TWIN of ``app.spreads.spark.anchor._is_subdoc``, which walks the same tree to resolve
    an anchor. Change one, change both."""
    return (
        isinstance(val, list)
        and bool(val)
        and all(isinstance(x, dict) and isinstance(x.get("block"), str) for x in val)
    )


def _list_shaped_entry(val: Any) -> int | None:
    """The index of the first entry that is itself a LIST of blocks, or ``None``.

    The shape an author writes when a ``pages`` entry feels like a ``blocks``
    list — ``pages: [[chart, grid], …]``. ``_is_subdoc`` rightly answers no
    (the items are lists, not ``{block: …}`` dicts), so the walk never descends
    and every gate passes — while the renderer reads ``.block`` off each entry,
    gets ``undefined``, and refuses the WHOLE surface (frontend R7). Saves
    clean, renders dead: measured live, a tabs trend card with three
    list-shaped pages, reported ok:true to the agent. Detected exactly — an
    inner list that IS a subdoc — so a data-bound list of lists, which never
    contains block dicts, cannot false-positive."""
    if not isinstance(val, list):
        return None
    for i, x in enumerate(val):
        if isinstance(x, list) and _is_subdoc(x):
            return i
    return None


def walk_block_dicts(blocks: Any) -> list[dict]:
    """Every block in an AUTHORED composition, pre-order, containers included.

    The raw-dict twin of ``_walk_composition``: same containment rule
    (``_is_subdoc``), different input — the ``{block, roles, knobs}`` dicts as an
    agent POSTs them, before anything parses them into tuples. Public because a
    caller that NORMALIZES a composition before the gate sees it must walk the
    same tree the gate will: ``render_spread`` coerced a numeric knob (``cols: 2``
    — the natural JSON spelling) at the top level only, so the identical knob
    inside a ``section`` reached the gate as an int and was refused. And
    ``block_guide`` tells authors to nest, so the refused shape was the one it
    teaches.

    Dicts are yielded BY REFERENCE — the point is to let the caller mutate them.
    """
    out: list[dict] = []
    for b in blocks if isinstance(blocks, list) else []:
        if not isinstance(b, dict):
            continue
        out.append(b)
        for val in (b.get("roles") or {}).values():
            if _is_subdoc(val):
                out.extend(walk_block_dicts(val))
    return out


def label_issues(blocks: Any, box: Any, label: str,
                 *, extra: Any = None, require_title: bool = False) -> list[str]:
    """The BOX gate — every ``$``-ref a spread reaches for, on both value sources.

    Two refusals, and each one is a bug that shipped:

    - **An unresolved ref.** ``resolve_tree`` leaves it verbatim, and the
      RENDERER reads a surviving ``$foo`` as a data path (``resolver.ts``:
      ``$foo`` → ``root.foo``) — so the card paints BLANK, not the raw string.
      Nothing downstream can tell that from a genuinely empty field.
      ``postlab.toss.invest``'s desk had nine of them and no box at all.
    - **A ref on a path-typed role.** The renderer roots a bare string
      (``rootKey``: ``x`` → ``$.x``), so a label RESOLVES to text and is then
      re-read as a path — blank again, and a box cannot save it. Checked only
      on an EXPLICIT ``rootPath`` kind: ``role_kind`` is deliberately partial
      (``None`` = unclassified), so a check that fired on ``None`` would fire on
      everything unknown.

    A block's ``on:`` map is deliberately NOT scanned: a spark's refs are a third
    ``$`` channel — ``$selection.<field>`` names the pressed row, ``into:
    $<block>`` names a sibling — so reading them as labels reports every
    interactive spread as broken.

    ``require_title`` is the MEMO-surface rule: a surface's tab title is read
    with no ref at all (``memo.spreads.loader``), so it is required there even
    though nothing references it. It is off elsewhere on purpose — a spread whose
    roles are all field-bound needs no box, which is 46 of the 66 shipped.
    """
    from app.spreads.boxref import DEFAULT_LOCALE, label_refs, resolve_ref

    issues: list[str] = []
    block_dicts = walk_block_dicts(blocks)
    for b in block_dicts:
        kind = b.get("block")
        for role, val in (b.get("roles") or {}).items():
            if not isinstance(val, str) or not val.startswith("$"):
                continue
            if not label_refs(val):  # a renderer path — not ours
                continue
            if (catalog.role_kind(kind, role) or {}).get("kind") == "rootPath":
                issues.append(
                    f"spread '{label}' binds label ref '{val}' to "
                    f"`{kind}.{role}`, which reads a data PATH — the label "
                    "resolves to text and is then re-read as `$.<text>`, so the "
                    "slot renders empty. Put the text on the value under a key "
                    "and bind that key, or move it to a text-typed role"
                )

    # ★ A BLOCK'S `on:` MAP IS NOT LABEL TEXT, AND THE OLD EXEMPTION STOPPED
    # COVERING IT. A spark's refs are a third `$` channel — `$selection.<field>`
    # names the pressed row, `into: $<block>` names a sibling — and neither head
    # is in `boxref._DATA_HEADS`, so `label_refs` returns them and every one is
    # reported missing from box.yaml. That was harmless while the controller was
    # a spread-level `interactions:` list this function never walked; a81779516
    # moved the map INSIDE the block, and `walk_block_dicts` walks blocks.
    #
    # Measured: a master-detail press (`{act, inputs {id: $selection.id},
    # into: $recordDetail}`) renders `ok: true` — the render route does not call
    # this — and is then refused at canvas persist, where the only user-visible
    # text is "this card's template could not be saved — re-render it", advice
    # that cannot succeed. `press: {open: …}` and `refresh:` were unaffected,
    # which is why it read as a master-detail problem rather than a gate bug.
    scanned = [{k: v for k, v in b.items() if k != "on"} for b in block_dicts]
    refs = set(label_refs(scanned) + label_refs(extra))
    for ref in sorted(refs):
        if resolve_ref(box, ref, DEFAULT_LOCALE) is None:
            issues.append(
                f"spread '{label}' label ref '{ref}' has no `en` text in box.yaml"
            )

    # The PULL rule, stated as a check: an entry exists BECAUSE a ref reaches for
    # it. The mirror of the miss above, and the reason this box stayed clean
    # while the dough box — a schema mirror, pushing one entry per declared port
    # — accumulated thousands nobody read. `title` is exempt: it is read with no
    # ref at all.
    from app.spreads.boxref import IMPLICIT_KEYS

    # `name`/`about` are NOT required here yet, deliberately. They are what an
    # agent reads to PICK a spread (`app.spreads.index`), so they want to be a
    # floor — but `save_spread` runs this on every mint, including an early draft
    # that has no box yet. So the demand sits where a spread becomes PUBLIC
    # instead: `require_box=True` on the explicit `mint_spread`, on `promote`,
    # and on `finalize`.
    used = {r[1:] for r in refs} | IMPLICIT_KEYS
    for key in sorted(box.keys_for(DEFAULT_LOCALE) - used):
        issues.append(
            f"spread '{label}' box.yaml carries '{key}', which no `$`-ref asks "
            "for — delete it, or bind it where it belongs"
        )
    return issues


# Nesting is now the shape the design system asks for, and nothing bounded it: a
# 60-deep composition and a list stamped inside every row of a list both validated
# clean. Every block that has ever shipped sits at depth 1 or 2 (103 and 27 across
# the 66 bundled spreads), so 3 is a level of headroom above all of it.
_MAX_NEST_DEPTH = 3


def _nesting_issues(blocks: list[dict], where: str = "layout", depth: int = 1,
                    in_record: str | None = None) -> list[str]:
    """Depth and per-record containment, which the flat walk cannot see.

    A ``per: record`` sub-document is stamped once per ROW, so a per-record nester
    inside one renders a list per row of a list — N x M cards from a spec that reads
    like two lines. A `gallery` or `sparkbar` in there is the sanctioned shape and
    stays legal; what is refused is the block that repeats a sub-document again."""
    issues: list[str] = []
    for i, b in enumerate(blocks if isinstance(blocks, list) else []):
        if not isinstance(b, dict):
            continue
        kind = str(b.get("block") or "")
        at = f"{where}[{i}]"
        if depth > _MAX_NEST_DEPTH:
            issues.append(
                f"{at} '{kind}' nests {depth} deep — the limit is {_MAX_NEST_DEPTH}. "
                f"Lift a level out into its own block; nothing shipped goes past 2."
            )
            continue
        nests = catalog.nests_for(kind) or {}
        per_record = nests.get("per") == "record"
        if per_record and in_record:
            issues.append(
                f"{at} '{kind}' repeats a sub-document inside '{in_record}', which "
                f"already stamps one per row — that is a list per row of a list. "
                f"Bind the inner list at the top level instead."
            )
            continue
        for role, val in (b.get("roles") or {}).items():
            if _is_subdoc(val):
                issues.extend(_nesting_issues(
                    val, f"{at}.{role}", depth + 1, kind if per_record else in_record,
                ))
    return issues


def _walk_composition(
    blocks: list[tuple[str, dict, dict, list]],
    _where: str = "layout",
) -> list[tuple[str, str, dict, dict, list]]:
    """Flatten a composition's containment tree to ``(where, kind, roles, knobs,
    view)``, pre-order.

    ★ WHY THIS EXISTS. The gate walked only the TOP LEVEL, so a block inside a
    container was not gated at all: measured, a nested block could name an unknown
    block kind, bind a role the block does not have, or omit a REQUIRED role, and
    all three came back clean. The frontend validator meanwhile DOES recurse
    (``validate.ts`` → ``expandable``/``section``/``columns``.blocks,
    ``tabs``/``overviewPager``.pages) and refuses the whole surface on any of them,
    stating its own invariant as "validated-or-refused, never half-rendered".

    So the two gates disagreed about a whole region of the grammar, in the worse
    direction: an authoring error there SAVED clean and then blanked the card at
    render, naming a rule the author had to go find. Nesting was rare while a spark
    could not anchor into a container; now that it can, this is where authoring
    happens — `block_guide`'s `interactive` family tells authors to nest ("never
    stack many blocks flat").

    ``where`` reads as the author's own file (``layout[0].blocks[1]``), matching the
    spark gate's paths so one mental model covers both."""
    out: list[tuple[str, str, dict, dict, list]] = []
    for i, (kind, roles, knobs, view) in enumerate(blocks):
        at = f"{_where}[{i}]"
        out.append((at, kind, roles, knobs, view))
        for role, val in (roles or {}).items():
            if not _is_subdoc(val):
                continue
            children = [
                (
                    b.get("block", ""),
                    b.get("roles") or {},
                    b.get("knobs") or {},
                    b.get("view") or [],
                )
                for b in val
                if not b.get("spread")      # an include, resolved at load
            ]
            out.extend(_walk_composition(children, f"{at}.{role}"))
    return out


def _gate_blocks(
    blocks: list[tuple[str, dict, dict, list]],
    ref_id: str,
    *,
    return_keys: frozenset[str] | None = None,
    output_fields: dict[str, set[str] | None] | None = None,
) -> list[str]:
    """The surface-agnostic block-catalog gate shared by :func:`composition`
    (memo ``Spread.layout``) and :func:`composition_spec` (a dough's frozen
    ``{tier,blocks}`` render spec). One block-contract source of truth
    (``catalog.BLOCK_DEFS``); messages read ``layout[i]`` for both since a
    donut snapshot IS a composition.

    ``return_keys`` / ``output_fields`` are only threaded by the donut-snapshot
    caller — the memo ``composition()`` path passes none (it gates no per-field
    record schema), so its role values are left untouched here."""
    issues: list[str] = []
    if not blocks:
        return [f"spread '{ref_id}' has an empty 'layout' — needs at least one block"]
    # Flatten the containment TREE first, so every block is gated wherever it sits.
    # See `_walk_composition` for why nesting had to start being gated.
    walked = _walk_composition(blocks)
    issues.extend(_nesting_issues(
        [{"block": k, "roles": r} for k, r, _, _ in blocks]
    ))
    # A `$view.<cell>` op arg is resolved against the WHOLE spread (the control may
    # sit in any block), so the cell gate needs the sibling blocks, not just this
    # one. `resolve_cell` reads only kind + roles.name, so this projection is all it
    # takes — no second pass, no model import. Built from the WALK, not the top
    # level: a searchBox inside a `section` is still a control this spread renders.
    raw_blocks = [{"block": k, "roles": r} for _, k, r, _, _ in walked]
    for where, kind, roles, knobs, view in walked:
        defn = catalog.BLOCK_DEFS.get(kind)
        if defn is None:
            issues.append(
                f"spread '{ref_id}' {where} names unknown block '{kind}' "
                f"(known: {sorted(catalog.block_kinds())})"
            )
            continue
        for role in defn["required"]:
            v = roles.get(role)
            if v is None or v == "":
                issues.append(
                    f"spread '{ref_id}' {where} block '{kind}' requires role '{role}'"
                )
        allowed = catalog.roles_for(kind)
        for role in roles:
            if role not in allowed:
                issues.append(
                    f"spread '{ref_id}' {where} block '{kind}' has no role "
                    f"'{role}' (roles: {sorted(allowed)})"
                )
        for role, val in roles.items():
            at = _list_shaped_entry(val)
            if at is not None:
                issues.append(
                    f"spread '{ref_id}' {where} block '{kind}' role '{role}': "
                    f"entry [{at}] is a LIST of {len(val[at])} blocks — each entry "
                    f"must be ONE block. Wrap the group in a section: "
                    f"{{block: section, roles: {{blocks: [...]}}}}"
                )
        for name, val in knobs.items():
            enum = defn["knobs"].get(name)
            if enum is None:
                issues.append(
                    f"spread '{ref_id}' {where} block '{kind}' has no knob '{name}'"
                )
            elif isinstance(val, str) and val.startswith("$view."):
                # Already refused by the enum check below, but silently: an author
                # reaching for a live presentation switch deserves the REASON and the
                # fix, not just "not in [...]". Knobs are read at COMPILE
                # (`knobValue`), so a cell in a knob slot could never update.
                issues.append(
                    f"spread '{ref_id}' {where} knob '{name}'='{val}' — a knob is read "
                    f"at COMPILE time, so it cannot follow a view cell. Bind the "
                    f"live value to a ROLE instead (e.g. trendChart "
                    f"roles.mode: $view.<cell>); knobs stay literal {list(enum)}"
                )
            elif _normalize_knob(val) not in enum:
                # Render a rejected value so it can't READ as an accepted one. A
                # raw boolean printed as ``'false' not in ['false', 'true']`` is a
                # flat contradiction, and the author — an agent especially — cannot
                # act on it: the fix it reads off the message is what it just
                # wrote. Booleans coerce above, so this now fires only on a value
                # that is genuinely wrong.
                shown = f"'{val}'" if isinstance(val, str) else f"{val!r} ({type(val).__name__})"
                issues.append(
                    f"spread '{ref_id}' {where} knob '{name}'={shown} not in {list(enum)}"
                )
        # A nested `view:` used to be REFUSED here, and correctly: the frontend
        # validator accepted one while the renderer dropped it, because a container's
        # compiler called `compileBlock(b.block, {roles, knobs})` with no view. A
        # refusal is the only non-misleading answer to a reshape nothing runs.
        #
        # The containers now pass `view: b.view` through, so the ops reach
        # `attachView` exactly as a top-level block's do — including inside a repeat,
        # where the nested list is bound `$item.<field>` and `candidatePaths` already
        # matches an explicit `$`-path against that repeat's own `over`. So the same
        # gate applies at every depth, and the `nested` flag no longer changes the
        # verdict. Pinned by `tests/e2e/test_spread_nested_gate.py` (here) and
        # `entityCards.view.test.tsx` (the render side).
        issues.extend(_gate_view(kind, view, defn, ref_id, where, raw_blocks))
        # Literal-label trap: a role that renders VERBATIM bound to a bare field key
        # that ALSO exists on the value → the agent meant the field's text, but the
        # label prints the key name. Only when the value's keys are known
        # (return_keys), and only for a bare identifier that matches a key (a real
        # label like "Verified purchase" has a space and never matches) — so the
        # trigger is tight (no false rejects of legitimate label text).
        for role in LITERAL_ROLES.get(kind, frozenset()):
            v = roles.get(role)
            if isinstance(v, str) and return_keys and v in return_keys and v.isidentifier():
                issues.append(
                    f"spread '{ref_id}' {where} block '{kind}' role '{role}' is a "
                    f"LITERAL label (rendered verbatim), but you bound field key "
                    f"'{v}' — it will print '{v}'; pass the label TEXT itself"
                )
        # Literal-`$` trap: on a role the catalog types `literal`, a leading `$` is
        # never indirection — it is the value the author MEANT (`currency: '$'`),
        # silently resolved as a data path. `'$'` returns the whole root and
        # stringifies to `[object Object]`; `'$172'` reads `root['172']` and comes
        # back blank. Neither errors anywhere, which is why this is an ISSUE (the
        # agent retries) and not a design note (advice it may ignore).
        #
        # The rule is NOT "no `$` on a literal role": `currency: '$.dollar'` with
        # `dollar: '$'` on the value is the SANCTIONED fix and production templates
        # already use it. Only a MALFORMED path is refused.
        #
        # This is the runtime twin of frontend B6, which decides the same class over
        # repo SOURCE — and therefore never sees a spec `render_spread` composed in
        # a chat turn, which is the path the bug actually shipped on. Unlike
        # LITERAL_ROLES above (hand-curated because `role_kind` returning None means
        # "unknown", not "not literal"), this asks for an EXPLICIT `literal`, so the
        # derived map is exactly the right source: an unclassified role stays silent.
        for role, v in roles.items():
            if not isinstance(v, str) or not _MALFORMED_PATH.match(v):
                continue
            if (catalog.role_kind(kind, role) or {}).get("kind") != "literal":
                continue
            renders = (
                "resolves to the whole root and renders '[object Object]'"
                if v in ("$", "$item")
                else f"resolves to root['{v[1:]}'] and renders blank"
            )
            issues.append(
                f"spread '{ref_id}' {where} block '{kind}' role '{role}'='{v}' reads "
                f"as a data PATH, not the literal text — it {renders}. Put the text "
                f"on the value and bind it: value {{\"symbol\": \"{v}\"}} + "
                f"role '{role}': '$.symbol'"
            )
        # Array-role trap: a role the catalog types `array` takes the schema
        # INLINE — `dataGrid.columns` is the column list itself, not a field key
        # pointing at one. Bind a string and the block iterates a string: no
        # columns compile, the grid renders empty, and `status: ready` says it
        # worked. Measured on a live turn — the agent bound the table's TITLE to
        # `columns` and the user got a blank pane with nothing anywhere saying so.
        #
        # `array` is an EXPLICIT positive kind, which is the only kind safe to
        # build on (see `app/spreads/CLAUDE.md` → roleKinds): it is the prop's
        # declared TS type, not an inference off how the block roots the role, so
        # `None` never reaches here. There are exactly THREE such roles in the
        # catalog (chartLegend.items · dataGrid.columns · stackedBar.keys), and
        # the shipped corpus was swept before this was written: its only non-list
        # bindings are `$` slot/box refs, resolved to a real list before render —
        # hence the `$` exemption, which is the same shape the literal-`$` gate
        # sanctions rather than a hole punched to make a test pass.
        for role, v in roles.items():
            if (catalog.role_kind(kind, role) or {}).get("kind") != "array":
                continue
            if isinstance(v, list) or (isinstance(v, str) and v.startswith("$")):
                continue
            issues.append(
                f"spread '{ref_id}' {where} block '{kind}' role '{role}' takes the "
                f"schema INLINE (a list), but you bound "
                f"{type(v).__name__} {v!r} — it will render nothing. Write the list "
                f"itself, e.g. '{role}': [{{\"key\": \"name\", \"label\": \"Name\"}}]"
            )
        issues.extend(
            _field_path_issues(kind, roles, ref_id, where, return_keys, output_fields)
        )
    return issues


# Dot-path tail segments the resolver treats specially (mirror
# ``doughs.validation.drill._SPECIAL_DRILL`` + numeric indices) — never object
# field names, so the FIELD-path tail check must not flag them.
_SPECIAL_TAIL = {"length", "count"}


def _gate_view_cell(
    val: Any,
    spread_blocks: list[dict[str, Any]] | None,
    ref_id: str,
    at: str,
    arg: str,
    issues: list[str],
) -> None:
    """A `$view.<cell>` op arg must name a control the SAME spread renders.

    The input-side twin of the anchor rule: an explicit reference has to resolve,
    or the op silently reads an argument nothing can ever fill. `$view.` is also
    FLAT — a cell holds a scalar, so `$view.a.b` has nothing to descend into."""
    if not (isinstance(val, str) and val.startswith("$view.")):
        return
    cell = val[len("$view."):]
    if not cell or "." in cell:
        issues.append(
            f"spread '{ref_id}' {at} arg '{arg}'='{val}' — a view-cell ref is "
            f"'$view.<cell>' with no dots (a cell holds a single value)"
        )
        return
    if spread_blocks is not None and viewops.resolve_cell(cell, spread_blocks) is None:
        issues.append(
            f"spread '{ref_id}' {at} arg '{arg}'='{val}' names a control the spread "
            f"does not render — add a control block (one of "
            f"{sorted(viewops.CONTROL_BLOCKS)}) with roles.name '{cell}'"
        )


def _gate_view(
    kind: str,
    view: Any,
    defn: catalog.BlockDef,
    ref_id: str,
    where: str,
    spread_blocks: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Gate a block's ``view:`` ops — the pure reshapes applied to its own list.

    Checks only what is CHECKABLE from the artifact: the block actually has a list
    to reshape, the op name is known, and its argument keys are the op's. The
    per-item FIELD names inside those args (``sort.by``, ``filter.where``) are
    deliberately NOT checked — the backend only knows a dough's TOP-LEVEL output
    fields, so gating a per-item key against them would false-reject every valid
    op. That check is a non-blocking design-lint note instead.

    Every message enumerates its legal set, so an authoring agent can self-correct
    off the error alone (the property the block/knob gates above already have)."""
    issues: list[str] = []
    if not view:
        return issues
    if not isinstance(view, list):
        return [f"spread '{ref_id}' {where} 'view' must be a list of ops"]

    list_role = defn.get("listRole")
    if not list_role:
        return [
            f"spread '{ref_id}' {where} block '{kind}' takes no 'view' ops — it has "
            f"no list to reshape (blocks that do: {sorted(catalog.viewable_kinds())})"
        ]

    for j, op in enumerate(view):
        at = f"{where}.view[{j}]"
        if not isinstance(op, dict) or len(op) != 1:
            issues.append(
                f"spread '{ref_id}' {at} must be a single-key mapping "
                f"'{{<op>: {{args}}}}' (ops: {list(viewops.op_names())})"
            )
            continue
        name, args = next(iter(op.items()))
        spec = viewops.OP_DEFS.get(name)
        if spec is None:
            issues.append(
                f"spread '{ref_id}' {at} unknown op '{name}' "
                f"(ops: {list(viewops.op_names())})"
            )
            continue
        if not isinstance(args, dict):
            issues.append(f"spread '{ref_id}' {at} op '{name}' args must be a mapping")
            continue
        allowed = set(spec["required"]) | set(spec["optional"])
        for key in spec["required"]:
            if args.get(key) in (None, ""):
                issues.append(
                    f"spread '{ref_id}' {at} op '{name}' requires '{key}' "
                    f"(args: {sorted(allowed)})"
                )
        for key in args:
            if key not in allowed:
                issues.append(
                    f"spread '{ref_id}' {at} op '{name}' has no arg '{key}' "
                    f"(args: {sorted(allowed)})"
                )
        for key, val in args.items():
            _gate_view_cell(val, spread_blocks, ref_id, at, key, issues)
        for key, enum in viewops.OP_KNOBS.get(name, {}).items():
            val = args.get(key)
            if val is not None and val not in enum:
                issues.append(
                    f"spread '{ref_id}' {at} op '{name}' arg '{key}'='{val}' "
                    f"not in {list(enum)}"
                )
    return issues


def _role_field_path(val: Any) -> str | None:
    """The FIELD-path string a block role head-checks against, or ``None`` to skip.

    Three role-value shapes reach here:

    - a **plain dotted string** (``answer``, ``result.answer``, ``segments``) — the
      value IS the field path; return it;
    - a **statBand-style meta dict** — the list lives in the ``over`` sub-key
      (``{over, label, value}``, see the frontend ``statBand.ts`` ``StatsBinding``),
      so the real field path is ``over``; unwrap it and treat it as the string case;
    - anything else — an empty/absent value, a ``$``-label (a display ref, not a
      data read), a dict without a usable ``over`` — is NOT a field path → skip.

    A ``$``-prefixed path is skipped in BOTH the plain and the ``over`` case: the
    frontend ``rootKey`` passes an explicit ``$…`` through un-rooted, so its head
    is an intentional root path, not a bare return key — head-checking it would
    false-reject.
    """
    if isinstance(val, dict):
        val = val.get("over")  # statBand meta shape: the list path lives at `over`
    if not isinstance(val, str) or not val or val.startswith("$"):
        return None
    return val


def _field_path_issues(
    kind: str,
    roles: dict,
    ref_id: str,
    where: str,
    return_keys: frozenset[str] | None,
    output_fields: dict[str, set[str] | None] | None,
) -> list[str]:
    """Donut-snapshot FIELD-path gate — the ``Dough.spread`` empty-card guard.

    A ``Dough.spread`` block role that is a FIELD PATH (a plain dotted string, or
    the ``over`` sub-key of a statBand meta dict — see :func:`_role_field_path`;
    never a ``$``-label) reads a value off ``donut.output`` at paint time; if its
    HEAD segment is not a return-block key the app renders a blank card. Only runs
    when the caller threads the dough's ``return_`` keys
    (:func:`composition_spec`).

    **Scope: ``field_roles`` ∪ every role the catalog types explicitly ``rootPath``.**
    The `field_roles` half is the emit's own "this is a data binding" set. The
    `rootPath` half was added because the two disagree and the gap ate a real bug:
    ``section.title`` is `rootPath` and is NOT a field role, so a static
    ``title: Search`` was skipped as "conservatively a literal" — and then
    ``section.ts`` compiled it through ``rootKey()`` into ``$.Search``, read nothing,
    and rendered an untitled card with no error anywhere. Measured in the app.

    A `rootPath` role CANNOT hold literal text — that is what the kind means — so
    there is no conservative reading to preserve for it, and no valid label to
    false-reject. Note this asks for an EXPLICIT positive kind, per the
    ``roleKinds`` rule in ``CLAUDE.md``: ``None`` means UNCLASSIFIED, so an
    unclassified role stays skipped exactly as before.

    (The sibling trap points the other way and is handled by ``LITERAL_ROLES``
    above: a role that renders VERBATIM bound to a field KEY prints the key name.
    Same author error, opposite direction, so the two checks must not be merged.)"""
    if not return_keys:
        return []
    issues: list[str] = []
    # The union lives in `catalog.path_roles_for` because `block_guide` TEACHES
    # the same set — computing it here and nowhere else is what let the gate
    # enforce a rule the language's own catalogue never stated.
    for role in sorted(catalog.path_roles_for(kind)):
        val = _role_field_path(roles.get(role))
        if val is None:
            continue  # absent / literal / $-label → not a field path
        head, _, rest = val.partition(".")
        if head not in return_keys:
            # NAME THE REMEDY, not just the defect. Measured: handed only the
            # defect half of this message, the agent diagnosed it exactly right
            # ("that title slot points at a data field, not fixed text") and then
            # DELETED the two `section` blocks, because it did not know a static
            # title is expressible at all — it reported back that "there is no
            # clean way". The rule was understood and the feature was lost, which
            # is a message defect, not a model one.
            #
            # The literal-`$` gate below is the pattern: it prints the exact
            # value + role pair to write. So does this now.
            issues.append(
                f"spread '{ref_id}' {where} block '{kind}' role '{role}: {val}' "
                f"does not resolve — '{head}' is not a return-block key "
                f"(keys: {sorted(return_keys)}); a bare field reads the output "
                f"root and paints a blank card. This role reads a PATH, so fixed "
                f"text cannot go here and a box.yaml `$`-ref will not help either "
                f"(the loader resolves it to the text first, and that text is then "
                f"read as a path). To show a constant, put it ON THE VALUE: add "
                f"`{role}_text: {val}` there and bind `{role}: {role}_text` "
                f"(for a dough's own spread, 'there' is its `return:`)"
            )
            continue
        # Dotted tail — gate against the output's model/schema fields when known.
        if rest and output_fields:
            tail = rest.partition(".")[0]
            fields = output_fields.get(head)
            if (
                fields is not None
                and tail not in fields
                and tail not in _SPECIAL_TAIL
                and not tail.isdigit()
            ):
                issues.append(
                    f"spread '{ref_id}' {where} block '{kind}' role '{role}: {val}' "
                    f"— '{tail}' is not a field of output '{head}' "
                    f"(fields: {sorted(fields)})"
                )
    return issues


def _rows_at(value: Any, path: str) -> list | None:
    """The list a rootPath role names, or ``None`` when the path reaches no list.

    ``None`` is a SKIP, not a finding: a role can legitimately name a list that
    this particular value has not filled yet (a staged beat), and a guard that
    refused an empty render would refuse the loading state.
    """
    cur: Any = value
    for seg in path.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return None
        cur = cur[seg]
    return cur if isinstance(cur, list) else None


def item_shape_issues(blocks: Any, value: Any) -> list[str]:
    """The VALUE gate — do the rows carry the sub-fields each block reads?

    ★ EVERY OTHER SPREAD CHECK IS SPEC-vs-CATALOG, so a role bound to a field the
    data does not carry is legal, silent, and BLANK. Measured: a primer bound
    ``keyPoints`` over items shaped ``{label, detail}``; the block reads ``.text``
    off each row, three sections rendered empty, and every gate passed. The
    grammar gate says so itself — "B9 renders the EMPTY STATE — refuses nothing".

    This is the half that needs the value, which is why it lives here and runs at
    RENDER, where both halves are in hand for the first time.

    Refuses only what it can prove. A role is checked when the catalog knows it
    reads off the item (``kind: itemPath``) AND the block's list role resolves to
    a non-empty list of dicts. It then reads the bound field — or, unbound, the
    block's own default, which is the case that has no spec to blame and would
    otherwise be uncheckable. A field absent from EVERY row is the finding; one
    row missing it is sparse data, not a mis-binding.
    """
    issues: list[str] = []
    for b in walk_block_dicts(blocks):
        kind = b.get("block")
        roles = b.get("roles") or {}
        if not isinstance(kind, str) or not isinstance(roles, dict):
            continue
        list_role = next(
            (r for r in catalog.roles_for(kind)
             if (catalog.role_kind(kind, r) or {}).get("shape") == "list"), None)
        if list_role is None:
            continue
        path = _role_field_path(roles.get(list_role))
        rows = _rows_at(value, path) if path else None
        rows = [r for r in rows if isinstance(r, dict)] if rows else []
        if not rows:
            continue
        required = catalog.required_for(kind)
        for role in sorted(catalog.roles_for(kind)):
            meta = catalog.role_kind(kind, role) or {}
            if meta.get("kind") != "itemPath":
                continue
            bound = roles.get(role)
            # REQUIRED, or explicitly BOUND. An unbound OPTIONAL role whose default
            # field is missing is usually correct authoring: `keyPoints.glyph`
            # degrades to the `icon` knob, and refusing it would fire on every block
            # that simply does not use its decoration. The catalog cannot tell a
            # decorative role from a content one, so under-coverage is the safe
            # direction — the same rule the emitter states for `shape`.
            explicit = isinstance(bound, str) and bound != ""
            if not explicit and role not in required:
                continue
            field = bound if explicit else meta.get("default")
            # No known default, or a `$` ref (a label, not a data read) — nothing
            # to check.
            if not isinstance(field, str) or not field or field.startswith("$"):
                continue
            if any(field in r for r in rows):
                continue
            have = sorted({k for r in rows[:8] for k in r})[:8]
            issues.append(
                f"block '{kind}' role '{role}' reads '{field}' off each item of "
                f"'{path}', and no row carries it — rows have {have}"
                + ("" if bound else f" (unbound, so it defaults to '{field}')"))
    return issues


def root_fields(layout: Any) -> set[str]:
    """Every ROOT field an authored composition reads — the head of each
    field-role path, containers included.

    The one place that answers "what must a value carry for this layout to draw",
    so a caller checking a value against a spread reads the same roles the render
    gate does. Conservative by construction, and deliberately: only roles the
    catalog calls FIELD roles count (a ``searchBox``'s ``name`` is a control
    IDENTITY, not a read), and an explicit ``$…`` path is skipped for the reason
    ``_role_field_path`` gives — the frontend passes it through un-rooted, so its
    head is not a bare return key. Under-reporting yields a check that misses a
    mismatch; over-reporting yields one that cries about a working spread.
    """
    from app.spreads import catalog

    field_roles = catalog.FIELD_ROLES
    out: set[str] = set()
    for blk in walk_block_dicts(layout):
        allowed = field_roles.get(blk.get("block"), frozenset())
        for role, val in (blk.get("roles") or {}).items():
            if role not in allowed:
                continue
            path = _role_field_path(val)
            if path:
                out.add(path.split(".")[0])
    return out
