"""The parsed spark — a TRIGGER MAP declared on the block that hosts it.

A **spark** is the controller half of a spread: what happens when you press a row,
right-click it, or hit refresh. It is authored ON the block, beside that block's
`roles:` and `view:`, because a controller has exactly the same inter-block
relation those do — none:

    - block: rowList
      roles: { items: trades, title: name }
      on:
        press:       { act: postlab.stocks.detail, inputs: { id: $.id }, into: self }
        contextmenu: { open: $.url }
        refresh:     { read: replace }

★ **THE TRIGGER IS THE KEY, AND THAT IS THE WHOLE DESIGN.** Three things fall out
of it that the previous shape had to enforce by hand:

- **A gesture cannot collide.** Two effects claiming one gesture used to be a
  save-time refusal (`_gate_row_gestures`); a map cannot hold two `press` keys, so
  the rule is now the grammar.
- **Scope is a TYPE, not an inference.** `press`/`contextmenu` take a gesture
  effect, `refresh` takes a read. A read under `press` is a parse error. Scope used
  to be derived from whether an anchor string carried a dotted segment
  (`Anchor.scope`), which meant every consumer re-derived it from text.
- **Three of the four anchor failures are unreachable.** `$rowList.row` had to
  RESOLVE — and could miss as `absent` / `ambiguous` / `no_row_scope` /
  `unknown_segment`. The host block is now lexically right here, so only the
  capability question survives, and it is answered against the block's own kind.
  (Measured, before: an agent burned 6 anchor guesses / 57.1s on `entityCards`.)

**Each effect is its own model, so the fields ARE the contract.** There used to be
one flat `Interaction` carrying the UNION of every effect's fields, plus a
hand-written `INTERACTION_DEFS` table saying which effect could use which — two
declarations of one rule, and the model's own docstring admitted "a field being
typed says nothing about which effect may carry it". Now `gate` on an `open` is a
parse error because `OpenEffect` has no such field. The table is deleted.

**The effect key carries its own primary argument** — `act: <dough>`, `nav:
<dough>`, `open: <path>`, `read: <mode>` — so the discriminator and the value are
one token instead
of an `effect:` line plus a `target:`/`to:`/`mode:` line.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from app.spreads.spark import anchor
from app.utils.base_model import AppBaseModel


def has_trigger_map(spread: dict[str, Any] | None) -> bool:
    """Does this frozen spread carry a controller at all?

    ★ THE ONE PREDICATE, because the old one was a KEY and the key is gone. Every
    consumer used to ask ``spread.get("interactions")`` — true when the flat list
    was present. The map moved onto the blocks and nine call sites kept asking,
    each now permanently false: the save-time spark gate stopped running, a card
    stopped carrying the ``source`` its own ``read`` re-bakes, and the canvas
    stopped reporting a spread as interactive. Nothing errored — that is the shape
    of it.

    So the question is asked of the STRUCTURE now, not of a key: walk the blocks
    (nested included) and look for an ``on:``. A predicate that walks cannot be
    left behind by a grammar change the way a key name can.
    """
    if not isinstance(spread, dict):
        return False
    blocks = spread.get("blocks")
    if not isinstance(blocks, list):
        return False
    return any(hit.block.get("on") for hit in anchor.walk_blocks(blocks))


class ActEffect(AppBaseModel):
    """Bake a dough with the triggering row's fields.

    ``act`` is the dough id. ``inputs`` maps that dough's input keys to
    ``$.<field>`` paths off the pressed row (or ``$selection.<field>`` for the
    master-detail shape). ``into`` names where the result lands — ``self`` for an
    inline slot under the row, ``$<block>`` for a sibling. ``gate: confirm`` holds
    the bake behind an approval the host renders.
    """

    act: str
    inputs: dict[str, str] = Field(default_factory=dict)
    into: str | None = None
    gate: Literal["confirm"] | None = None

    model_config = ConfigDict(extra="forbid")


class OpenEffect(AppBaseModel):
    """Open the triggering row's URL through the host's external-open seam.

    ``open`` is a ``$.<field>`` path off the row. No ``gate``: nothing is baked, so
    there is nothing to confirm — and because this is its own model, writing one is
    a parse error rather than a field the gate has to remember to refuse.
    """

    open: str

    model_config = ConfigDict(extra="forbid")


class NavEffect(AppBaseModel):
    """Navigate to another SURFACE — the in-app arm of ``open``.

    ``nav`` is the target dough id; pressing the row bakes it with ``inputs`` (the
    same ``$.<field>`` / ``$selection.`` / ``$value.`` / literal grammar an ``act``
    binds) and paints the spread the target's returned shape resolves to, as a new
    canvas surface. No ``into``: a navigation always lands a NEW surface, so the
    landing is implicit — that absence is the whole difference from an ``act``,
    which lands INSIDE the current spread. No ``gate``: you are moving to a surface,
    not committing a mutation.
    """

    nav: str
    inputs: dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ReadEffect(AppBaseModel):
    """Re-call the spread's OWN source and fold the result back in.

    ``read`` IS the fold mode — ``replace`` (refresh / filter) or ``append``
    (paginate). No ``target``: a read re-bakes the source that produced this value,
    which is what makes it a read rather than an act. ``params`` are the re-call
    arguments merged over the source's original inputs — a ``$value.<path>`` off
    the last output, a ``$control.<name>`` off a control the spread renders, or a
    literal.

    No ``into``: it folds into the value it came from, so there is no landing site
    to name. No ``gate``: its source must be side-effect-free, so there is nothing
    to confirm.
    """

    read: Literal["replace", "append"]
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


#: What a GESTURE may fire. All are row-scoped — they act on the item pressed.
GestureEffect = ActEffect | OpenEffect | NavEffect


class BlockSpark(AppBaseModel):
    """One block's ``on:`` map — trigger → effect.

    The trigger set is CLOSED and each member's type states its scope: the two
    gestures take a row-scoped effect, ``refresh`` takes the block-scoped read.
    Adding a trigger (``submit``, ``change``, per-row ``actions``) is a field here
    plus its binder wiring — not a new concept and not a new table.
    """

    press: GestureEffect | None = None
    contextmenu: GestureEffect | None = None
    refresh: ReadEffect | None = None
    search: ReadEffect | None = None
    """A read submitted by a CONTROL this spread renders (a `searchBox` keyword, a
    `viewControl` pick) rather than by the footer button.

    Two block-scoped reads on one list is not a contrived shape — it is the
    searcher, the composition the build guide ships as a skeleton: a new keyword
    REPLACES the result set while Load-more APPENDS to it. They differ by trigger
    and by mode, not by target, so one `refresh` key cannot hold both.

    WHICH control is named by the `params` (`$control.<name>`); that a control
    fires it at all is this key. The binder used to derive both from the params —
    "has a `$control.` arg" meant "yields the footer" — so the two reads were
    distinguishable only by inspecting their arguments, and a refresh that merely
    wanted the box's current value read as a search."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _name_the_real_fault(cls, data: Any) -> Any:
        """Say WHICH effect was meant and what is wrong with it.

        A bare union reports the FIRST branch's missing field, so `{open, gate}`
        comes back as "press.ActEffect.act" — an author who wrote a gate on an open
        is told the dough id is missing. That is the failure mode `AnchorMiss` was
        written to end one layer down; it must not be reintroduced here.

        So the effect is identified by WHICH effect key is present — a closed,
        one-of-three question — and the message names that effect and its own legal
        fields. Anything this cannot classify falls through to pydantic unchanged.
        """
        if not isinstance(data, dict):
            return data
        legal = {"act": ActEffect, "open": OpenEffect, "read": ReadEffect, "nav": NavEffect}
        for trigger, payload in data.items():
            if trigger not in ("press", "contextmenu", "refresh", "search") or not isinstance(payload, dict):
                continue
            named = [k for k in legal if k in payload]
            if len(named) > 1:
                raise ValueError(
                    f"`on.{trigger}` names {len(named)} effects ({', '.join(sorted(named))}) — "
                    f"a trigger fires exactly one"
                )
            if not named:
                raise ValueError(
                    f"`on.{trigger}` names no effect — give it one of "
                    f"act: <dough_path> / nav: <dough_path> / open: $.<field>"
                    + ("" if trigger in ("refresh", "search")
                       else " (or use `refresh:`/`search:` for a read)")
                )
            effect = named[0]
            # Scope is the trigger's own property, so a mismatch is named as one.
            if effect == "read" and trigger not in ("refresh", "search"):
                raise ValueError(
                    f"`on.{trigger}.read` — a read is BLOCK-scoped (it re-calls the "
                    f"spread's own source and folds the result), so it hangs off "
                    f"`refresh:`, not a per-row gesture"
                )
            if effect != "read" and trigger in ("refresh", "search"):
                raise ValueError(
                    f"`on.{trigger}.{effect}` — {trigger} fires the block-scope "
                    f"read; a row effect belongs on `press:` or `contextmenu:`"
                )
            allowed = set(legal[effect].model_fields)
            if stray := sorted(set(payload) - allowed):
                raise ValueError(
                    f"`on.{trigger}` is an `{effect}` effect, which takes "
                    f"{sorted(allowed)} — it has no {stray}"
                )
        return data

    @model_validator(mode="after")
    def _require_a_trigger(self) -> "BlockSpark":
        """An empty ``on:`` is meaningless — refuse it rather than carry a no-op
        controller (the same rule the old ``Spark._require_content`` held)."""
        if all(
            getattr(self, t) is None
            for t in ("press", "contextmenu", "refresh", "search")
        ):
            raise ValueError(
                "`on:` declares no trigger — name at least one of "
                "press / contextmenu / refresh / search"
            )
        return self

    def row_effects(self) -> dict[str, GestureEffect]:
        """The gesture triggers that are bound — what needs a pressable row."""
        return {
            name: eff
            for name, eff in (("press", self.press), ("contextmenu", self.contextmenu))
            if eff is not None
        }
