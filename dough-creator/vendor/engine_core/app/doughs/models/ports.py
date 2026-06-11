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
    """

    type: ValueType = "string"
    value: Any | None = None
    default: Any | None = None
    required: bool = True
    visible: bool = True
    options: list[str] | None = None
    model: str | None = None

    model_config = ConfigDict(extra="forbid")


DisplayKind = Literal[
    "markdown", "data_table", "items_table",
    "browser_tab", "app_window", "raw",
]
"""How a result panel should render this output. Frontend renders one
panel per declared output, dispatched by ``display``. The honest
defaults (string→markdown, list→data_table, others→raw) fire when
``display`` is unset, so most authoring sites never need to touch it.
``items_table`` is only valid on a list output produced by an ``each:``
step; ``browser_tab`` / ``app_window`` are only valid on object outputs."""


DISPLAY_REQUIRED_TYPES: dict[str, tuple[str, ...]] = {
    "markdown": ("string",),
    "data_table": ("list",),
    "items_table": ("list",),
    "browser_tab": ("object",),
    "app_window": ("object",),
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
