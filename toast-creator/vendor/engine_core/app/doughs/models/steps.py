"""Action + composition-step models — a flour's ``action:`` and a dough's
``steps:`` shapes.

``ActionDef`` is the single leaf action on a flour (tool / agent).
``DoughStep`` / ``EachStep`` / ``AllStep`` are the three composition step shapes;
``parse_step`` dispatches a raw step dict to the right one by key.

Depends only on ``ports`` (for ``ValueType``); otherwise a leaf. Re-exported
through the ``models`` package facade for back-compat.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from app.utils.base_model import AppBaseModel

from app.doughs.models.ports import ValueType


class ActionDef(AppBaseModel):
    """Top-level action on a flour — exactly one of tool/agent.

    Forbidden inside a composition's ``steps:`` array; only valid as a
    Dough-level ``action:`` field on flours.
    """

    tool: str | None = None
    agent: str | None = None

    with_: dict[str, Any] = Field(default_factory=dict, alias="with")
    to: str | dict[str, str] | None = None    # output mapping
    confirm: bool = False

    # Per-flour glaze override for an ``agent:`` action. Either dial wins over the
    # resolved bake glaze when set (``action.level or glaze.level`` etc. in
    # ``execution/actions.run_agent_action``); both ``None`` → the flour inherits
    # the bake's resolved (level, effort). ``level`` = model family rung
    # (light/standard/frontier); ``effort`` = reasoning depth.
    level: str | None = None
    effort: str | None = None

    timeout_ms: int | None = None
    """Per-action override for the leaf-tool execution timeout. Provider
    *refresh/sweep* tools do many calls (enumerate + N history fetches) and
    legitimately exceed the 30s default meant for a single HTTP hit; they
    declare a longer budget here. None → the engine default."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="after")
    def _exactly_one_action(self) -> "ActionDef":
        primitives = [k for k in ("tool", "agent") if getattr(self, k)]
        if len(primitives) == 0:
            raise ValueError(
                "ActionDef must declare exactly one of: tool, agent"
            )
        if len(primitives) > 1:
            raise ValueError(
                f"ActionDef may declare only one action; got {primitives}"
            )
        return self


class ExpectedOutput(AppBaseModel):
    """Declares what a step's output should look like for pass/fail checking.

    Baker compares actual vs expected after each step. On mismatch,
    recovery sends expected+actual to a light CLI session (LLM decides).
    """

    type: ValueType
    shape: str | None = None      # optional description (e.g. "list of email objects with subject, from")
    example: Any | None = None    # optional example value for the LLM to compare against

    model_config = ConfigDict(extra="allow")


