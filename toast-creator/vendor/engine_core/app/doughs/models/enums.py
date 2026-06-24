"""Dough engine enums — the small shared base.

Leaf module (no ``app.doughs`` imports). Both the definition side
(``dough``/``steps``/``ports``) and the runtime side (``donut``) build on
these. Re-exported through the ``models`` package facade for back-compat
(`from app.doughs.models import FailureClass` keeps working).
"""

from __future__ import annotations

from enum import Enum


class FailureClass(str, Enum):
    empty = "empty"
    ambiguous = "ambiguous"
    transient = "transient"
    schema = "schema"
    policy = "policy"
    auth = "auth"


class RecoveryTier(str, Enum):
    normalize = "normalize"
    widen = "widen"
    retry = "retry"


class WorkflowEventType(str, Enum):
    step_started = "step_started"
    step_succeeded = "step_succeeded"
    step_failed = "step_failed"
    step_skipped = "step_skipped"
    recovery_started = "recovery_started"
    recovery_succeeded = "recovery_succeeded"
    recovery_failed = "recovery_failed"
    user_prompted = "user_prompted"
    user_responded = "user_responded"
    child_bake_started = "child_bake_started"
    child_bake_completed = "child_bake_completed"
    side_effect_prepared = "side_effect_prepared"
    side_effect_confirmed = "side_effect_confirmed"
    checkpoint_saved = "checkpoint_saved"
    bake_resumed = "bake_resumed"
