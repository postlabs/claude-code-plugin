"""WebDough — strict subclass of Dough for browser-automation workflows.

A WebDough is a real Dough (same file format, same store, same Baker,
same SSE events). The extras:

  - `web:` as a 5th step type (see WebStep) — browser actions that need
    a live Browser.
  - Strict schema (`extra="forbid"`) so typos and unknown fields at the
    emit boundary fail fast. Generic `Dough` stays permissive.
  - Web-only metadata declared explicitly: `url`, `verified_with`,
    `auto_generated`, `output`.

Load order note
---------------
`WebStep` is defined BEFORE the `from app.doughs.models.dough import Dough`
on purpose. `models/__init__.py` registers `WebStep` into STEP_KEY_MAP via a
deferred import. If someone imports `web_dough` first, the package's
`__init__` will try to pull `WebStep` while `web_dough` is still partially
loaded — so WebStep needs to be available by then. Defining it up top
(before we pull Dough) makes that safe.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field

from app.utils.base_model import AppBaseModel


# ═══════════════════════════════════════════════════════════════════════════════
# Step type — registered in app.doughs.models.STEP_KEY_MAP
# ═══════════════════════════════════════════════════════════════════════════════


class WebStep(AppBaseModel):
    """Browser action step.

    YAML: - web: click            # action verb (click/fill/navigate/...)
            selector: { ... }     # action-specific params — extra="allow"
            save: result          # optional, web-step-local
            when: ${inputs.flag}  # optional, web-step-local
            on_error: continue    # one of fail|continue|retry

    Vocabulary note: ``save:`` / ``when:`` / ``on_error:`` are LEGAL on
    WebStep (they're how the recorder emits gating/output bindings).
    They are FORBIDDEN on composition-level ``DoughStep`` / ``EachStep``
    via ``rules.FORBIDDEN_STEP_KEYS`` — those are composition keys
    the validator rejects with a lift-to-flour hint. Web doughs operate
    at a lower abstraction tier (browser action sequences); the strict
    composition rules don't apply.

    Action-specific params (`selector`, `target_ref`, `value`, `url`,
    `timeout`, `state`, `direction`, ...) are intentionally not modeled
    here — they pass through via `extra="allow"`. A per-verb strict
    schema is a future refactor.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    web: str
    save: str | None = None
    when: str | None = None
    on_error: Literal["fail", "continue", "retry"] = "continue"


# ─── Defer Dough import until after WebStep is available ───────────────
# models/__init__.py's STEP_KEY_MAP registration pulls WebStep from this module.
# Keeping this import below WebStep ensures the reverse import works
# regardless of which module is loaded first.
from app.doughs.models.dough import Dough  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════
# Web-only output shape
# ═══════════════════════════════════════════════════════════════════════════════


class WebDoughOutput(AppBaseModel):
    """Declarative shape hint for the action's public output.

    Used by evaluator, docs, and UI. The resolver consumes the Dough's
    `return:` contract, not this — this is metadata only.
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    fields: list[str] = []


# ═══════════════════════════════════════════════════════════════════════════════
# WebDough — Dough subclass with source-locked strict schema
# ═══════════════════════════════════════════════════════════════════════════════


class WebDough(Dough):
    """Strict Dough for web-automation flows.

    Class is identified by id shape (``web.<site>.<action>``); see
    ``app.doughs.validation.rules.is_web_dough``. Every legal top-level field is
    declared — ``extra="forbid"`` closes the escape hatch the base Dough
    leaves open (Dough stays permissive because creator/manual doughs
    legitimately carry arbitrary metadata).

    Use at the emit boundary:
        WebDough.model_validate(envelope)

    isinstance(wd, Dough) is True — consumers typed on Dough work
    without modification.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # Discriminator on disk — the loader gates on
    # ``source == "web_dough"`` to distinguish web doughs from custom /
    # fixed ones (see ``web_engine/storage/loader.py``). Locked to a
    # single literal so a stray value can't make the file load as a
    # WebDough when it isn't one.
    source: Literal["web_dough"] = "web_dough"

    # Tighten retrieval metadata to REQUIRED on web doughs. ``Dough``
    # leaves verb/object optional for hand-authored drafts (creator
    # workflow may save before naming a capability), but every WebDough
    # is auto-emitted from planner → generator → envelope or recorder
    # → envelope. Both upstream pipelines force verb/object on their
    # emit schemas (closed 13-verb enum + non-empty noun), so a missing
    # or empty value here means an upstream LLM contract violation —
    # fail loudly at publish instead of silently writing an un-indexed
    # dough that verb-search will never surface. ``min_length=1``
    # rejects the empty-string case (the closed verb enum itself is
    # validated by the emit schemas one layer up, not re-validated
    # here, to avoid maintaining a fourth copy of the 13-verb list).
    verb: str = Field(..., min_length=1)
    object_: str = Field(..., min_length=1, alias="object")

    url: str | None = None
    verified_with: dict[str, Any] = {}
    auto_generated: bool = False
    output: WebDoughOutput | None = None