class RecoveryAction(AppBaseModel):
    """Single recovery tier action."""

    action: Literal["normalize", "widen", "rank", "retry", "surface"]
    message: str | None = None
    max_attempts: int | None = None
    backoff_ms: int | None = None
    config: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class DoughStep(AppBaseModel):
    """Call another dough — flour or composition.

    YAML: - dough: compose_reply
            with: { email: ${email}, tone: ${inputs.tone} }
    """

    dough: str
    # OPTIONAL — the target's uid `<handle>.do-<hex>`, carried beside the path ref
    # as a verify/heal token: the path resolves (the path IS the dir), and WHEN a
    # uid is present it confirms the resolved dir is the same artifact and heals a
    # moved ref. Absent for a freshly authored step (nothing stamps it at write
    # today — only `scripts/stamp_step_uids.py` fills the kit source); a required
    # field would refuse every authored composition at parse. Path-only resolution
    # is the graceful fallback.
    dough_uid: str = ""
    with_: dict[str, Any] = Field(default_factory=dict, alias="with")
    optional: bool = False
    confirm: bool = False
    expected_output: ExpectedOutput | None = None

    # ── Dynamic dispatch (route) — OPTIONAL, additive, presence-guarded ──
    # When ``route`` is set, ``dough`` is a ``${ref}`` that resolves to a KEY
    # (a handle like "browser"/"bake"/"read"/"fs") and ``route`` maps that key
    # to the whitelisted dough id to call. The whitelist IS the security
    # boundary — the resolved key can only pick an author-declared target,
    # never an arbitrary dough id. When ``route`` is None (every shipped dough
    # + every test) the executor early-returns the literal ``dough`` untouched,
    # so behavior is byte-identical. Honored only under a
    # ``_ROUTE_ALLOWED_PREFIXES`` ancestor (side-channel gate; see executors
    # ``_route_dough_path``).
    route: dict[str, str] | None = None
    # Stable publish name for a routed step so every route target's output
    # lands under ONE scope name (e.g. ``act``), keeping downstream ``${act.…}``
    # refs stable across handles. None (all existing steps) → the publisher
    # name falls back to ``bare_dough_path(step.dough)`` (byte-identical).
    publish_as: str | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ScaleConfig(AppBaseModel):
    """Controls batching and prioritization for each: steps with large lists.

    When a prior step returns e.g. 78 mail threads, processing all sequentially
    is too slow. ScaleConfig tells the baker how to batch and prioritize.

    YAML: - each: ${threads}
            scale:
              soft_cap: 20
              batch_size: 10
              strategy: unread_then_recent
    """

    soft_cap: int = 50
    """Process at most this many items. Items beyond soft_cap are dropped."""

    batch_size: int = 10
    """Process items in batches of this size. Progress events emitted per batch.
    ``each:`` only — ``all:`` runs concurrently instead and rejects it."""

    strategy: Literal[
        "recent_first", "oldest_first", "unread_then_recent", "as_is"
    ] = "as_is"
    """Ordering strategy applied before soft_cap truncation."""


class EachStep(AppBaseModel):
    """Iterate over a list, run sub-steps per item.

    The body's last ``dough:`` step's outputs auto-promote to lists in
    the surrounding scope (so ``${calendar_write_fragment}`` after the
    loop is the list of per-iteration values). Sub-steps reference the
    current item via ``${as_name}``.

    YAML: - each: ${unanswered}
            as: email
            max: 10
            do:
              - dough: compose_reply
                with: { email: ${email}, tone: ${inputs.tone} }
    """

    each: str                         # ${ref} to list
    as_: str = Field(default="item", alias="as")
    do: list[dict[str, Any]] = Field(default_factory=list)
    max: int | str | None = None      # int literal or ${ref} resolved at run time
    # Let an item's failure leave a hole instead of aborting the sequence.
    #
    # ★ Declared here, not inherited by accident. ``_exec_iter`` has always read
    # it with ``getattr``, so an ``each:`` carrying the key worked only because
    # ``extra="allow"`` let it through — a load-bearing flag surviving on a
    # permissive-config technicality, invisible to anyone reading the model.
    #
    # It matters for an ESCALATION body, where the iteration exists to IMPROVE a
    # result that already exists. Measured: ``act_extract``'s R2 rung re-clicks a
    # region using a ref from the R1 snapshot, an SPA re-rendered between the two,
    # and the stale-ref failure propagated — so all 8 targets of a fan-out
    # returned null while each one's R1 read sat complete in hand. An escalation
    # allowed to destroy what it was refining is worse than no escalation.
    tolerate_failures: bool = False
    optional: bool = False
    confirm: bool = False
    scale: ScaleConfig | None = None  # batching and prioritization config
    expected_output: ExpectedOutput | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# Default concurrency cap for `all:` steps without an explicit ``max_parallel``.
# Bounded so a large list can't spawn unbounded coroutines / browser tabs /
# kit API calls at once. See AllStep below.
DEFAULT_MAX_PARALLEL = 8

# Hard ceiling on ``all:`` concurrency. The validator rejects a ``max_parallel``
# outside ``1..MAX_PARALLEL_CEILING``, and the executor clamps to it as a
# belt-and-suspenders (a child dough isn't re-validated at bake time). Keeps the
# "bounded fan-out" promise real even when an author sets an absurd value.
MAX_PARALLEL_CEILING = 32


