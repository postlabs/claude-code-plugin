"""Surface/dough-agnostic spark validation — the TRIGGER-MAP gate.

Gate the ``on:`` maps a frozen composition's blocks carry. The structural twin of
``app/spreads/validate.py``: ``spark_spec`` mirrors ``composition_spec``, and
``_gate_block_spark`` mirrors ``_gate_blocks``' body.

★ **THE HOST IS LEXICAL NOW, SO MOST OF THIS GATE IS GONE.** A spark used to be a
flat ``interactions:`` list whose ``anchor: $rowList.row`` had to RESOLVE against
the layout — and could miss four ways (``absent`` / ``ambiguous`` /
``no_row_scope`` / ``unknown_segment``), each needing its own remedy sentence. The
map is declared ON the block it drives, so three of those are unreachable: the
block is right here, it cannot be missing, and it cannot be two. Only the
CAPABILITY question survives, and it is asked of the host's own kind.

Gone with them: the whole ``interaction_defs`` module (the per-effect models ARE
the contract, and its ``CONTROL_BLOCKS`` was a pass-through to
``app.spreads.viewops``, which this now imports directly), the gesture-collision
pass (a map cannot hold two ``press`` keys), and the one-read-per-block pass (nor
two ``refresh`` keys).

What is left is exactly the checks needing a fact from OUTSIDE the block, threaded
in by the caller and never imported — the identical seam ``composition_spec`` uses
for ``return_keys``/``output_fields``:

- ``target_inputs`` — each ``act`` target's declared inputs, so the datum mapping
  can be checked (key ∈ the target's inputs; every required input bound);
- ``source_consequence`` — the OWNING dough's risk tier, so a ``read`` is held to
  a side-effect-free source (the CQRS split).

This keeps ``app.spreads.spark`` a leaf: it imports its own ``model``/``anchor``/
``capability`` plus the block catalog, and memo and doughs import it downward.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.spreads import catalog, viewops
from app.spreads.spark import anchor, capability
from app.spreads.spark.model import ActEffect, BlockSpark, NavEffect, OpenEffect, ReadEffect

#: The one source tier a ``read`` may re-call — the query side of the CQRS split.
#: A read that could mutate is not a read. A literal, not an import, so this stays
#: a leaf.
READ_SAFE_CONSEQUENCE = "read_only"


@dataclass(frozen=True)
class TargetInputs:
    """The declared-input facts of one target dough, threaded in by the caller
    (mirrors how ``output_fields`` is a threaded set-map, NOT a doughs import).
    ``all`` = every declared input key; ``required`` = the genuinely must-provide
    subset (required AND no fixed value AND no default)."""

    all: frozenset[str]
    required: frozenset[str]


def _first_fault(exc: ValidationError) -> str:
    """The model's own message, unwrapped.

    ``BlockSpark`` classifies the fault BEFORE pydantic's union does, so its
    ``ValueError`` is the useful line; reporting pydantic's union noise instead
    would name the wrong effect (``{open, gate}`` comes back as a missing ``act``).
    """
    for err in exc.errors():
        msg = str(err.get("msg", ""))
        if msg.startswith("Value error, "):
            return msg[len("Value error, "):]
    errs = exc.errors()
    if errs:
        loc = ".".join(str(x) for x in errs[0].get("loc", ()))
        return f"{loc}: {errs[0].get('msg', 'invalid')}"
    return "invalid `on:` map"


def spark_spec(
    spec: dict[str, Any],
    ref_id: str,
    *,
    target_inputs: dict[str, TargetInputs] | None = None,
    source_consequence: str | None = None,
) -> list[str]:
    """Gate every ``on:`` trigger map in a frozen composition.

    Walks the containment TREE, so a map on a block inside a ``section``/``tabs``
    is gated where it sits — the same walk the composition gate makes, which is
    why a nested block is not a special case here either.
    """
    blocks = spec.get("blocks")
    if not isinstance(blocks, list):
        return [f"spark '{ref_id}' has no 'blocks' to carry a trigger map"]
    issues: list[str] = []
    submitters: dict[str, list[str]] = {}
    for hit in anchor.walk_blocks(blocks):
        on = hit.block.get("on")
        if on is None:
            continue
        where = _path_label(hit.path)
        kind = str(hit.block.get("block") or "")
        try:
            spark = BlockSpark.model_validate(on)
        except ValidationError as exc:
            issues.append(f"spark '{ref_id}' {where} {_first_fault(exc)}")
            continue
        for name in _controls_submitting(spark):
            submitters.setdefault(name, []).append(where)
        issues.extend(
            _gate_block_spark(
                spark, kind, hit.block, blocks, ref_id, where,
                target_inputs, source_consequence,
            )
        )
    issues.extend(_gate_one_control_one_read(submitters, ref_id))
    return issues


def _controls_submitting(spark: BlockSpark) -> list[str]:
    """The controls this block's ``search`` is submitted BY."""
    if spark.search is None:
        return []
    return [
        name
        for v in spark.search.params.values()
        if isinstance(v, str) and (name := anchor.parse_control_path(v)) is not None
    ]


