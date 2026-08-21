"""The ``Dough`` root model.

``Dough`` is the parent model of the dough engine; its child models live in
sibling modules (``ports``, ``box``, ``steps``, ``enums``) and are imported
here. The package ``__init__`` is a pure re-export facade over those submodules.
See ``app/doughs/models/__init__.py``.

Bakery vocabulary (tool / flour / dough / kit / kind / class / step shapes) is
defined in the root CLAUDE.md "Dough Engine" section — single source of truth.

Reference syntax: ${scope.path}
  ${inputs.x}     — input values (fixed or user-provided)
  ${X}            — auto-published from a prior dough: step (X = bare flour id)
  ${item_name}    — foreach item (matches as: field)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict, Field

from app.doughs.validation.rules import custom_root
from app.utils.base_model import AppBaseModel

from app.doughs.models.box import FieldBox
from app.doughs.models.ports import InputDef, OutputDef
from app.doughs.models.steps import ActionDef, RecoveryAction, parse_steps

if TYPE_CHECKING:
    # Only used in method-signature annotations (stringized) — not a Pydantic
    # field type, so it never needs to resolve at runtime.
    from app.doughs.models.box import Box


class Dough(AppBaseModel):
    """A workflow definition. See root CLAUDE.md "Dough Engine" for vocab.

    ``kind`` (flour vs dough) is inferred from shape — derived ``@property``,
    NOT a stored YAML field. Explicit ``kind:`` keys are rejected at the dict
    layer by ``validate_dough_dict`` with a hint pointing at shape inference
    (Pydantic itself absorbs unknown keys via ``extra="allow"``).

    Stored as YAML alongside a required ``box.yaml`` sidecar. Every dough
    must declare ``return:`` — it defines the public output contract.
    """

    path: str
    # The whole uid — `<handle>.do-<hex>` — generated whole at create
    # (`mint(handle, "dough")`) and stored whole.
    # `path` above is the human location (grep + folders, `path IS the dir`,
    # re-derived from location at load); a rename/move CHANGES the path but never
    # the uid. Shipped in kit yamls; generated on create for authored doughs.
    uid: str = ""
    # `path` is not stored inline — re-derived from location at load, and emitted
    # to yaml as a `path:` grep/browse hint by ``to_yaml_dict``. The old `label:`
    # field (a redundant copy of it) is gone; a stale `label:` in an unmigrated
    # yaml is absorbed by ``extra="ignore"``.
    version: str = "1"
    # Derived from id at load (the parent slash-path; everything before the
    # leaf segment). NOT persisted — ``to_yaml_dict`` omits it — and NOT used
    # for path resolution (the id IS the path; see ``store._dough_dir``). Kept
    # as a constructor input so model_validate(data) and clone update={} still
    # accept it; it always mirrors the id's path prefix.
    folder: str = Field(default_factory=custom_root)
    """Defaults to the profile's author root. A plain ``= "user"`` would be
    evaluated once at class definition, pinning whichever profile imported the
    model first — the same reason the root is a call and not a constant."""

    # What this dough acts ON — an open lowercase singular noun (``message``,
    # ``event``, ``file``). Optional (a draft may be saved without one), and the
    # half of the old capability pair that survived: it names the grant class the
    # staff gate keys on (``<object>:<namespace>``). ``object_`` uses an alias so
    # YAML writes the natural ``object:`` key without clashing with the builtin.
    object_: str | None = Field(default=None, alias="object")

    # The DECLARED risk tier — read_only | writes_data | high_consequence |
    # experimental. Read directly by the staff autonomy gate and the spark
    # read-safety check, and surfaced as the /kits risk badge. It used to be
    # derived from a capability verb through two lookup tables; every dough
    # states its own now. Declared rather than left to ``extra="allow"`` so it
    # survives a to_yaml_dict round-trip (clone / rename / import) — an absorbed
    # field is silently dropped there, which would strip a dough's risk tier.
    consequence: str | None = None

    # A reusable procedure the user saved — an ``agent:`` flour they invoke by
    # name rather than a capability over one object. It was a value in the verb
    # enum (``verb: skill``), which is why it outlived that axis: the enum's own
    # comment called it distinct from every tool verb beside it. Marking it
    # directly is what the value was standing in for.
    skill: bool = False

    # References to taste flours (`<handle>.taste.<id>`) whose lens text is FOLDED
    # into this flour's served spec at READ time (query.spec) when it is a
    # skill. The taste STORE stays the source of truth; a skill
    # merely POINTS at it — reading the skill brings the lens. Unresolvable ids
    # fail open (no text, never an error). Declared (not left to extra="allow")
    # so it survives to_yaml_dict round-trips (clone/rename/import).
    applies_taste: list[str] = Field(default_factory=list)

    # A skill flour's IMPORTS — the dough + spread ids it reaches for as it paints
    # beats (its beat doughs and its spread palette). Like a module's imports: the
    # skill DECLARES the set once so it never has to `find_spreads` every run or
    # re-list them in prose. FOLDED into the served spec at READ time (query.spec)
    # exactly like `applies_taste`, so reading the skill brings its palette — name +
    # about per id, resolved live. A ref is a uid OR a path (put the uid, path in a
    # trailing comment, per the guide), and mixes doughs + spreads freely — the
    # resolver tells them apart. Unresolvable ids fail OPEN (listed bare, never an
    # error); `find_*` by intent stays the fallback for anything not imported.
    imports: list[str] = Field(default_factory=list)

    # The markets this dough's inventory serves — inherited from its kit's
    # manifest and STAMPED at load (loading.read), not read from dough.yaml, so
    # it is not emitted by to_yaml_dict. Empty ⇒ global / always-eligible. Read
    # by query.find() as a discovery gate against the query's language.
    markets: list[str] = Field(default_factory=list)

    @property
    def kind(self) -> Literal["flour", "dough"]:
        """Inferred from shape: action: → flour; steps: → dough."""
        if self.action is not None:
            return "flour"
        return "dough"

    # --- Inputs (unified: fixed, prompted, and flags) ---
    inputs: dict[str, InputDef] = Field(default_factory=dict)

    # --- Named outputs — typed contract symmetric to inputs.
    # Each entry declares ``type:`` (mandatory) and optional ``model:`` for
    # richer Pydantic shapes. Descriptions belong in box.yaml, never here. ---
    outputs: dict[str, OutputDef] = Field(default_factory=dict)

    # --- Leaf action (Phase 1: alternative to `steps:` for leaf doughs).
    # A dough has either `action:` (leaf) or non-empty `steps:` (composition),
    # not neither. Both is allowed during transition (warned, not errored). ---
    action: ActionDef | None = None

    # --- The recipe (compact step syntax) ---
    steps: list[dict[str, Any]] = Field(default_factory=list)

    # Opt in to running consecutive steps that are PROVABLY independent at the
    # same time (``execution.deps.plan``). Off by default and deliberately not
    # inferred: the dependency graph reads ``${ref}`` and cannot see a SIDE
    # EFFECT, so two steps that never touch each other's output can still both
    # write one file. Turning it on is a claim about that, which only the author
    # can make. Nothing about the composition's meaning changes — merged steps
    # are exactly the ones whose order was never observable.
    parallel: bool = False

    # Written by an EMITTER rather than by a person — a promoted read, today.
    # It is DECLARED rather than left to `extra: allow` because the two are not
    # the same on disk: `to_yaml_dict` never merges `model_extra`, so an extra
    # survives validation, rides in memory, and is silently dropped by the write.
    # `escalate` reads this off a dough the BAKE loaded (i.e. off disk) to decide
    # whether using a draft publishes it, so as an extra it was always False
    # there and nothing a promotion drafted could ever be published.
    auto_generated: bool = False

    # --- Public output contract (mandatory) ---
    return_: dict[str, str] = Field(alias="return")

    # --- Recovery per failure class ---
    recovery: dict[str, list[RecoveryAction]] = Field(default_factory=dict)

    # --- Default view (a POINTER, not a document) ---
    # The id of a view in the profile view tree ({profile}/views/, app/views/)
    # this dough is drawn with by default. The dough contract stays pure data
    # logic; presentation is designated, not owned. Resolution order at any
    # display point: the panel's explicit view > this pointer > (M3) the value
    # type's registered view > the Auto floor. A colocated private
    # `view/view.yaml` in the dough dir beats this pointer at load. Empty = no
    # designation. Emitted by ``to_yaml_dict`` — it is authored metadata.
    default_spread: str = ""

    # --- The frozen SPREAD (data-independent; ONE carrier) ---
    # When set, this dough's typed ``donut.output`` renders through the
    # ``<Spread>``/``<Spark>`` seam — on the chat canvas at bake-complete and,
    # via the card rebuilt from the persisted donut, on every other consumer
    # (card pull, history, resume); the donut keeps no copy of it. Shaped like
    # the artifact it froze:
    # ``{tier:'composition', blocks:[{block, roles, knobs, on?}, …]}`` — the
    # controller rides inside each block as its ``on:`` trigger map, not a
    # separate key. Data-INDEPENDENT (only ``value`` touches the bake output;
    # the arrangement is authored once, and a clicked datum is supplied by the
    # frontend binder at click-time).
    #
    # NOT authored inline in ``dough.yaml``: the loader
    # (``definitions.spread.load_dough_spread``) resolves it from
    # ``{profile}/spreads/<handle>/<name>/spread.yaml`` — the dough's own
    # ``default_spread:`` reference, or a spread declaring ``default: true`` for
    # the output MODEL or its return KEY SET — at read time and $-resolves its
    # literal labels — so ``to_yaml_dict`` does NOT emit it. Gated at save by BOTH kernels reading their half of this one
    # dict: ``composition_spec`` the block layout (``INVALID_SPREAD``),
    # ``spark_spec`` the blocks' ``on:`` maps (``INVALID_SPARK``). ``None`` = an
    # ordinary bake that renders through the typed DonutResult path, unchanged.
    spread: dict[str, Any] | None = None

    # --- Display labels (populated from box.yaml at API time, not stored) ---
    # ``input_meta`` / ``output_meta`` carry the per-key FieldBox (short
    # ``name`` + longer ``description``) for the active locale, with per-key
    # en fallback. All three come from this dough's OWN box; a CALLED flour's
    # labels are read off that flour, by whoever renders the step.
    step_labels: dict[str, str] = Field(default_factory=dict)
    input_meta: dict[str, FieldBox] = Field(default_factory=dict)
    output_meta: dict[str, FieldBox] = Field(default_factory=dict)

    # --- Metadata ---
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def get_steps(self) -> list:
        """Parse raw step dicts into typed step models."""
        return parse_steps(self.steps)

    def to_yaml_dict(self) -> dict[str, Any]:
        """Convert to dict for YAML serialization. Compact — omits empty/default values.

        Never writes `kind:` — it's a derived `@property` inferred from shape
        (`action:` → flour, `steps:` → dough). The validator explicitly
        rejects YAML with `kind:` (``validate_yaml`` via ``FORBIDDEN_PRE_PARSE_KEYS``),
        so emitting it here would make every saved dough fail its own next validate pass.
        """
        d: dict[str, Any] = {}
        # The stable uid must survive every rewrite (clone / rename / finalize /
        # import) — `path` is not emitted (re-derived at load), so `uid` is the
        # identity line and is emitted first.
        if self.uid:
            d["uid"] = self.uid
        # The human PATH — re-derived from location at load, so it is emitted as a
        # `path:` grep/browse hint. Export embeds verbatim bytes, so the canonical
        # share hash is unaffected by this line.
        if self.path:
            d["path"] = self.path
        if self.object_:
            d["object"] = self.object_
        if self.consequence:
            d["consequence"] = self.consequence
        if self.skill:
            d["skill"] = True
        if self.applies_taste:
            d["applies_taste"] = self.applies_taste
        if self.imports:
            d["imports"] = self.imports
        if self.inputs:
            d["inputs"] = {
                k: v.model_dump(exclude_none=True, exclude_defaults=True)
                for k, v in self.inputs.items()
            }
        if self.outputs:
            d["outputs"] = {
                k: v.model_dump(exclude_none=True, exclude_defaults=True)
                for k, v in self.outputs.items()
            }
        if self.action is not None:
            d["action"] = self.action.model_dump(
                by_alias=True, exclude_none=True, exclude_defaults=True,
            )
        if self.steps:
            d["steps"] = self.steps
        if self.parallel:
            d["parallel"] = True
        if self.auto_generated:
            d["auto_generated"] = True
        d["return"] = self.return_
        if self.recovery:
            d["recovery"] = {
                k: [a.model_dump(exclude_none=True) for a in v]
                for k, v in self.recovery.items()
            }
        if self.default_spread:
            d["default_spread"] = self.default_spread
        # ``view`` is NOT emitted into dough.yaml — it is a runtime carrier
        # resolved from the dough's VIEW at load (definitions.spread), so a
        # re-save must not write it back inline (that was the old carrier).
        return d
