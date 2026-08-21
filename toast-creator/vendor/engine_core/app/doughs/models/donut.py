"""Donut (bake-result) + execution models — a submodule of the ``models/`` package.

The runtime side of the dough engine: what a bake *produces* and the journal
it records. Depends one-way on the leaf base modules (``enums`` for
``FailureClass``/``RecoveryTier``/``WorkflowEventType``, ``ports`` for
``DisplayKind``); nothing on the definition side (``Dough`` and its parts)
references back here, so the cut is acyclic and this module is import-order
independent.

**Facade:** the package ``__init__`` (``models/__init__.py``) re-exports every
public name here, so ``from app.doughs.models import Donut`` keeps working
everywhere. New runtime-only code may import straight from this submodule.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, model_validator

from app.utils.base_model import AppBaseModel

from app.doughs.models.enums import FailureClass, RecoveryTier, WorkflowEventType
from app.doughs.models.ports import DisplayKind


class WorkflowEvent(AppBaseModel):
    """One entry in the Donut's chronological event log."""

    seq: int
    at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: WorkflowEventType
    step_key: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class CheckpointState(AppBaseModel):
    """Paused-state marker for mid-bake resume.

    Resolver scope is NOT stored here — it's rebuilt from the donut itself
    (``context.resolved_inputs`` + done-step outputs) via
    ``execution.replay.resolver_from_donut``. This carries only what the donut
    can't otherwise derive: the pending step's confirm preview.
    """

    current_step_index: int = 0
    persisted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ItemResult(AppBaseModel):
    """One iteration of an ``each:`` step.

    Populated by the baker per item processed inside ``_exec_iter``.
    ``value_preview`` / ``output_preview`` mirror StepResult's 500-char
    truncation convention so SSE frames stay small; ``value`` / ``output``
    carry the full payload for on-demand expansion from the persisted
    Donut.
    """

    index: int
    value_preview: str = ""
    value: Any = None
    output_preview: str = ""
    output: Any = None
    status: Literal["done", "failed"] = "done"
    error: str | None = None
    duration_ms: int = 0


class StepResult(AppBaseModel):
    """Flat summary of one step's outcome.

    Simple bakes populate only the top fields. Rich fields are
    empty/None for trivial steps. Full chronology in Donut.events.
    """

    step_key: str
    label: str = ""
    status: Literal["pending", "running", "done", "skipped", "failed", "paused"] = "pending"
    output_preview: str = ""
    output: Any = None
    error: str | None = None
    # Translation key + params from a BakeError. None for raw exceptions —
    # frontend falls back to `error`.
    error_code: str | None = None
    error_params: dict[str, str] | None = None
    duration_ms: int = 0
    passed: bool | None = None        # None if no expected_output defined
    failure_class: FailureClass | None = None
    recovery_used: RecoveryTier | None = None
    decision_reason: str | None = None
    execution_id: str | None = None
    # Populated only for ``each:`` steps — one entry per iteration. None
    # everywhere else; the frontend keys off presence to pick the table
    # renderer over the flat preview.
    items: list[ItemResult] | None = None


class BakeContext(AppBaseModel):
    """What was provided at bake time — for audit/replay."""

    raw_input: str | None = None
    resolved_inputs: dict[str, Any] = Field(default_factory=dict)
    flags: dict[str, bool] = Field(default_factory=dict)
    activated_steps: list[str] = Field(default_factory=list)
    skipped_steps: list[str] = Field(default_factory=list)
    # The root bake's donut_id (the unit the user asked for). Every donut in a
    # bake tree — the root and each recursive/fan-out child — records the SAME
    # root here (from the bake-scoped contextvar), so a child donut traces back
    # to its bake (e.g. promote a web task's web_decide reads by bake_id).
    # Equals the donut's own id for a top-level bake; None outside any bake.
    root_donut_id: str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Donut Result — typed bake output
# ═══════════════════════════════════════════════════════════════════════════════


class ActionResult(AppBaseModel):
    """One action (tool call / side effect) taken during bake."""

    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    success: bool = True


class Artifact(AppBaseModel):
    """One renderable section of a Donut's final result.

    Frontend dispatches by ``kind`` to pick a renderer. The wire shape is
    ``{kind, label, data}`` with ``data`` payload conventions per kind:

    - ``markdown``: ``{ "content": str }``. Rendered as Markdown.
    - ``data_table``: ``{ "rows": list[dict], "columns": list[str] | None }``.
      Generic list-of-records → table; columns inferred from row keys
      when not supplied.
    - ``items_table``: ``{ "rows": list[ItemsTableRow], "step_key": str | None }``.
      Per-iteration audit from an ``each:`` step — input/output preview,
      status badge, error per row. Only produced for outputs that trace
      back to an ``each:`` step.
    - ``browser_tab``: ``{ "url": str, "title": str | None, "tab_id": str | None }``.
      Points at a browser tab the bake left open. Producer-side wiring
      is deferred until a real flour emits one.
    - ``app_window``: ``{ "app": str, "pid": int | None, "label": str | None }``.
      Native app the bake launched. Producer-side wiring deferred.
    - ``shopping``: ``{ "title"?: str, "summary"?: str, "results": list[dict] }``.
      Product-card grid — the frontend renders it through the ``<Spread>``
      ``shopping`` template (image + price + rating + merchant per result).
    - ``raw``: ``{ "value": Any }``. JSON fallback for object outputs
      without a more specific renderer.
    """

    kind: DisplayKind
    label: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class DonutResult(AppBaseModel):
    """Typed result of a bake — text-summary + artifacts.

    Always emits a ``text`` summary (one or two lines describing the
    outcome). Beyond that, ``artifacts`` is an ordered list of typed
    sections; the frontend renders one panel per artifact dispatched
    by ``kind``.

    ``type`` is a coarse classifier:
      - text:   no side-effecting steps ran
      - action: side-effecting steps ran
      - mixed:  both
    """

    type: Literal["text", "action", "mixed"]
    text: str = ""
    actions: list[ActionResult] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)