def _gate_one_control_one_read(
    submitters: dict[str, list[str]], ref_id: str
) -> list[str]:
    """One control cannot submit two blocks' searches.

    The binder stamps ``controlEffect`` on the named control, and that is ONE
    slot: a second search naming the same box overwrites the first, which then
    has no trigger at all — a ``search`` claims no footer to fall back on. So the
    loser is not degraded, it is unreachable, and nothing at render says so.

    Cross-block by nature, which is why it sits here and not in
    ``_gate_block_spark``: the collision is between two blocks' maps, and neither
    is wrong on its own.
    """
    return [
        f"spark '{ref_id}' control '{name}' is named by {len(wheres)} searches "
        f"({', '.join(wheres)}) — a control submits ONE read (it carries a single "
        f"`controlEffect`), so the others would never fire; give each its own "
        f"control, or fold them into one search"
        for name, wheres in sorted(submitters.items())
        if len(wheres) > 1
    ]


def _gate_block_spark(
    spark: BlockSpark,
    kind: str,
    block: dict[str, Any],
    blocks: list[dict[str, Any]],
    ref_id: str,
    where: str,
    target_inputs: dict[str, TargetInputs] | None,
    source_consequence: str | None,
) -> list[str]:
    """One block's map: can this block HOST these triggers, and is each effect's
    own binding sound."""
    issues: list[str] = []

    # ── capability: the only anchor question that survived the move ──────────
    rows = spark.row_effects()
    if rows and not anchor.row_scopes(kind):
        issues.append(
            f"spark '{ref_id}' {where} block '{kind}' renders no pressable ROW, so "
            f"{sorted(rows)} can never fire — a per-row effect needs a block whose "
            f"compiler emits one node per record: {sorted(anchor.anchorable_kinds())}"
        )
    if spark.refresh and "readTrigger" not in catalog.roles_for(kind):
        # The binder STAMPS `readTrigger` on this block, and the renderer refuses a
        # bound role the block does not declare — refusing the WHOLE surface, not
        # the one role. Without this the failure is: saves clean, then renders a
        # ValidationPanel citing a role the author never wrote.
        #
        # `search` is exempt because its trigger is the CONTROL, not a footer: the
        # binder stamps `controlEffect` on the searchBox and nothing on this block.
        # Holding a search to the footer's host set refused the one composition it
        # exists for — a list that is only ever driven by a keyword box.
        issues.append(
            f"spark '{ref_id}' {where} block '{kind}' hosts no refresh control — "
            f"blocks that do: {sorted(capability.hosts_for('readHost'))}"
        )

    for trigger, effect in (
        ("press", spark.press),
        ("contextmenu", spark.contextmenu),
        ("refresh", spark.refresh),
        ("search", spark.search),
    ):
        if effect is None:
            continue
        at = f"{where} on.{trigger}"
        if isinstance(effect, ActEffect):
            _gate_act(effect, blocks, ref_id, at, target_inputs, issues)
        elif isinstance(effect, NavEffect):
            _gate_nav(effect, ref_id, at, target_inputs, issues)
        elif isinstance(effect, OpenEffect):
            _gate_open(effect, ref_id, at, issues)
        elif isinstance(effect, ReadEffect):
            _gate_read(effect, trigger, block, blocks, ref_id, at, source_consequence, issues)
    return issues


