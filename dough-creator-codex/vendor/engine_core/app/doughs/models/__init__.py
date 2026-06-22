"""Dough Engine data models — package facade.

The model set is split across focused submodules; this ``__init__`` is the
**public facade** that re-exports them so ``from app.doughs.models import X``
resolves for every model. New code may import straight from the submodule
(``from app.doughs.models.donut import Donut``).

This is the one sanctioned re-export ``__init__`` in the backend (the general
rule bans re-export ``__init__`` files — see ``src/backend/CLAUDE.md``). The
exception is narrow and legitimate: it preserves the public API of what used to
be a single ``models.py``, split into a package for file size. It is NOT a
licence for new barrel ``__init__`` files elsewhere.

Layering (leaf → root), strictly acyclic:

    enums ─┬─► ports ─┬─► steps ─┐
           │          └─► box ───┤
           │                     ├─► dough ─► (this facade)
           └─► (donut) ◄─ ports ─┘

``dough`` owns the ``Dough`` root model; ``donut`` owns the runtime/result
models and rides on the same leaves. The deferred ``web:`` step registration
happens here, after ``Dough`` exists (``web_dough`` subclasses it).
"""

from app.doughs.models.enums import (
    FailureClass,
    RecoveryTier,
    WorkflowEventType,
)
from app.doughs.models.ports import (
    DEFAULT_DISPLAY_BY_TYPE,
    DISPLAY_REQUIRED_TYPES,
    DisplayKind,
    InputDef,
    OutputDef,
    ValueType,
)
from app.doughs.models.box import Box, BoxLocale, FieldBox
from app.doughs.models.steps import (
    DEFAULT_MAX_PARALLEL,
    MAX_PARALLEL_CEILING,
    STEP_KEY_MAP,
    ActionDef,
    AllStep,
    DoughStep,
    EachStep,
    ExpectedOutput,
    RecoveryAction,
    ScaleConfig,
    parse_step,
    parse_steps,
)
from app.doughs.models.dough import Dough
from app.doughs.models.donut import (
    ActionResult,
    Artifact,
    BakeContext,
    CheckpointState,
    Donut,
    DonutResult,
    DonutSummary,
    Glaze,
    ItemResult,
    StepResult,
    WorkflowEvent,
    new_donut_id,
)

# ── Deferred `web:` step registration ────────────────────────────────────────
# `web_dough` subclasses `Dough`, so it can't be imported until `Dough` exists.
# Import the source submodule directly (`...models.dough`, done above) so this
# wiring doesn't depend on facade load order.
from app.doughs.models.web_dough import WebStep as _WebStep

STEP_KEY_MAP["web"] = _WebStep


__all__ = [
    # enums
    "FailureClass", "RecoveryTier", "WorkflowEventType",
    # ports
    "ValueType", "InputDef", "OutputDef", "DisplayKind",
    "DISPLAY_REQUIRED_TYPES", "DEFAULT_DISPLAY_BY_TYPE",
    # box
    "FieldBox", "BoxLocale", "Box",
    # steps / actions
    "ActionDef", "ExpectedOutput", "RecoveryAction", "DoughStep", "ScaleConfig",
    "EachStep", "AllStep", "DEFAULT_MAX_PARALLEL", "MAX_PARALLEL_CEILING",
    "STEP_KEY_MAP", "parse_step", "parse_steps",
    # dough
    "Dough",
    # donut / runtime
    "WorkflowEvent", "CheckpointState", "ItemResult", "StepResult", "BakeContext",
    "ActionResult", "Artifact", "DonutResult", "new_donut_id", "Donut",
    "DonutSummary", "Glaze",
]
