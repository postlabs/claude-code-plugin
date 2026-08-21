"""The value REF — the three ways a spread's value arrives.

Shapes only. ``resolve_ref`` and its arm registry live one level up in
``artifact/value.py``, because resolving a ``source`` reads a donut
(``app.doughs``) and a ``surface`` reads a workspace (``app.memo``) — both UP
from here. These sit in the kernel because ``Spread`` CARRIES one, and the
kernel cannot import ``artifact/``.

    source {dough, inputs, donut}   a bake result: read the last donut, or
                                    re-bake (dough + inputs) when fresh
    surface {name}                  a live memo workspace read
    file {path}                     a keyed JSON on disk — sample.json (the
                                    known example, finalizes with the spread) or
                                    dataN.json (a temp value, dies with the tray)

Nesting has NO ref: a nested node reads a sub-key of its parent's value.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, model_validator

from app.utils.base_model import AppBaseModel


class SourceRef(AppBaseModel):
    """A bake-backed value: the dough that produces it, the inputs it took, and
    the last donut it produced. ``donut`` is the fast path (read it back);
    ``dough`` + ``inputs`` is the refresh path (re-bake). Resolved by the source
    arm (``app.doughs`` registers it)."""

    model_config = ConfigDict(extra="forbid")

    dough: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    donut: str = ""


class SurfaceRef(AppBaseModel):
    """A live memo workspace read — the value the ``assemble`` fold produced,
    now named by the surface it reads instead of carried inline. Resolved by the
    surface arm (``app.memo`` registers it)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    labels: dict[str, str] = Field(default_factory=dict)
    """Token → display text the surface's fold consumes — the enum labels and
    field captions that used to sit inside ``assemble.args``. COPY, like
    ``Ref.stamp``, and resolved against the spread's own ``box.yaml`` by the
    loader; the difference is only where it lands. A fold reads the raw token off
    the record (NO PRETTIFYING) and looks its text up here, so the label stays in
    the box of the card that shows it."""


class FileRef(AppBaseModel):
    """A keyed JSON value on disk, by filename relative to the spread's dir —
    ``sample.json`` (the known example that finalizes with the spread) or
    ``dataN.json`` (a temp value the agent composed this turn)."""

    model_config = ConfigDict(extra="forbid")

    path: str


class Ref(AppBaseModel):
    """How a spread's value arrives — EXACTLY one of the three arms. The spread
    cannot tell them apart and must not: the join to the layout is the value's
    SHAPE (``for.keys`` / field-key roles), never the provenance."""

    model_config = ConfigDict(extra="forbid")

    source: SourceRef | None = None
    surface: SurfaceRef | None = None
    file: FileRef | None = None

    stamp: dict[str, str] = Field(default_factory=dict)
    """Literal envelope keys merged onto the resolved value — COPY, never data,
    and orthogonal to which arm produced it. A heading role reads a data PATH
    (``catalog.role_kind`` → ``rootPath``), so a ``$``-ref bound straight to one
    resolves to text that ``rootKey`` re-reads as ``$.<text>`` and the card
    paints blank. Stamping the text ONTO the value is the sanctioned fix, and
    this is where it lives now that ``assemble``'s ``heading``/``heading_key``
    pair is gone. The LOADER applies it, because the loader is what holds the
    ``box.yaml`` these resolve against — an arm never learns about copy."""

    @model_validator(mode="after")
    def _exactly_one(self) -> "Ref":
        set_ = [k for k in ("source", "surface", "file") if getattr(self, k) is not None]
        if len(set_) != 1:
            raise ValueError(
                f"a value ref is exactly one of source/surface/file, got {set_ or 'none'}"
            )
        return self