def _gate_act(
    effect: ActEffect,
    blocks: list[dict[str, Any]],
    ref_id: str,
    at: str,
    target_inputs: dict[str, TargetInputs] | None,
    issues: list[str],
) -> None:
    """The datum mapping, and where the result lands."""
    _gate_target_inputs(effect.act, effect.inputs, ref_id, at, target_inputs, issues)
    if effect.into is None or effect.into == "self":
        return
    parsed = anchor.parse_anchor(effect.into)
    if parsed is None or parsed.scope != "block":
        issues.append(
            f"spark '{ref_id}' {at} into='{effect.into}' — must be 'self' (a slot "
            f"under the pressed row) or a '$<block>' sibling ref"
        )
        return
    landed = anchor.resolve_anchor(parsed, blocks)
    if isinstance(landed, anchor.AnchorMiss):
        # `into` still NAMES a second block, so it keeps the ambiguity split the
        # trigger map deleted for hosts: "add the block" and "name one of the two"
        # want opposite fixes.
        if landed.reason == "ambiguous":
            seen = ", ".join(_path_label(h.path) for h in landed.hits)
            issues.append(
                f"spark '{ref_id}' {at} into '{effect.into}' is AMBIGUOUS — the "
                f"spread renders {len(landed.hits)} matching blocks ({seen}); give "
                f"the one you mean a `name:` and land on that"
            )
        else:
            issues.append(
                f"spark '{ref_id}' {at} into '{effect.into}' does not resolve to a "
                f"block in this spread (blocks: {_kinds_in(blocks)})"
            )


def _gate_nav(
    effect: NavEffect,
    ref_id: str,
    at: str,
    target_inputs: dict[str, TargetInputs] | None,
    issues: list[str],
) -> None:
    """A ``nav`` bakes its target with the row's fields; the target's own anchored
    spread resolves the surface. Only the input mapping is checkable here — the
    identical gate an ``act`` binding gets (key ∈ the target's inputs, each value a
    datum/selection/envelope ref or literal, every required input bound). There is
    no ``into`` to resolve: the landing is a new surface."""
    _gate_target_inputs(effect.nav, effect.inputs, ref_id, at, target_inputs, issues)


def _gate_open(effect: OpenEffect, ref_id: str, at: str, issues: list[str]) -> None:
    """``open`` reads the row's OWN link — a ``$.<field>`` datum path, never a
    literal URL (a per-row open that ignored the row would be a link, not a row
    effect)."""
    if anchor.parse_data_path(effect.open) is None:
        issues.append(
            f"spark '{ref_id}' {at} open='{effect.open}' must be a '$.<field>' "
            f"datum path off the pressed row (the row's URL)"
        )


