"""Action + composition-step models — a flour's ``action:`` and a dough's
``steps:`` shapes.

``ActionDef`` is the single leaf action on a flour (tool / agent / web).
``DoughStep`` / ``EachStep`` / ``AllStep`` are the three composition step shapes;
``parse_step`` dispatches a raw step dict to the right one by key. The 5th
``web:`` shape is registered into ``STEP_KEY_MAP`` by ``models/__init__.py``
(deferred, after ``Dough`` exists — see the load-order note there).

Depends only on ``ports`` (for ``ValueType``); otherwise a leaf. Re-exported
through the ``models`` package facade for back-compat.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from app.utils.base_model import AppBaseModel

from app.doughs.models.ports import ValueType


class ActionDef(AppBaseModel):
    """Top-level action on a flour — exactly one of tool/agent/web.

    Forbidden inside a composition's ``steps:`` array; only valid as a
    Dough-level ``action:`` field on flours.
    """

    tool: str | None = None
    agent: str | None = None
    web: str | None = None

    with_: dict[str, Any] = Field(default_factory=dict, alias="with")
    to: str | dict[str, str] | None = None    # output mapping
    confirm: bool = False

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @model_validator(mode="after")
    def _exactly_one_action(self) -> "ActionDef":
        primitives = [k for k in ("tool", "agent", "web") if getattr(self, k)]
        if len(primitives) == 0:
            raise ValueError(
                "ActionDef must declare exactly one of: tool, agent, web"
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
    with_: dict[str, Any] = Field(default_factory=dict, alias="with")
    optional: bool = False
    confirm: bool = False
    expected_output: ExpectedOutput | None = None

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
    """Process items in batches of this size. Progress events emitted per batch."""

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
        calls). The first item failure cancels the in-flight siblings and
        propagates (same abort semantics as ``each:``).

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
    max_parallel: int = DEFAULT_MAX_PARALLEL  # bounded concurrency cap
    optional: bool = False
    # Per-ITEM failure isolation (default off = legacy fail-fast). When true a
    # failing item is recorded as a failed row with ``None`` output and its
    # siblings keep running — the fan-out completes with holes instead of the
    # first failure cancelling everything. For independent fan-out (per-target
    # agent calls) where one target's error shouldn't sink the rest.
    tolerate_failures: bool = False
    confirm: bool = False
    scale: ScaleConfig | None = None  # soft_cap + strategy (batch_size unused — concurrency replaces batching)
    expected_output: ExpectedOutput | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


STEP_KEY_MAP: dict[str, type] = {
    "dough": DoughStep,
    "each": EachStep,
    "all": AllStep,
}
# `web:` is registered here by ``models/__init__.py`` (deferred import, after
# Dough exists). See ``models/__init__.py`` and ``web_dough.py`` load-order notes.


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
