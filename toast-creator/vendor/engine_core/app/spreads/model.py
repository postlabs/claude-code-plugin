"""The parsed ``spread.yaml`` model.

A **spread** is a kit-shipped, declarative, READ-ONLY spread definition for the
memo page — the live-read analog of a flour's ``dough.yaml`` (and, like a flour,
it ships a sibling ``box.yaml`` carrying display labels). It is NOT a bake: it
maps one workspace surface to a renderable ``<Spread>`` dataset
(``{title, value, spec}``) by naming a ``layout:`` composition and a ``value:``
ref (where the value comes FROM, never the value itself).

``spread.yaml`` shape (mail reference — the live dashboard):

    uid: postlab.sp-37f36a929a244223b9b6841b74cdecdf   # the identity; path is DERIVED from location
    layout:                     # an ordered list of blocks; each {block, roles, knobs}
      - block: shareBar
        roles:
          segments: split       # a {label,value,tone,muted}[] proportion rollup
          title: $statsTitle    # $-ref → resolved from box.yaml labels
      - block: rowList
        roles:
          items: highlights     # the folded record list
          title: title
          badge: disposition
          badgeLabels:          # value→$-ref (localized badge text)
            important: $disposition.important
    value:                      # where the value comes FROM, never the value
      surface:
        name: mail

**The ``$``-ref label channel.** Any string in a block's ``roles`` or in
``value:`` of the form ``$<path>`` is a reference into the spread's
box.yaml label set — the loader resolves it (locale → en) and substitutes the
display string. This is how English label literals (tab title, statsTitle, KPI
labels, meta labels, section headings, vocab tokens) move OUT of code and into
box.yaml while the ``spec``/``value`` come out byte-identical. A plain (non-``$``)
string is a raw field key / value and passes through untouched.

Common ``$``-refs (box.yaml keys — the box is ONE flat ``key → text`` map, so a
dotted ref like ``$vocab.disposition.important`` is a single key, not a
namespace; resolved against box.yaml, see ``boxref.py``):

- ``$name``             → the spread's own label (the dataset's ``title``).
- ``$heading``         → the section-heading literal stamped into ``value``.
- ``$statsTitle``       → the dashboard's literal quiet band label.
- ``$meta.<k>``         → a labeled-meta ``{field,label}`` label.
- ``$vocab.<field>.<token>`` → an enum token's display label (badge tokens only).

A memo spread's value comes from its SURFACE (``value: {surface: {name}}``); the
fold that produces it belongs to the surface and lives in
``app.memo.spreads.folds``. The ref carries only copy: ``stamp`` for envelope
text a path-typed role cannot otherwise receive, ``labels`` for the token text a
fold looks up.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.spreads.refs import Ref
from app.spreads.spark.model import BlockSpark
from app.utils.base_model import AppBaseModel



class LayoutBlock(AppBaseModel):
    """One entry in a composition's ``layout:`` — a named block + its role/knob
    binding. The frontend ``CompositionBlock`` twin: ``compileBlock(block,
    {roles, knobs})`` lowers it. ``roles`` values are field keys / literals /
    ``$``-refs (resolved against box.yaml by the loader, like a template bind);
    ``knobs`` values are enum strings. The block kind + role/knob legality is
    gated by ``validate.composition`` against ``catalog.BLOCK_DEFS``."""

    # A layout entry is a BLOCK. A sub-spread is never inlined here — it is
    # NESTED by reference (`Spread.nested`, a `{spread, spread_uid, over/value}`
    # decl resolved at HYDRATE as its own node), the direct mirror of a dough
    # step calling a sub-dough: referenced by path/id, rendered as a boundary,
    # never flattened into this layout.
    block: str = ""
    # An optional AUTHOR-CHOSEN handle for this block, so a spark anchor and a
    # view op can address THIS one rather than "the only rowList".
    #
    # Without it an anchor names a KIND, which stops meaning anything the moment
    # a spread holds two of them — `resolve_anchor` correctly refuses the
    # ambiguity, so the second list is not mis-bound, it is simply unaddressable.
    # That is tolerable while a canvas is many small nodes with one list each,
    # and it is the blocker the moment the canvas IS one spread.
    #
    # Optional on purpose: `$rowList` keeps resolving by kind when a spread has
    # exactly one, so nothing already authored has to change. Naming is what you
    # reach for when you want a second one.
    #
    # The precedent is `$control.<name>`, which has ALWAYS addressed by the name
    # the author chose (`anchor.resolve_control`) — this makes anchors work the
    # way controls already do, rather than inventing an addressing scheme.
    name: str = ""
    roles: dict[str, Any] = Field(default_factory=dict)
    knobs: dict[str, str] = Field(default_factory=dict)
    """Enum STRINGS. A YAML boolean is coerced by ``_coerce_knobs`` below rather
    than refused — see there for why the coercion has to live at the PARSE."""
    on: BlockSpark | None = None
    """The CONTROLLER — what happens when this block is pressed, right-clicked or
    refreshed. Declared here for the same reason `view:` is: a composition's only
    inter-block relation is containment, so an interaction that named another block
    would have to address it by a string that must then RESOLVE. It used to: a flat
    spread-level `interactions:` list whose `$rowList.row` anchor missed four
    different ways. On the block it drives, three of those four are unreachable.

    See `spark.model.BlockSpark` — the trigger is the key, and each effect is its
    own model, so `gate` on an `open` is a parse error rather than a table lookup."""
    view: list[dict[str, Any]] = Field(default_factory=list)
    """VIEW OPS — a pure, ordered reshape of THIS block's own list, applied at
    render time to data ALREADY in ``value``. No bake, no host, no controller:
    ``filter``/``sort``/``limit`` are declared here and the frontend applies them
    between the value and the list seam.

    Declared on the CONSUMING block on purpose. The composition's only inter-block
    relation has ever been containment, and a block has no ``id`` to be addressed
    by — so an op that named another block would have to bind by data path and
    would silently reshape every block sharing that path. Here the op reads as
    what it is: this list, these ops, in this order.

    **The honest boundary:** a view op reshapes what is ON SCREEN. Nothing in the
    value contract says whether the value is the whole set, so a ``sort`` over a
    truncated fetch gives a confidently wrong answer. Any question whose answer
    depends on the full set is a spark ``read``, not a view op."""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _requires_block(self) -> "LayoutBlock":
        """A layout entry names a block. A sub-spread is nested by reference
        (`Spread.nested`), never inlined into the layout."""
        if not self.block:
            raise ValueError("a layout entry needs a `block:` — a sub-spread is "
                             "nested via `Spread.nested`, not inlined here")
        return self

    @field_validator("knobs", mode="before")
    @classmethod
    def _coerce_knobs(cls, val: Any) -> Any:
        """Coerce a YAML boolean knob to its catalog STRING form, AT THE PARSE.

        `d9a9e8033` established that knob enums are strings by construction
        (``['false','true']``) while a spread is authored in YAML, where
        ``divided: true`` parses to a real ``bool`` — and that refusing it refuses a
        spec meaning exactly what it says. It put the coercion at three READERS
        (``validate._normalize_knob``, the frontend ``normalizeKnob`` and
        ``validate.ts``).

        It could not take effect on a dough spread, because that path PARSES first:
        the view loader (``app.spreads.artifact.load``) calls ``Spread.model_validate``
        before any validator runs, so ``dict[str, str]`` rejected the bool and the
        loader's ``except`` dropped the ENTIRE spread with a warning. The spark gate
        then reported "this dough declares no spread" — which sends the author to
        the wrong file for a one-word problem in another one. Measured while
        authoring a real app: `divided: true` on a rowList cost the whole view.

        So this is the fourth agreeing reader, and the only one upstream of the
        others. Keep all four in step."""
        if not isinstance(val, dict):
            return val
        return {
            k: (str(v).lower() if isinstance(v, bool) else v)
            for k, v in val.items()
        }


def _custom_prefix() -> str:
    """The active account's id prefix.

    Reached through `utils`, never through `app.doughs` — this kernel is a LEAF
    that memo and doughs both import DOWN into, and taking an edge back up would
    put a cycle where the layering exists to prevent one.
    """
    from app.utils.profile.owner import active_handle

    return active_handle() + "."


class NestedSpread(AppBaseModel):
    """A child spread rendered as its OWN node — THE way a spread nests another,
    the direct mirror of a dough step calling a sub-dough. Referenced by
    ``spread`` (a path/id — a dot path or a ``sp-`` uid), resolved at HYDRATE, and
    drawn SEPARATELY as a child ``WireNode``. Never inlined into the parent layout.

    Where that value comes from is the whole point, and it is EITHER:

    - ``over`` — a sub-key of the PARENT's value (the memo case: one folded
      surface sliced across several child cards); or
    - ``value`` — an INDEPENDENT ref of the child's own (the CANVAS case: each
      item names its own template AND its own data, so unrelated results — a
      chart off one bake, a table off another surface — are siblings under one
      root).

    That second arm is what lets the canvas dissolve fully into ONE spread: there
    is no separate node species, only a root spread whose children are spreads,
    each pointing at a durable template (``spread``) and a throwaway value
    (``value`` = a ref re-resolved at hydrate). Exactly one of the two — a child
    that slices the parent does not also bring its own source."""

    model_config = ConfigDict(extra="forbid")

    spread: str
    # The SCOPED verify/heal token for the reference — the twin of a dough step's
    # `dough_uid`. `spread:` is the path/id that resolves; `spread_uid:` is
    # `<handle>.sp-<hex>`, the durable pointer that verifies the resolved dir is
    # this artifact and heals the ref if the target moved. Optional (it is the
    # target's own whole uid; `stamp_spread_uids.py` fills it).
    spread_uid: str = ""
    over: str = ""
    value: Ref | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "NestedSpread":
        if self.over and self.value is not None:
            raise ValueError(
                "a nested spread reads its value from `over` (a slice of the "
                "parent) OR `value` (its own ref) — not both"
            )
        return self


class SpreadFor(AppBaseModel):
    """The view's contract anchor — what value shape this view draws.

    ``model`` is the nominal anchor (a dotted Pydantic ref today, an artifact
    type id after M3); ``keys`` the structural fallback (top-level keys the
    value must carry). Either alone is legal; both empty is only legal on a
    PRIVATE (colocated) view, whose anchor is its dough's own outputs."""

    model_config = ConfigDict(extra="forbid")

    model: str = ""
    keys: list[str] = Field(default_factory=list)