def _gate_read(
    effect: ReadEffect,
    trigger: str,
    block: dict[str, Any],
    blocks: list[dict[str, Any]],
    ref_id: str,
    at: str,
    source_consequence: str | None,
    issues: list[str],
) -> None:
    """A read re-bakes the spread's OWN source, so that source must be
    side-effect-free; and an ``append`` fold needs a flat list key."""
    if trigger == "search" and not any(
        isinstance(v, str) and anchor.parse_control_path(v) is not None
        for v in effect.params.values()
    ):
        # `search` IS "a control submits this read" — the binder wires it by
        # stamping `controlEffect` on the control a `$control.` param names, and
        # stamps no footer. So a search naming no control has no trigger at all:
        # it saves clean and renders a list nothing can ever re-fetch. `refresh`
        # is the key for a read the footer button fires.
        issues.append(
            f"spark '{ref_id}' {at} is a `search:` but no param reads a control — "
            f"a search is submitted BY a control, so bind one "
            f"(params: {{<input>: $control.<name>}}) or use `refresh:` for a "
            f"footer-fired read"
        )
    if source_consequence is not None and source_consequence != READ_SAFE_CONSEQUENCE:
        issues.append(
            f"spark '{ref_id}' {at} read re-calls this spread's own source, which "
            f"declares '{source_consequence}' — a read must re-call a "
            f"side-effect-free source ('{READ_SAFE_CONSEQUENCE}'), the query half "
            f"of the CQRS split; a press that CHANGES something is an `act`"
        )
    _gate_read_params(effect, ref_id, at, issues, blocks)
    _gate_append_list_key(effect, block, ref_id, at, issues)


def _path_label(path: tuple[int | str, ...]) -> str:
    """A containment path as something an author can find in their own file:
    ``(1, 'blocks', 0)`` → ``layout[1].blocks[0]``. Written out rather than printed
    as a tuple because the point of the message is that they go look at it."""
    out = f"layout[{path[0]}]" if path else "layout"
    for seg in path[1:]:
        out += f"[{seg}]" if isinstance(seg, int) else f".{seg}"
    return out


def _kinds_in(spread_blocks: list[dict[str, Any]]) -> list[str]:
    """The block kinds this spread actually renders — the legal set an ABSENT
    miss names, so the author corrects against what is there instead of
    re-guessing."""
    return sorted({
        k for h in anchor.walk_blocks(spread_blocks)
        if (k := str(h.block.get("block") or ""))
    })


def _gate_target_inputs(
    target: str,
    inputs: dict[str, Any],
    ref_id: str,
    where: str,
    target_inputs: dict[str, TargetInputs] | None,
    issues: list[str],
) -> None:
    """The press-gesture input-mapping gate, shared by ``act`` and ``nav`` (both
    bake a TARGET dough with the row's fields): each mapped key ∈ the target's
    declared inputs, each value a ``$.<datum-path>``, every genuinely-required
    target input bound. Skipped when the caller threads no ``target_inputs`` (e.g.
    the target isn't resolvable), mirroring the storeless field-path skip."""
    for key, val in inputs.items():
        # Four shapes, and the last two were REFUSED until this gate first ran over
        # the shipped spreads:
        #   `$.<field>`         the CLICKED row (press-to-bake)
        #   `$selection.<field>`the SELECTED row (master-detail, §17)
        #   `$value.<path>`     the ENVELOPE the row sits in — `account: $value.account`
        #                       is "cancel THIS order, for THAT account", and three
        #                       shipped spreads bind it
        #   a LITERAL           a constant the target needs (`confirm: 'true'`)
        #
        # A jar spread is copied into the profile, never validated on the way, so
        # this gate had never seen one: the two shapes it refused had been shipping
        # the whole time. The row paths alone were never the contract — `read.params`
        # has allowed literals and `$value.` since it was written, and an act's
        # inputs are the same kind of argument list.
        if not isinstance(val, str) or not val.startswith("$"):
            continue  # a literal constant — nothing to resolve
        ok = (
            anchor.parse_data_path(val) is not None
            or anchor.parse_selection_path(val) is not None
            or anchor.parse_result_path(val) is not None
        )
        if not ok:
            issues.append(
                f"spark '{ref_id}' {where} inputs['{key}']='{val}' must be a "
                f"'$.<field>' (clicked row), '$selection.<field>' (selected row) or "
                f"'$value.<path>' (the envelope) ref — or a bare literal"
            )
    if target_inputs is None or target not in target_inputs:
        return  # target facts not threaded — the key/coverage check is skipped
    tgt = target_inputs[target]
    for key in inputs:
        if key not in tgt.all:
            issues.append(
                f"spark '{ref_id}' {where} inputs['{key}'] is not a declared "
                f"input of target '{target}' (inputs: {sorted(tgt.all)})"
            )
    for req in tgt.required:
        if req not in inputs:
            issues.append(
                f"spark '{ref_id}' {where} required input '{req}' of target "
                f"'{target}' is not bound"
            )