class AllStep(AppBaseModel):
    """Run sub-steps over a list CONCURRENTLY — the parallel sibling of ``each:``.

    Same body grammar as ``each:`` (``as:``, ``do:``, ``max:``, ``scale:``);
    the difference is **execution policy**, which the shape declares outright:

      - ``each:`` runs items in order, one at a time — ordered side-effects,
        rate-friendly, and the first item failure aborts the rest mid-sequence.
      - ``all:`` runs items concurrently up to ``max_parallel`` — the right
        shape for independent fan-out (multi-source gather, per-item agent
        calls). ``tolerate_failures`` picks the failure policy: off (default)
        the first item failure cancels the in-flight siblings and propagates,
        like ``each:``; on, that item becomes a ``None`` hole in the output
        list and its siblings run to completion.

    Items are scope-isolated *by construction* — each item forks the resolver
    (``resolver.child()``), so the body cannot read another item's output and
    sub-step refs never cross items. The output list and the per-item results
    preserve INPUT order regardless of completion order. Because items are
    isolated, the only thing ``all:`` gives up vs ``each:`` is side-effect
    ORDERING and serial rate — so only reach for ``all:`` when item order does
    not matter (the creator guide carries that contract; it is not statically
    checkable).

    YAML: - all: ${queries}
            as: q
            max_parallel: 8
            do:
              - dough: search_web
                with: { query: ${q} }
    """

    all_: str = Field(alias="all")    # ${ref} to list
    as_: str = Field(default="item", alias="as")
    do: list[dict[str, Any]] = Field(default_factory=list)
    max: int | str | None = None      # int literal or ${ref} resolved at run time
    # Same two shapes as ``max``, for the same reason one step down: the width a
    # fan-out should run at is not always knowable when the dough is written.
    # ``act_run``'s is the user's ``lightsession_concurrency`` — live, per
    # profile, [1,32] — and a YAML literal cannot follow it, so raising the
    # setting used to change nothing and lowering it left tabs open with no
    # emit to run. A ``${ref}`` here lets one user-owned number move both.
    # ★ A ref TRADES AWAY AUTHOR-TIME CHECKING: the range test in
    # ``validation/engine.py`` cannot run on a value that does not exist yet, so
    # it moves to the executor's clamp. The shared-tab guard in
    # ``validation/checks.py`` does NOT move — it treats a ref as parallel,
    # because "might be >1" has to be handled like ">1".
    max_parallel: int | str = DEFAULT_MAX_PARALLEL  # bounded concurrency cap
    optional: bool = False
    # Per-ITEM failure isolation — see the failure-policy bullet above. Whatever
    # consumes the output list must handle ``None`` holes.
    tolerate_failures: bool = False
    confirm: bool = False
    # soft_cap + strategy only — concurrency replaces batching, so a `batch_size`
    # here is validator-rejected (ALL_STEP_BATCH_SIZE) rather than silently ignored.
    scale: ScaleConfig | None = None
    expected_output: ExpectedOutput | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


STEP_KEY_MAP: dict[str, type] = {
    "dough": DoughStep,
    "each": EachStep,
    "all": AllStep,
}


def parse_step(raw: dict[str, Any]) -> DoughStep | EachStep | AllStep:
    """Parse a raw step dict by detecting which key is present."""
    for key, model_cls in STEP_KEY_MAP.items():
        if key in raw:
            return model_cls.model_validate(raw)
    raise ValueError(
        f"Unknown step type. Expected one of {list(STEP_KEY_MAP.keys())}, "
        f"got keys: {list(raw.keys())}"
    )


def parse_steps(raw_list: list[dict[str, Any]]) -> list:
    """Parse a list of raw step dicts."""
    return [parse_step(s) for s in raw_list]
