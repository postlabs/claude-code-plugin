"""Box — the i18n display sidecar models (``box.yaml``).

Lives next to ``dough.yaml`` and carries all display text in multiple
languages. These are the data shapes; the load/save/merge/compose *logic* is
in ``box.py``. Leaf module (no ``app.doughs`` imports). Re-exported through
``models`` for back-compat.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, field_validator

from app.utils.base_model import AppBaseModel


class FieldBox(AppBaseModel):
    """Display text for one input or output entry inside a box.yaml locale.

    Two tiers:

    - ``name`` — short label rendered in bake-form fields and binding rows.
    - ``description`` — the behavioral sentence: the form hint, and the
      per-field prose ``query.spec()`` hands the agent. When empty, both
      slots stay blank.

    Legacy flat-string entries from older box.yaml files are accepted at
    load time and normalized to ``{name: <string>, description: ""}`` —
    see :meth:`BoxLocale._normalize_field_map`. On save, every entry is
    written as the structured form (no flat strings emitted).

    ``extra="forbid"`` so misspelled keys (``label:``, ``hint:``) fail
    loudly at load.
    """

    name: str = ""
    description: str = ""

    model_config = ConfigDict(extra="forbid")


class BoxLocale(AppBaseModel):
    """Single-locale display text for a dough.

    ``inputs`` / ``outputs`` carry structured :class:`FieldBox` entries
    keyed by input/output name. Legacy flat-string entries (``key: <label>``)
    are accepted at load and normalized to ``FieldBox(name=<label>)``.

    ``steps`` is a flat ``key → label`` map (e.g. ``load_queue: "Load queue"``)
    — this dough's OWN override for what a step is called. Object-form entries
    from older box.yaml files are accepted and normalized to the plain string
    form at load time. Absent, the reader resolves the label from the called
    dough itself.
    """

    name: str
    about: str = ""
    inputs: dict[str, FieldBox] = Field(default_factory=dict)
    outputs: dict[str, FieldBox] = Field(default_factory=dict)
    steps: dict[str, str] = Field(default_factory=dict)

    @field_validator("inputs", "outputs", mode="before")
    @classmethod
    def _normalize_field_map(cls, raw: Any) -> Any:
        return _coerce_field_map(raw)

    @field_validator("steps", mode="before")
    @classmethod
    def _normalize_steps(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        out: dict[str, str] = {}
        for key, val in raw.items():
            if isinstance(val, str):
                out[key] = val
            elif isinstance(val, dict):
                out[key] = val.get("label", "")
        return out

    def to_yaml_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_defaults=True, exclude_none=True)


def _coerce_field_map(raw: Any) -> Any:
    """Turn legacy ``{key: <str>}`` entries into ``{key: {name: <str>}}``."""
    if not isinstance(raw, dict):
        return raw
    out: dict[str, Any] = {}
    for key, val in raw.items():
        if isinstance(val, str):
            out[key] = {"name": val}
        else:
            out[key] = val
    return out


class Box(AppBaseModel):
    """Multi-locale display text container (box.yaml).

    Top-level keys are locale codes. Validated as a root dict of BoxLocale
    entries. ``en`` is the full block; a non-``en`` locale carries ``name``
    only — see ``definitions/box.py`` for why, and
    ``checks.box_completeness`` for the gate.

    YAML shape:
      en:
        name: Morning Briefing
        about: Fetch unread emails ...
        inputs:
          email_account: Gmail account
        steps:
          emails: Fetch unread emails
      ko:
        name: 모닝 브리핑
    """

    locales: dict[str, BoxLocale] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")

    @classmethod
    def from_yaml_dict(cls, data: dict) -> "Box":
        """Parse raw YAML dict (locale keys at top level) into Box."""
        locales = {}
        for key, val in data.items():
            if isinstance(val, dict):
                locales[key] = BoxLocale(**val)
        return cls(locales=locales)

    def to_yaml_dict(self) -> dict:
        """Convert back to flat dict for YAML serialization."""
        return {
            locale: loc.to_yaml_dict()
            for locale, loc in self.locales.items()
        }

    def get_locale(self, locale: str) -> BoxLocale | None:
        """Get locale data with base-language fallback (ko-KR → ko)."""
        loc = self.locales.get(locale)
        if not loc and "-" in locale:
            loc = self.locales.get(locale.split("-")[0])
        return loc