def _gate_append_list_key(
    effect: "ReadEffect",
    block: dict[str, Any],
    ref_id: str,
    where: str,
    issues: list[str],
) -> None:
    """``mode: append`` requires the anchored block's list role to be a FLAT
    top-level output key.

    The fold concatenates by looking the list up with a SINGLE-KEY lookup on the
    new output (``Spark.tsx::foldRead``: ``output[itemsKey]``, where ``itemsKey``
    is the block's bound list role). A dotted role — ``items: result.rows`` — is
    read as one literal key, finds nothing, fails the ``Array.isArray`` test, and
    the fold falls through to its REPLACE branch. Load-more then overwrites the
    list it was asked to extend, silently: no error, no warning, and the button
    keeps working. The page just stops growing.

    Provable from the artifact alone, which is why this is an error and not a
    lint note — no data shape makes ``output["result.rows"]`` resolve, so there is
    no legitimate authoring this refuses. Recorded independently by the author of
    the first shipped load-more app (``<handle>.cp_review_browser``'s spread comment)
    after paying for it once.

    Only gated for ``append``: a ``replace`` read swaps the whole value and never
    consults the list key, so a nested role is merely unusual there, not broken.
    """
    if effect.read != "append":
        return
    kind = str(block.get("block") or "")
    # Read the role the FOLD reads, which is the literal `items` role — not the
    # catalog's `listRole`. They are usually the same and it is tempting to ask
    # the catalog, but `Spark.tsx::itemsKeyFor` hardcodes `roles.items`, and a
    # block can render a list (and a load-more footer) while declaring no
    # `listRole` at all: `cardList` does exactly that. Keying on the catalog
    # made this gate skip such blocks SILENTLY — measured on an agent-authored
    # `cardList` searcher that appended through a role no gate was looking at.
    # A gate must read the same field as the runtime it speaks for.
    # `resolved.block` is the block itself, not an index into the top level — the
    # anchored block may be nested inside a `section`, where an index would address
    # a different list entirely.
    key = (block.get("roles") or {}).get("items")
    if isinstance(key, str) and "." in key:
        issues.append(
            f"spark '{ref_id}' {where} mode 'append' needs block '{kind}' role "
            f"'items: {key}' to be a FLAT output key — the fold looks the "
            f"list up by that key alone, so a dotted path finds nothing and "
            f"silently REPLACES instead of appending; return the list at the top "
            f"level and bind 'items: {key.rpartition('.')[2]}'"
        )