def new_donut_id() -> str:
    """Allocate a fresh, opaque donut id (ephemeral run identifier)."""
    return uuid.uuid4().hex[:12]


class Donut(AppBaseModel):
    """Bake result + execution journal.

    The Donut IS the journal:
    - steps[]      = flat summary (what happened)
    - events[]     = chronological event log (how/why)
    - checkpoint   = resume state (where to continue)
    - glaze        = settings snapshot (what knobs were set)
    """

    version: int = 1

    id: str
    dough_path: str
    dough_version: str = "1"

    status: Literal["baking", "done", "done_with_errors", "failed", "paused"] = "baking"
    glaze: Glaze = Field(default_factory=lambda: Glaze())
    steps: list[StepResult] = Field(default_factory=list)
    events: list[WorkflowEvent] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    result: DonutResult | None = None
    error: str | None = None
    # First failed step's code/params, lifted so list views can localize
    # without fetching the full step array.
    error_code: str | None = None
    error_params: dict[str, str] | None = None

    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    duration_ms: int = 0

    checkpoint: CheckpointState | None = None
    context: BakeContext = Field(default_factory=BakeContext)
    llm_call_count: int = 0
    recovery_count: int = 0

    @model_validator(mode="before")
    @classmethod
    def _drop_retired_carriers(cls, data: Any) -> Any:
        """Retired render keys are DROPPED, not upgraded.

        A donut carried the render spec for three eras — ``view``, then
        ``spread``/``spark``, then a folded ``spread`` — and carries none now:
        the layout belongs to the dough and is read when a card is built.

        Dropped rather than refused, and the asymmetry with the canvas node is
        deliberate: a donut is the RUN — its steps, timings, errors and output —
        and the render spec was one optional field on it. Refusing the record
        would throw away a bake's whole history to save a card, so the old keys
        are stripped and the donut keeps its run.
        """
        if not isinstance(data, dict):
            return data
        for retired in ("view", "spark", "spread"):
            data.pop(retired, None)
        return data

    def to_summary(self) -> DonutSummary:
        return DonutSummary(
            id=self.id,
            dough_path=self.dough_path,
            status=self.status,
            result_type=self.result.type if self.result else None,
            started_at=self.started_at,
            completed_at=self.completed_at,
            duration_ms=self.duration_ms,
            step_count=len(self.steps),
            error=self.error,
            error_code=self.error_code,
            error_params=self.error_params,
        )


class DonutSummary(AppBaseModel):
    """Lightweight donut metadata for list responses."""

    id: str
    dough_path: str
    status: Literal["baking", "done", "done_with_errors", "failed", "paused"] = "baking"
    result_type: Literal["text", "action", "mixed"] | None = None
    started_at: str
    completed_at: str | None = None
    duration_ms: int = 0
    step_count: int = 0
    error: str | None = None
    error_code: str | None = None
    error_params: dict[str, str] | None = None


# ── Glaze — execution settings for dough baking ─────────────────────


class Glaze(AppBaseModel):
    """Execution settings for baking a dough — two abstract dials, NO model name.

    Sits alongside dough.yaml as glaze.yaml. A glaze never pins a concrete model
    id; it carries an abstract coordinate that the adapter
    (``app.cli.catalog.adapter.resolve``) turns into a concrete call against the
    LIVE catalog at bake time. So a glaze written today still resolves after a
    provider renames its lineup, with zero edits.

    Two orthogonal dials, both ALWAYS applied:
      - ``level``  — the capability rung, cheap → strong:
        ``superlight | light | standard | frontier | apex``. A tier with no model
        on a given provider snaps to the nearest occupied rung (ties → cheaper).
      - ``effort`` — ``low | medium | high | xhigh | max | ultra`` — reasoning
        depth, applied at EVERY level, clamped to the model's own ceiling (ties →
        higher). A separate CLI param for claude/codex; fused into the model id
        for agy. Never silently dropped.

    Provider/level/effort fallback chain (merged leg-by-leg, filling only the
    still-``None`` legs at each step — see ``definitions/glaze.py::resolve``):
    dough glaze.yaml → profile default_glaze.yaml → FLOOR. The FLOOR is the
    profile's LIGHT session (``cli_sessions["light"]`` slot: provider + level +
    effort), else ``Glaze(provider=DEFAULT_AGENT_PROVIDER, level="light")`` — NOT
    a hardcoded opus/frontier. Because there is no model name, the three legs fill
    independently (no provider+model coherent-pair coupling). Recovery/budget
    settings are hardcoded in Baker for now.

    One (level, effort) resolves at the bake root and threads into every nested
    flour; an individual ``agent:`` flour may override either via ``action.level``
    / ``action.effort`` (see ``execution/actions.run_agent_action``).
    """

    provider: str | None = None
    level: str | None = None
    effort: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    confirm_steps: bool = False
