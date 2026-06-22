"""The ``Dough`` root model.

``Dough`` is the parent model of the dough engine; its child models live in
sibling modules (``ports``, ``box``, ``steps``, ``enums``) and are imported
here. The package ``__init__`` re-exports everything as the public facade and
wires the deferred ``web:`` step. See ``app/doughs/models/__init__.py``.

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

    id: str
    version: str = "1"
    icon: str = ""
    # Derived from id at load (the parent slash-path; everything before the
    # leaf segment). NOT persisted — ``to_yaml_dict`` omits it — and NOT used
    # for path resolution (the id IS the path; see ``store._dough_dir``). Kept
    # as a constructor input so model_validate(data) and clone update={} still
    # accept it; it always mirrors the id's path prefix.
    folder: str = "user"

    # Capability metadata for retrieval. Kit flours inherit verb/object
    # from kit.yaml::provides[]; user doughs (user.*) carry them
    # top-level on dough.yaml. Both are optional on the model (user
    # may save a draft without them) — only set values are indexed by
    # retrieval's verb-search path. `object_` uses an alias so YAML
    # writes the natural ``object:`` key without clashing with the
    # Python builtin.
    verb: str | None = None
    object_: str | None = Field(default=None, alias="object")

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

    # --- Public output contract (mandatory) ---
    return_: dict[str, str] = Field(alias="return")

    # --- Recovery per failure class ---
    recovery: dict[str, list[RecoveryAction]] = Field(default_factory=dict)

    # --- Display labels (populated from box.yaml at API time, not stored) ---
    # ``input_meta`` / ``output_meta`` carry the per-key FieldBox (short
    # ``name`` + longer ``description``) for the active locale, with
    # per-key en fallback. ``step_input_meta`` does the same for each
    # called flour's inputs (keyed by bare flour id, then by input key).
    step_labels: dict[str, str] = Field(default_factory=dict)
    step_input_meta: dict[str, dict[str, FieldBox]] = Field(default_factory=dict)
    input_meta: dict[str, FieldBox] = Field(default_factory=dict)
    output_meta: dict[str, FieldBox] = Field(default_factory=dict)

    # --- Metadata ---
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def get_steps(self) -> list:
        """Parse raw step dicts into typed step models."""
        return parse_steps(self.steps)

    def baker_view(self, box: "Box | None" = None, locale: str = "en") -> dict[str, Any]:
        """Minimal projection for the baker LLM (~100-150 tokens).

        Strips fixed values, steps, recovery, metadata.
        Only includes what the baker needs to parse user input.
        Includes the box.yaml input description as a ``# <hint>`` so small
        LLMs can map user intent onto declared inputs. Text (name/about/
        description) resolved from Box with per-key locale → en fallback.
        """
        from app.doughs.definitions.box import resolve_input_meta, resolve_text

        text = resolve_text(box, locale) if box else {}
        meta = resolve_input_meta(box, locale) if box else {}
        view: dict[str, Any] = {}
        if text.get("name"):
            view["name"] = text["name"]
        if text.get("about"):
            view["about"] = text["about"]

        promptable: dict[str, str] = {}
        flags: dict[str, Any] = {}

        for name, inp in self.inputs.items():
            # Skip fixed/hidden inputs
            if inp.value is not None or not inp.visible:
                continue
            # Boolean with default → flag
            if inp.type == "boolean" and inp.default is not None:
                flags[name] = inp.default
            else:
                # Promptable input — include type, default, and box hint
                desc = inp.type
                if inp.default is not None:
                    desc += f"={inp.default}"
                entry = meta.get(name)
                if entry and entry.description:
                    desc += f"  # {entry.description}"
                promptable[name] = desc

        if promptable:
            view["inputs"] = promptable
        if flags:
            view["flags"] = flags
        return view

    def catalog_entry(self, box: "Box | None" = None, locale: str = "en") -> dict[str, Any]:
        """Lightweight entry for catalog / discoverability.

        Includes: id, name, about, kind, input/output summary.
        Used for search, browsing, and Creator LLM catalog context.
        Text (name/about) resolved from Box.
        """
        from app.doughs.definitions.box import resolve_text

        text = resolve_text(box, locale) if box else {}

        # Summarize inputs
        input_summary: list[str] = []
        for inp_name, inp in self.inputs.items():
            if inp.value is not None:
                continue  # skip fixed/hidden
            marker = "?" if not inp.required else ""
            input_summary.append(f"{inp_name}: {inp.type}{marker}")

        # Summarize outputs from return
        output_names = list(self.return_.keys()) if self.return_ else []

        entry: dict[str, Any] = {
            "id": self.id,
            "name": text.get("name", self.id),
            "kind": self.kind,
        }
        if text.get("about"):
            entry["about"] = text["about"]
        if input_summary:
            entry["inputs"] = input_summary
        if output_names:
            entry["outputs"] = output_names
        return entry

    def to_yaml_dict(self) -> dict[str, Any]:
        """Convert to dict for YAML serialization. Compact — omits empty/default values.

        Never writes `kind:` — it's a derived `@property` inferred from shape
        (`action:` → flour, `steps:` → dough). The validator explicitly
        rejects YAML with `kind:` (``validate_yaml`` via ``FORBIDDEN_PRE_PARSE_KEYS``),
        so emitting it here would make every saved dough fail its own next validate pass.
        """
        d: dict[str, Any] = {}
        if self.icon:
            d["icon"] = self.icon
        if self.verb:
            d["verb"] = self.verb
        if self.object_:
            d["object"] = self.object_
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
        d["return"] = self.return_
        if self.recovery:
            d["recovery"] = {
                k: [a.model_dump(exclude_none=True) for a in v]
                for k, v in self.recovery.items()
            }
        return d