def _gate_effect_host(
    block_kind: Any,
    role: str,
    subject: str,
    what: str,
    ref_id: str,
    where: str,
    issues: list[str],
) -> None:
    """Refuse a binding whose host block cannot CARRY the role the binder stamps.

    The binder does not ask permission: it writes ``roles.<role>`` onto the block a
    binding names — ``readTrigger`` on a read's anchored block, ``controlEffect`` on
    the control a ``$control.`` param reads. The frontend spec validator then
    refuses any bound role outside the block's required∪optional set (R8), and it
    refuses the WHOLE spread, not the one role. So without this gate the failure
    mode is: saves clean, then renders as a ValidationPanel citing a role the author
    never wrote.

    Keyed on the CATALOG rather than a hand-kept list of capable kinds, because the
    catalog is the same artifact the frontend compiles from — the moment a block
    gains the role, this gate starts admitting it with no edit here. The LEGAL SET
    in the message routes through ``capability.hosts_for_role`` where the role maps
    to a capability, so ``controlEffect`` recommends the WIRED control set and not
    every declarer (``inputRequest`` declares it inert — ``viewops._NOT_WIRED``).

    Storeless in the same sense as the scope + ``on:`` guards: it needs only the
    block KIND, read over the one sanctioned ``app.spreads.spark → app.spreads`` edge."""
    if not isinstance(block_kind, str) or not block_kind:
        return
    if role in catalog.roles_for(block_kind):
        return
    # The legal set comes from the capability index when the role maps to one —
    # `controlEffect` in particular must recommend the WIRED control set, not
    # every declarer (`inputRequest` declares it and renders an inert form).
    capable = list(capability.hosts_for_role(role)) or sorted(
        k for k in catalog.block_kinds() if role in catalog.roles_for(k)
    )
    issues.append(
        f"spark '{ref_id}' {where} {subject} — block '{block_kind}' cannot {what}: "
        f"it declares no '{role}' role, and the binder stamping one would make the "
        f"whole spread refuse to render. Use one of {capable}"
    )


def _gate_read_params(
    effect: "ReadEffect",
    ref_id: str,
    where: str,
    issues: list[str],
    spread_blocks: list[dict[str, Any]] | None = None,
) -> None:
    """The ``read`` params gate: each value is a LITERAL (a non-string scalar, or a
    string with NO ``$`` prefix — a filter/sort constant), a ``$value.<path>`` ref
    (a path off the last output — a pagination cursor), or a ``$control.<name>``
    ref (the live value of a view control — a search keyword, design §20). A ``$.``
    ROW datum-path is rejected: a read triggers at block scope, so there is no
    pressed row. (A literal string that itself starts with ``$`` is unsupported —
    rare for a dough input value; flag it rather than pay an escape-syntax tax.)

    A ``$control.`` ref is additionally RESOLVED against the view when
    ``spread_blocks`` is threaded: the named control must exist, or the read fires
    with an argument nothing can ever fill. This is the same
    reference-must-resolve rule the anchor obeys — just on the input side."""
    params = effect.params
    for key, val in params.items():
        if not (isinstance(val, str) and val.startswith("$")):
            continue
        control = anchor.parse_control_path(val)
        if control is not None:
            if spread_blocks is not None:
                hit = anchor.resolve_control(control, spread_blocks)
                if isinstance(hit, anchor.ControlMiss):
                    # The two reasons want opposite fixes — a missing block vs a
                    # wrong name — and the old single message sent a typo
                    # hunting for a block that was rendering all along.
                    if hit.reason == "name_not_found" and hit.present:
                        issues.append(
                            f"spark '{ref_id}' {where} params['{key}']='{val}' — "
                            f"no control named '{control}': the spread's controls "
                            f"are named {sorted(set(hit.present))}; read one of "
                            f"those, or rename the control block's roles.name"
                        )
                    else:
                        issues.append(
                            f"spark '{ref_id}' {where} params['{key}']='{val}' names a "
                            f"control the spread does not render — add a control block "
                            f"(one of {sorted(viewops.CONTROL_BLOCKS)}) with "
                            f"roles.name '{control}'"
                        )
                else:
                    _gate_effect_host(
                        hit.block.get("block"),
                        "controlEffect",
                        f"params['{key}']='{val}'",
                        "submit a read",
                        ref_id,
                        where,
                        issues,
                    )
            continue
        if anchor.parse_result_path(val) is None:
            issues.append(
                f"spark '{ref_id}' {where} params['{key}']='{val}' — a read arg "
                f"must be a literal, a '$value.<path>' ref, or a '$control.<name>' "
                f"ref (a '$.' row datum-path is unavailable to a block-scoped read)"
            )
