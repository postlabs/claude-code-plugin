"""Typed input/output ports — the value-shape side of a dough's contract.

``InputDef`` / ``OutputDef`` declare the typed ports `Dough` exposes; the
display constants say how an output renders. Leaf module (no ``app.doughs``
imports). Re-exported through the ``models`` package facade. All display *text*
lives in the ``box.yaml`` sidecar (see the ``box`` submodule), never here.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field

from app.utils.base_model import AppBaseModel


# The five value-shape names used by InputDef and ExpectedOutput.
# One alias, one source of truth — used by every typed-shape declaration
# across the model modules. If a new shape is ever needed (rare), add it here
# and every call site picks it up.
ValueType = Literal["string", "number", "boolean", "list", "object", "date", "datetime"]


class InputDef(AppBaseModel):
    """Declares a typed input port.

    Unified model — no separate bound/open/flags:
      value set      → fixed, hidden from user
      default set    → prompted with suggestion
      neither        → required, must be provided
      boolean+default → behavioral flag

    All display text (short ``name`` + longer ``description``) lives in
    the sibling ``box.yaml`` under ``<locale>.inputs.<key>``. Symmetric
    to :class:`OutputDef`.

    ★ ``reads`` / ``deeper`` — WHAT THIS PORT ACTUALLY CONSUMES, AND THE ONE
    ASYMMETRY THIS MODEL USED TO CARRY. An OUTPUT declares its shape and
    ``binding._assert_shape`` enforces it; an INPUT declared none, so
    ``check_input`` waved ``object``/``list`` through and a consumer had no way
    to decline what it was handed. A step's value travels WHOLE — ``${act_walk}``
    means every key that flour publishes, because the resolver cannot name a
    subset — so a producer growing an output for its own good reason landed it in
    every consumer already packing that step.

    Measured (``docs_sh/prompt_input_contract/analysis.md``): one browse handed
    ``web_synthesize`` 505,200 characters, 358,104 of them a key its own prompt
    never mentions, and the bake DIED at an input limit rather than slowing down.
    The same shape exists outside this stack, which is what made it an engine
    concern rather than a browser-stack habit.

    ``reads`` names the keys kept WHOLE; ``deeper`` names the keys that carry a
    nested node and are descended into. Two lists rather than a schema, because
    the shapes here are recursive (a trace's ``deeper`` holds another trace) and
    the strictifier cannot inline a recursive ``$ref`` — and because nothing here
    is model-facing, so a schema would be doing a projection's job with a
    validator's vocabulary.

    ★ ``max_bytes`` / ``trim`` — THE SAME PORT'S OTHER LIMIT, DECLARED IN THE
    SAME PLACE. Narrowing keys is not a size bound: a browse's records are wanted
    and are 95% of what survives. An agent flour talking to a CLI has a hard input
    ceiling, which is a property of the CONSUMER and belongs on its port —
    measured, ~470 KB, in BYTES (korean 273,512 chars fails where ascii 272,967
    answers, so a character budget is out by ~1.75x on Korean). ``trim`` names
    which kept key holds divisible records; the binder drops from the END of those
    lists until the value fits, because the engine cannot know which record
    matters and the site already ordered them.

    ★ IT PROJECTS, IT NEVER REJECTS. Mirroring the output rule would invert the
    failure: a producer adding a key would kill every consumer's bake instead of
    bloating a prompt, and when ``citations`` was added this month every browse
    would have failed rather than slowed. Extra keys are dropped and NAMED (the
    binder logs them), because a projection that cannot say what it took is the
    silent cap this repo keeps paying for. Declaring nothing keeps the old
    behaviour exactly.
    """

    type: ValueType = "string"
    value: Any | None = None
    default: Any | None = None
    required: bool = True
    visible: bool = True
    # A preference-gated input: if the caller leaves it unset AND no per-profile
    # preference is saved, the bake STOPS and asks (posts a `preference` ask)
    # instead of falling to `default`. For an input with no safe default — a login
    # method, a target account — where a silent default is a wrong guess. The
    # `default` (if any) becomes the ask's suggested option, never a silent fill.
    prefer: bool = False
    options: list[str] | None = None
    model: str | None = None
    reads: list[str] | None = None
    deeper: list[str] | None = None
    trim: list[str] | None = None
    max_bytes: int | None = None

    model_config = ConfigDict(extra="forbid")

    @property
    def projects(self) -> bool:
        """Whether this port narrows what reaches it (``reads`` declared)."""
        return bool(self.reads)


DisplayKind = Literal[
    "markdown", "data_table", "items_table",
    "browser_tab", "app_window", "shopping", "raw",
]
"""How a result panel should render this output. Frontend renders one
panel per declared output, dispatched by ``display``. The honest
defaults (string→markdown, list→data_table, others→raw) fire when
``display`` is unset, so most authoring sites never need to touch it.
``items_table`` is only valid on a list output produced by an ``each:``
step; ``browser_tab`` / ``app_window`` / ``shopping`` are only valid on
object outputs. ``shopping`` renders a product-card grid via the frontend
``<Spread>`` ``shopping`` template — the output is an envelope
``{title?, summary?, results: [{title, image, price, ...}]}``; never a
default, always an explicit opt-in."""


DISPLAY_REQUIRED_TYPES: dict[str, tuple[str, ...]] = {
    "markdown": ("string",),
    "data_table": ("list",),
    "items_table": ("list",),
    "browser_tab": ("object",),
    "app_window": ("object",),
    "shopping": ("object",),
    "raw": ("string", "number", "boolean", "object", "list"),
}
"""For each ``display`` value, which ``OutputDef.type`` values it accepts.
Single source of truth — the validator reads this to reject mismatches
and the baker reads its inverse to pick honest defaults."""


DEFAULT_DISPLAY_BY_TYPE: dict[str, str] = {
    "string": "markdown",
    "list": "data_table",
    "number": "raw",
    "boolean": "raw",
    "object": "raw",
}
"""``display`` to pick when an OutputDef omits the field. Authoring
agents declare ``display:`` only when overriding these defaults."""


class OutputDef(AppBaseModel):
    """Declares a typed output port. Symmetric to InputDef.

    No description — that lives in box.yaml. ``extra="forbid"`` enforces.
    """

    type: ValueType
    model: str | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    display: DisplayKind | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