class Spread(AppBaseModel):
    """One parsed ``spread.yaml`` — the whole file, memo and donut alike.

    A spread is a ``layout:`` composition over the ONE block catalog
    (``catalog``), its ``$``-ref labels resolved through ``boxref``, gated by the
    ONE validator, rendered by the ONE ``<Spread>``. That much is identical for
    every spread; the dough ``kind`` inference does not apply here.

    **Every spread answers one question: where does my value come from.** Two
    answers, and a file gives exactly one:

    - ``for:`` — a value of this SHAPE is handed to me. Nominal (``model``) or
      structural (``keys``); the resolution ladder matches a dough's outputs
      against it, so a dough and a card find each other without either naming
      the other.
    - ``value:`` — I name a REF and ``resolve_ref`` produces it: a bake, a live
      memo read, a keyed JSON on disk. This replaced ``assemble:``, which spelled
      a fold recipe out INSIDE the render definition — which collection, which
      join key, how far back — so six cards over one surface could disagree about
      it. The recipe is the surface's, and lives with the surface.

    They are exclusive across every shipped spread because they are one question,
    not a base case and a variant. Reading them as "a model plus an optional
    extra" is what let a SECOND model grow beside this one: each rejected the
    other's files while both declared ``extra="forbid"``, so both claimed to be
    the complete schema and both lied — until ``validate_kits`` parsed every file
    through the half that could not represent it, failed 23 of 37, and had its
    workflow deleted for mailing a failure on every push.

    **The two path classes** (memo only). A kit spread's ``path`` encodes its
    sub-kit + surface (``advanced.workspace.<surface>.<name>``), so
    ``registry.SPREADS`` derives the surface from it. A user spread's ``path`` is
    ``<handle>.<name>`` and carries no surface, so it must declare one. A donut
    spread has no ``path``.
    """

    # ── identity ────────────────────────────────────────────────────────────
    uid: str = ""
    """The whole uid — ``<handle>.sp-<hex>`` — generated whole at create
    (``mint(handle, "spread")``) and stored whole. ``path`` is the human LABEL —
    grep, folders — and a rename or tray→tree move changes it; the uid does not."""
    path: str | None = None

    # ── what it draws ───────────────────────────────────────────────────────
    layout: list[LayoutBlock] | None = None
    """The composition — an ordered list of blocks the frontend compiles into a
    stack. Required (``_require_layout``). An entry may also be an INCLUDE
    (``{spread, over}``), which is why every walker reads the RAW dicts rather
    than these parsed models."""
    nested: list[NestedSpread] = Field(default_factory=list)
    """Child spreads drawn as their OWN nodes over sub-keys of this spread's value
    — VALUE nesting (``NestedSpread``), the recursion the frontend draws through
    ``<WireNodeView>`` and the shape the canvas dissolves into. Distinct from a
    layout ``{spread, over}`` include, which inlines a child's blocks into one
    render; here each child is a separate ``<Spread>`` over its own slice."""

    # ── where the value comes from (exactly one) ────────────────────────────
    for_: SpreadFor | None = Field(default=None, alias="for")
    """A value of this shape is handed in."""
    value: Ref | None = None
    """Or: it arrives through a REF — ``source`` (a bake), ``surface`` (a live
    memo read), ``file`` (a keyed JSON). The spread names WHERE the value comes
    from and ``resolve_ref`` produces it; no fold rides in a render definition."""
    surface: str | None = None
    """The surface a memo spread reads — derived from the id for a kit spread,
    declared for a user one."""

    # ── how it is chosen ────────────────────────────────────────────────────
    default: bool = False
    """This spread is THE default for its ``for`` shape, so a dough producing
    that shape with no spread of its own paints through here. Declaration-based
    on purpose: an unmarked spread is only ever used by explicit reference, so
    minting one can never silently repaint someone else's results."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _require_layout(self) -> "Spread":
        """A spread renders through a ``layout:`` composition — the ONE render path
        (the old ``template:`` tier was removed, so there is no longer an XOR to
        enforce, only the presence of ``layout:``). Where the value comes from is
        orthogonal and runs the same way regardless."""
        if self.layout is None:
            raise ValueError(
                f"spread '{self.path}' declares no 'layout:' — a spread renders "
                f"through a 'layout:' composition"
            )
        return self

    @property
    def is_user(self) -> bool:
        """An author-owned spread — path is ``<handle>.<name>`` (the same two-segment
        class as an authored dough). A donut spread has no path and is
        never a user spread."""
        return self.path is not None and self.path.startswith(_custom_prefix())
