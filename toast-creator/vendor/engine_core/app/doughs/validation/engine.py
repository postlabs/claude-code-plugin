"""Dough definition validation — v2 schema with ${ref} strings.

Two entry points:

- :func:`validate` — validate a parsed :class:`Dough`. ``scope="save"``
  (default) runs pre-write checks; ``scope="load"`` runs boot-time
  checks (cross-ref protection between fixed and custom doughs).
- :func:`validate_yaml` — accept a raw YAML dict, parse to ``Dough``,
  run pre-write checks. Surfaces both ``FORBIDDEN_PRE_PARSE_KEYS``
  rejections (shape-inferred fields) and standard validation issues.

:func:`validate_dough_path` lives in ``id_utils.py`` — it validates an id
string, not a Dough. Reference drilling lives in ``drill.py``.

Issues are :class:`ValidationIssue` instances — a ``str`` subclass
carrying ``code`` (from :class:`ValidationCode`), ``message`` (English
fallback), ``hint`` (actionable next-step suggestion), and ``params``
(i18n interpolation values). Frontend renders via
``i18n.t('validation.<code>', params)``; backend callers reading
``str(issue)`` get ``"<message> — hint: <hint>"``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ValidationError as PydanticValidationError

from app.doughs.validation import checks, drill
from app.doughs.definitions.ids import bare_dough_path, last_dough_id_in_steps
from app.doughs.execution.resolver import REF_PATTERN
from app.doughs.models import (
    MAX_PARALLEL_CEILING,
    Dough,
    AllStep, DoughStep, EachStep,
    parse_step,
)
from app.spreads.validate import composition_spec
from app.spreads.spark.validate import TargetInputs, spark_spec
from app.spreads.spark import model as spark_model
from app.doughs.validation.rules import (
    custom_prefix,
    FORBIDDEN_PRE_PARSE_KEYS,
    FORBIDDEN_STEP_KEYS,
    is_fixed,
    is_kit_dough,
)

if TYPE_CHECKING:
    from app.doughs.definitions.service import DoughStore
    from app.doughs.models import Box

Scope = Literal["save", "load"]


class ValidationCode(StrEnum):
    """Build-time validation codes. Frontend maps each to a
    ``validation.<code>`` i18n key (mirrors ``BakeErrorCode`` →
    ``error.<code>`` at bake time).

    Adding a new issue:
      1. Append a new code here (don't rename existing ones).
      2. Pass it as ``code=`` to ``_issue(...)`` at the producer site.
      3. Add ``validation.<code>`` keys to ``i18n/locales/{ko,en}/doughs.ts``.
    """
    DOUGH_HAS_NEITHER = "dough_has_neither"
    DOUGH_HAS_BOTH = "dough_has_both"
    RETURN_MISSING = "return_missing"
    FORBIDDEN_PRE_PARSE_KEY = "forbidden_pre_parse_key"
    ACTION_TO_UNDECLARED = "action_to_undeclared"
    ACTION_TO_DICT_KEY_UNDECLARED = "action_to_dict_key_undeclared"
    STEP_PARSE_FAILED = "step_parse_failed"
    DOUGH_STEP_MISSING_REF = "dough_step_missing_ref"
    EACH_STEP_MISSING_ITER = "each_step_missing_iter"
    EACH_STEP_MISSING_DO = "each_step_missing_do"
    ALL_STEP_MISSING_ITER = "all_step_missing_iter"
    ALL_STEP_MISSING_DO = "all_step_missing_do"
    ALL_STEP_MAX_PARALLEL_RANGE = "all_step_max_parallel_range"
    ALL_STEP_BATCH_SIZE = "all_step_batch_size"
    ALL_STEP_SHARED_TAB_HANDLE = "all_step_shared_tab_handle"
    STEP_INLINE_PRIMITIVE_FORBIDDEN = "step_inline_primitive_forbidden"
    STEP_MULTIPLE_KEYS = "step_multiple_keys"
    STEP_WITH_KEY_UNKNOWN = "step_with_key_unknown"
    STEP_WITH_REQUIRED_MISSING = "step_with_required_missing"
    STEP_UNKNOWN_SHAPE = "step_unknown_shape"
    STEP_FIELD_SAVE_REMOVED = "step_field_save_removed"
    STEP_FIELD_WHEN_REMOVED = "step_field_when_removed"
    STEP_FIELD_ON_ERROR_REMOVED = "step_field_on_error_removed"
    STEP_LITERAL_ARIA_REF = "step_literal_aria_ref"
    WEB_QUERY_NEVER_APPLIED = "web_query_never_applied"
    LOGIN_CONTRACT_INCOMPLETE = "login_contract_incomplete"
    RUN_STEPS_DRIVE_UNGUARDED = "run_steps_drive_unguarded"
    USER_FLOUR_TOOL_FORBIDDEN = "user_flour_tool_forbidden"
    INPUT_REF_UNDECLARED = "input_ref_undeclared"
    REF_NO_PUBLISHER = "ref_no_publisher"
    REF_DRILL_FIELD_NOT_FOUND = "ref_drill_field_not_found"
    REF_SHAPE_MISMATCH = "ref_shape_mismatch"
    DUP_PUBLISH = "dup_publish"
    RETURN_REF_NO_PUBLISHER = "return_ref_no_publisher"
    FIXED_REFS_MISSING_USER = "fixed_refs_missing_user"
    KIT_FLOUR_OUTPUT_MISSING_MODEL = "kit_flour_output_missing_model"
    AGENT_OBJECT_OUTPUT_NEEDS_SCHEMA = "agent_object_output_needs_schema"
    # Raised when the JSON Schema under `outputs.<x>.schema` has a root
    # `type:` that the engine cannot bind into the declared `out.type` slot.
    # The runtime wrap+unwrap (schema_strict.wrap_root_array) handles the
    # natural list-output case (`out.type: list` + `schema.type: array`); this
    # catches the genuine mismatches the engine can't paper over — e.g.
    # `out.type: object` with `schema.type: array` (wrap fires, returns list,
    # shape check fails with a confusing chain).
    AGENT_SCHEMA_TYPE_MISMATCH = "agent_schema_type_mismatch"
    DOUGH_REF_NOT_FOUND = "dough_ref_not_found"
    OUTPUT_DISPLAY_TYPE_MISMATCH = "output_display_type_mismatch"
    OUTPUT_DISPLAY_REQUIRES_EACH = "output_display_requires_each"
    INVALID_SPREAD = "invalid_spread"
    INVALID_SPARK = "invalid_spark"
    SPREAD_REF_INVALID = "spread_ref_invalid"
    BOX_INPUT_LABEL_MISSING = "box_input_label_missing"
    BOX_OUTPUT_LABEL_MISSING = "box_output_label_missing"
    BOX_INPUT_DESCRIPTION_MISSING = "box_input_description_missing"
    BOX_OUTPUT_DESCRIPTION_MISSING = "box_output_description_missing"
    BOX_INPUT_ORPHAN = "box_input_orphan"
    BOX_OUTPUT_ORPHAN = "box_output_orphan"
    BOX_NON_EN_SLOT = "box_non_en_slot"
    YAML_COMMENT = "yaml_comment"
    # A Pydantic model-schema error (extra/misplaced key, wrong type) surfaced
    # by validate_yaml(strict_schema=True) for callers with no save-path
    # model_validate of their own (the /validate endpoint → peel validate_dough).
    SCHEMA_INVALID = "schema_invalid"


class ValidationIssue(str):
    """A single validation error with a typed code, English message,
    directive hint, and i18n params.

    Subclasses ``str`` so existing ``"\\n".join(f"- {e}" for e in errors)``
    formatting keeps working — ``str(issue)`` returns
    ``"<message> — hint: <hint>"`` when a hint exists, else ``<message>``.
    Structured consumers (the ``/validate`` endpoint, the chat
    auto-validator, the frontend) read ``.code``, ``.params``,
    ``.message``, and ``.hint`` via ``to_dict()``.

    The ``code`` + ``params`` pair mirrors :class:`BakeError` — frontend
    renders ``i18n.t('validation.<code>', params)`` and falls back to
    ``message`` when no translation is registered.
    """

    code: str
    message: str
    hint: str | None
    params: dict[str, str]

    def __new__(
        cls,
        message: str,
        hint: str | None = None,
        *,
        code: ValidationCode,
        params: dict[str, str] | None = None,
    ) -> "ValidationIssue":
        rendered = f"{message} — hint: {hint}" if hint else message
        inst = super().__new__(cls, rendered)
        inst.code = code.value
        inst.message = message
        inst.hint = hint
        inst.params = params or {}
        return inst

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "params": self.params,
        }


def _issue(
    message: str,
    hint: str | None = None,
    *,
    code: ValidationCode,
    params: dict[str, str] | None = None,
) -> ValidationIssue:
    return ValidationIssue(message, hint, code=code, params=params)


def _schema_issues(exc: PydanticValidationError) -> list[ValidationIssue]:
    """Translate a ``Dough.model_validate`` failure into readable issues.

    Only used by ``validate_yaml(strict_schema=True)`` — the path the
    ``/validate`` endpoint (peel ``validate_dough``) takes for a dough that
    exists on disk but is schema-invalid, so an authoring agent gets an
    actionable hint instead of an opaque 404/500. Callers that model-validate
    on their own (the save path) never pass ``strict_schema``.
    """
    issues: list[ValidationIssue] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        etype = err.get("type", "")
        detail = err.get("msg", "invalid value")
        if etype == "missing" and err["loc"] in (("return",), ("return_",)):
            # Reuse the existing code/i18n so the missing-return hint reads
            # identically to the _validate_for_save path.
            issues.append(_issue(
                "Dough has no `return:` block.",
                hint="every flour and dough must declare a `return:` block "
                     "mapping declared `outputs:` names to in-scope ${refs}.",
                code=ValidationCode.RETURN_MISSING,
            ))
        elif etype == "extra_forbidden":
            issues.append(_issue(
                f"`{loc}` is not a valid dough.yaml field.",
                hint="delete this key — field descriptions live in box.yaml, "
                     "not dough.yaml; an input/output def allows only "
                     "type/required/default/options/model.",
                code=ValidationCode.SCHEMA_INVALID,
                params={"loc": loc, "type": etype, "detail": detail},
            ))
        else:
            issues.append(_issue(
                f"`{loc}`: {detail}.",
                code=ValidationCode.SCHEMA_INVALID,
                params={"loc": loc, "type": etype, "detail": detail},
            ))
    return issues


def validate(
    dough: Dough,
    *,
    scope: Scope = "save",
    store: "DoughStore | None" = None,
    all_doughs: dict[str, Dough] | None = None,
    box: "Box | None" = None,
) -> list[ValidationIssue]:
    """Validate a parsed dough. ``store`` is consulted only at
    ``scope="save"`` (``dough:`` ref existence); ``all_doughs`` only at
    ``scope="load"`` (fixed→custom cross-ref protection); ``box`` is
    consulted only at ``scope="save"`` to enforce input/output labels.
    """
    if scope == "save":
        issues = _validate_for_save(dough, store=store)
        if box is not None:
            issues.extend(checks.box_completeness(dough, box))
        return issues
    if scope == "load":
        return _validate_for_load(dough, all_doughs=all_doughs)
    raise ValueError(f"unknown validation scope: {scope!r}")


def validate_yaml(
    dough_dict: dict,
    *,
    store: "DoughStore | None" = None,
    box: "Box | None" = None,
    strict_schema: bool = False,
) -> list[ValidationIssue]:
    """Parse a raw YAML dict as a :class:`Dough` and run :func:`validate`.

    By default returns ``[]`` when the dict isn't a parseable Dough at all —
    load-time schema errors surface on the next disk write through Pydantic,
    and double-reporting them here just duplicates the noise for save-path
    callers that model-validate on their own.

    ``strict_schema=True`` instead surfaces those schema errors as
    ``SCHEMA_INVALID`` / reused ``RETURN_MISSING`` issues (via
    :func:`_schema_issues`). Pass it ONLY from callers with no model_validate
    safety net of their own — today just the ``/validate`` endpoint backing
    the peel ``validate_dough`` tool, so an authoring agent gets an actionable
    hint instead of an opaque 404/500. Every other caller keeps the default.

    Pre-parse rejections (``FORBIDDEN_PRE_PARSE_KEYS``) catch
    shape-inferred fields like ``kind:`` that Pydantic's ``extra="allow"``
    would otherwise absorb silently. Extending the catalogue is a one-line
    edit in ``rules.py`` — no scaffolding here changes.
    """
    pre_errors: list[ValidationIssue] = []
    if isinstance(dough_dict, dict):
        for key, hint in FORBIDDEN_PRE_PARSE_KEYS.items():
            if key in dough_dict:
                pre_errors.append(_issue(
                    f"`{key}:` is not a valid dough.yaml field.",
                    hint=f"delete the `{key}:` line. {hint}",
                    code=ValidationCode.FORBIDDEN_PRE_PARSE_KEY,
                    params={"key": key},
                ))

    try:
        dough = Dough.model_validate(dough_dict)
    except PydanticValidationError as exc:
        if strict_schema:
            return pre_errors + _schema_issues(exc)
        return pre_errors
    issues = pre_errors + _validate_for_save(dough, store=store)
    if box is not None:
        issues.extend(checks.box_completeness(dough, box))
    return issues


def _validate_for_save(
    dough: Dough,
    *,
    store: "DoughStore | None" = None,
) -> list[ValidationIssue]:
    """Full pre-write validation.

    Kind is inferred from shape: ``action:`` → flour; ``steps:`` → dough.
    A dough has exactly one of the two — never both, never neither.

    Composition rules (only ``dough:``, ``each:``, and ``all:`` allowed in steps):
      - Inline action primitives (``tool:`` / ``agent:`` / ``llm:`` /
        ``web:``) are forbidden — lift into a flour, call via ``dough:``.
      - ``save:`` is forbidden — outputs auto-publish from the called
        dough's ``outputs:`` declaration.
      - ``when:`` is forbidden — gating belongs inside flours.
      - ``on_error:`` is forbidden — use ``optional: true`` instead.

    When ``store`` is passed, every ``dough:`` reference in steps
    (including ``each.do`` sub-steps) is also confirmed to resolve to
    a real dough in the registry or user library.
    """
    errors: list[ValidationIssue] = []

    has_steps = bool(dough.steps)
    has_action = dough.action is not None

    if not has_steps and not has_action:
        errors.append(_issue(
            "Dough has neither steps nor action.",
            hint="add `action:` for a flour (single tool/agent call) "
                 "or `steps:` for a dough (composition of other flours/doughs) ",
            code=ValidationCode.DOUGH_HAS_NEITHER,
        ))
        return errors

    if has_steps and has_action:
        errors.append(_issue(
            "Dough has both `action:` and `steps:` — pick one.",
            hint="use `action:` for a flour (single tool/agent step) or "
                 "`steps:` for a dough (composition)",
            code=ValidationCode.DOUGH_HAS_BOTH,
        ))
        return errors

    if has_action:
        errors.extend(checks.action(dough))
        if is_kit_dough(dough.path):
            errors.extend(checks.kit_outputs(dough))

    errors.extend(checks.display_types(dough))

    if dough.spread is not None:
        errors.extend(_spread_issues(dough))
        if spark_model.has_trigger_map(dough.spread):
            errors.extend(_spark_issues(dough, store))

    if dough.default_spread and store is not None:
        errors.extend(_view_ref_issues(dough, store))

    if not dough.return_:
        errors.append(_issue(
            "Dough has no return: block.",
            hint="every flour and dough must declare a `return:` block mapping "
                 "declared `outputs:` names to in-scope ${refs}",
            code=ValidationCode.RETURN_MISSING,
        ))

    if has_action and not has_steps:
        return errors

    errors.extend(checks.step_shapes(dough.steps))

    parsed_steps = []
    for i, raw in enumerate(dough.steps):
        if isinstance(raw, dict) and FORBIDDEN_STEP_KEYS & raw.keys():
            continue  # already reported by checks.step_shapes (R5)
        try:
            step = parse_step(raw)
            parsed_steps.append(step)
        except ValueError as e:
            errors.append(_issue(
                f"Step {i}: {e}",
                hint="composition steps must be `dough:` (call a flour/dough), "
                     "`each:` (iterate in order), or `all:` (iterate "
                     "concurrently). No other shapes are allowed. ",
                code=ValidationCode.STEP_PARSE_FAILED,
                params={"index": str(i), "error": str(e)},
            ))

    if not parsed_steps:
        return errors

    # --- Validate each step has its required ref ---
    for step in parsed_steps:
        if isinstance(step, DoughStep):
            if not step.dough:
                errors.append(_issue(
                    "DoughStep has no dough reference",
                    hint="every `- dough:` step needs a flour/dough id; "
                         "discover candidates: peel flours --object <o> ",
                    code=ValidationCode.DOUGH_STEP_MISSING_REF,
                ))
        elif isinstance(step, EachStep):
            if not step.each:
                errors.append(_issue(
                    "EachStep has no iteration ref",
                    hint="`each:` needs a ${list_ref} from a prior step "
                         "or ${inputs.<list_input>}",
                    code=ValidationCode.EACH_STEP_MISSING_ITER,
                ))
            if not step.do:
                errors.append(_issue(
                    "EachStep has no sub-steps",
                    hint="`each:` requires a `do:` array of inner steps "
                         "(at minimum one `- dough:` call)",
                    code=ValidationCode.EACH_STEP_MISSING_DO,
                ))
        elif isinstance(step, AllStep):
            if not step.all_:
                errors.append(_issue(
                    "AllStep has no iteration ref",
                    hint="`all:` needs a ${list_ref} from a prior step "
                         "or ${inputs.<list_input>}",
                    code=ValidationCode.ALL_STEP_MISSING_ITER,
                ))
            if not step.do:
                errors.append(_issue(
                    "AllStep has no sub-steps",
                    hint="`all:` requires a `do:` array of inner steps "
                         "(at minimum one `- dough:` call)",
                    code=ValidationCode.ALL_STEP_MISSING_DO,
                ))
            # A ``${ref}`` width has no value to range-check yet; the executor's
            # clamp is what bounds it (``iterate.resolve_parallel_cap`` +
            # ``min(cap, MAX_PARALLEL_CEILING)``). Checking a literal here is
            # still worth it — an author who typed 500 finds out now.
            if isinstance(step.max_parallel, int) and not (
                    1 <= step.max_parallel <= MAX_PARALLEL_CEILING):
                errors.append(_issue(
                    f"AllStep max_parallel={step.max_parallel} is out of range "
                    f"(1..{MAX_PARALLEL_CEILING}).",
                    hint=f"`all:` fans out concurrently — set `max_parallel:` "
                         f"between 1 and {MAX_PARALLEL_CEILING} (omit it for the "
                         f"default), so the bake stays bounded.",
                    code=ValidationCode.ALL_STEP_MAX_PARALLEL_RANGE,
                    params={"value": str(step.max_parallel), "max": str(MAX_PARALLEL_CEILING)},
                ))
            # `batch_size` is an `each:` knob — `all:` replaces batching with
            # concurrency and never reads it. Reject rather than silently ignore.
            if step.scale is not None and "batch_size" in step.scale.model_fields_set:
                errors.append(_issue(
                    "AllStep sets `scale.batch_size`, which `all:` ignores.",
                    hint="`all:` runs items concurrently instead of in batches — "
                         "drop `batch_size` and use `max_parallel:` to size the "
                         "fan-out (`scale.soft_cap`/`strategy` still apply).",
                    code=ValidationCode.ALL_STEP_BATCH_SIZE,
                ))

    # --- Ref resolution: refs must resolve to inputs.* or an in-scope name ---
    # In-scope names come from two sources:
    #   1. dough auto-publish: a `dough: <ref>` step makes bare(<ref>) available
    #   2. each-body auto-promote: an `each:` body's last `dough:` id
    #      becomes available as a list in the surrounding scope
    available: set[str] = set()
    # `inputs` and `vault` are ambient roots (deps._AMBIENT_ROOTS): a bare
    # ${inputs} ref is the whole inputs object, always in scope at runtime
    # (resolver.set("inputs", …)). A web write dough uses it to json-dump its
    # inputs into an eval_js snippet — the escaped form that survives a quote/
    # apostrophe in the text. `${vault.<key>}` is redeemed at the sink against the
    # page origin, so it needs no publishing step — it is valid at any depth, not
    # only inside an `each` body.
    available.add("inputs")
    available.add("vault")
    for name in dough.inputs:
        available.add(f"inputs.{name}")

    # Detect duplicate auto-publish names — collision == write-time error.
    publishers: dict[str, int] = {}

    # Pre-pass: every ${ref} ROOT used anywhere — top-level steps, each/all
    # bodies (which `_collect_refs` scopes out, so descend the raw `do` list),
    # and the return block. A duplicate auto-publish whose name is referenced
    # NOWHERE is a pure side-effecting call (a driving flour re-invoked in
    # sequence — e.g. webengine.browser.run_steps) — runtime is last-write-wins
    # and the value is never read, so the collision is harmless, not a typo, and
    # is exempt from the DUP_PUBLISH check below. A REFERENCED duplicate stays an
    # error (the ref would bind ambiguously). Store-independent, so it holds on
    # every call path (save + bake preflight) regardless of the flour's outputs.
    referenced_roots: set[str] = set()
    for _s in parsed_steps:
        for _rp in _collect_refs(_s):
            referenced_roots.add(_rp.split(".")[0])
        _do = getattr(_s, "do", None)
        if isinstance(_do, list):
            for _raw in _do:
                for _rp in _extract_refs_from_value(_raw):
                    referenced_roots.add(_rp.split(".")[0])
    for _expr in dough.return_.values():
        for _rp in _extract_refs(_expr):
            referenced_roots.add(_rp.split(".")[0])

    for idx, step in enumerate(parsed_steps):
        refs = _collect_refs(step)
        for ref_path in refs:
            root = ref_path.split(".")[0]
            if ref_path.startswith("inputs."):
                input_name = ref_path.split(".")[1] if "." in ref_path else ""
                if input_name and input_name not in dough.inputs:
                    errors.append(_issue(
                        f"Step {idx} references '${{inputs.{input_name}}}' "
                        f"but no input '{input_name}' is defined",
                        hint=f"declare '{input_name}' under top-level `inputs:` "
                             f"with a `type:`, or fix the ref to a real input "
                             f"name (have: {sorted(dough.inputs) or 'none'}) ",
                        code=ValidationCode.INPUT_REF_UNDECLARED,
                        params={
                            "step": str(idx), "name": input_name,
                            "defined_inputs": ", ".join(sorted(dough.inputs)) or "none",
                        },
                    ))
                continue
            if root not in available:
                errors.append(_issue(
                    f"Step {idx} references '${{{ref_path}}}' "
                    f"but no prior step publishes '{root}'",
                    hint=f"no upstream step publishes '{root}'. Inspect "
                         f"candidates: peel spec <flour_id_of_a_prior_step> — "
                         f"or insert a prep flour that produces '{root}' ",
                    code=ValidationCode.REF_NO_PUBLISHER,
                    params={"step": str(idx), "ref": ref_path, "root": root},
                ))
                continue
            # Drill-down check: ${root.p1[.p2]} — verify the drill resolves
            # against the publisher dough's declared outputs. Catches the
            # `${classifier.items}` bug (drilling a field that is not an
            # output handle) and the `${X.X}` double-nesting confusion.
            # `drill.issue` mirrors the baker's two publish shapes.
            if root in publishers and store is not None:
                pub_step = parsed_steps[publishers[root]]
                target_id = pub_step.dough if isinstance(pub_step, DoughStep) else None
                target = store.get_dough(target_id) if target_id else None
                di = drill.issue(ref_path, target) if target else None
                if di:
                    errors.append(_issue(
                        f"Step {idx} references '${{{ref_path}}}' but "
                        f"'{di['field']}' is not a field of `{di['owner']}` "
                        f"on '{target_id}'.",
                        hint=f"valid fields on `{di['owner']}`: {di['valid']}. ",
                        code=ValidationCode.REF_DRILL_FIELD_NOT_FOUND,
                        params={
                            "step": str(idx), "ref": ref_path,
                            "root": root, "field": di["field"],
                            "owner": di["owner"], "valid_fields": di["valid"],
                        },
                    ))

        published_name: str | None = None
        if isinstance(step, DoughStep) and step.dough:
            # ``publish_as`` first — the SAME precedence the runtime uses
            # (``execution/scope.py``: ``publish_as or bare_dough_path``). Without
            # it this pass disagrees with the engine about what a step is
            # called, and every top-level use of ``publish_as`` draws two false
            # errors at once: a ``dup_publish`` against the sibling that shares
            # its dough id, and a ``return_ref_no_publisher`` for the name it
            # actually publishes under. ``each:``/``all:`` bodies keep resolving
            # by bare id (``last_dough_id_in_steps``) — that is the documented
            # behavior a body's own refs are written against, not an oversight.
            published_name = step.publish_as or bare_dough_path(step.dough)
        elif isinstance(step, (EachStep, AllStep)):
            published_name = last_dough_id_in_steps(step.do)

        if published_name:
            if published_name in publishers:
                # Two exemptions, OR'd:
                #  1. Infra kits (advanced.*) ship long compositions that
                #     legitimately re-call the same helper (basic.condition,
                #     write_fragment per bucket) in sequence — last-write-wins,
                #     each publish consumed before the next overwrites.
                #  2. The published name is referenced NOWHERE (see the
                #     referenced_roots pre-pass) — a pure side-effecting call
                #     (a driving flour like run_steps re-invoked in sequence);
                #     nobody reads it, so the collision is harmless.
                # Otherwise keep the strict check — for user-authored doughs a
                # referenced collision is almost always a typo.
                exempt = (
                    dough.path.startswith("advanced.")
                    or published_name not in referenced_roots
                )
                if not exempt:
                    errors.append(_issue(
                        f"Step {idx} publishes '{published_name}' but step "
                        f"{publishers[published_name]} already published it — "
                        f"two steps cannot publish the same name in one scope.",
                        hint="wrap one step in a sub-dough, or write an adapter "
                             "flour that renames the output (a 'prep_*' flour) ",
                        code=ValidationCode.DUP_PUBLISH,
                        params={
                            "name": published_name,
                            "prior_step": str(publishers[published_name]),
                            "curr_step": str(idx),
                        },
                    ))
                # Treat the latest publish as the active one regardless,
                # so downstream refs resolve.
                publishers[published_name] = idx
                available.add(published_name)
            else:
                publishers[published_name] = idx
                available.add(published_name)

    # --- Validate return: block refs ---
    for key, ref_expr in dough.return_.items():
        refs = _extract_refs(ref_expr)
        for ref_path in refs:
            root = ref_path.split(".")[0]
            if ref_path.startswith("inputs."):
                continue
            if root not in available:
                errors.append(_issue(
                    f"return.{key} references '${{{ref_path}}}' "
                    f"but no step publishes '{root}'",
                    hint=f"either add a step that publishes '{root}', or "
                         f"point `return.{key}` at a name that is in scope "
                         f"(in scope: {sorted(available) or 'none'}) ",
                    code=ValidationCode.RETURN_REF_NO_PUBLISHER,
                    params={
                        "key": key, "ref": ref_path, "root": root,
                        "in_scope": ", ".join(sorted(available)) or "none",
                    },
                ))
                continue

            if store is None or root not in publishers:
                continue
            pub_step = parsed_steps[publishers[root]]
            target_id = pub_step.dough if isinstance(pub_step, DoughStep) else None
            target = store.get_dough(target_id) if target_id else None
            if target is None:
                continue

            # Same drill check as steps — catches `return: x: ${X.badfield}`.
            di = drill.issue(ref_path, target)
            if di:
                errors.append(_issue(
                    f"return.{key} references '${{{ref_path}}}' but "
                    f"'{di['field']}' is not a field of `{di['owner']}` "
                    f"on '{target_id}'.",
                    hint=f"valid fields on `{di['owner']}`: {di['valid']}. ",
                    code=ValidationCode.REF_DRILL_FIELD_NOT_FOUND,
                    params={
                        "key": key, "ref": ref_path, "root": root,
                        "field": di["field"], "owner": di["owner"],
                        "valid_fields": di["valid"],
                    },
                ))
                continue

            # Shape-mismatch check: a bare envelope ref `${X}` assigned to a
            # declared object output whose field set is DISJOINT from what `X`
            # actually produces — the `return: classification: ${classifier}`
            # double-wrap, where the classifier publishes `{classification:…}`
            # but the output expects `{total, items, …}`. Only flag on a clean
            # bare ref with a known, disjoint shape (conservative — never on a
            # partial overlap or an unknowable shape).
            if ref_path != root:
                continue
            out_def = dough.outputs.get(key)
            if out_def is None or out_def.type != "object":
                continue
            declared = drill.output_fields(out_def)
            if not declared:
                continue
            produced, drill_hint = drill.published_shape(target, root)
            if produced and declared.isdisjoint(produced):
                errors.append(_issue(
                    f"return.{key} assigns the whole `{root}` envelope "
                    f"(fields: {', '.join(sorted(produced))}) to output "
                    f"'{key}' which expects {', '.join(sorted(declared))}.",
                    hint=(f"drill to the matching field — e.g. "
                          f"`${{{root}.{drill_hint}}}`. " if drill_hint
                          else f"point `return.{key}` at the field that holds "
                               f"{', '.join(sorted(declared))}. "),
                    code=ValidationCode.REF_SHAPE_MISMATCH,
                    params={
                        "key": key, "root": root,
                        "produced": ", ".join(sorted(produced)),
                        "declared": ", ".join(sorted(declared)),
                        "suggest": f"{root}.{drill_hint}" if drill_hint else "",
                    },
                ))

    errors.extend(checks.step_with_keys(dough, store))
    errors.extend(checks.items_table(dough, parsed_steps, publishers))
    errors.extend(checks.parallel_shared_tab(dough, parsed_steps, publishers))
    errors.extend(checks.literal_aria_ref(dough))
    errors.extend(checks.run_steps_guarded(dough))
    errors.extend(checks.web_query_is_applied(dough))
    errors.extend(checks.login_contract(dough))

    if store is not None:
        for ref in dict.fromkeys(_iter_dough_refs(dough)):
            if not ref:
                continue
            if not store.dough_exists(ref):
                errors.append(_issue(
                    f"Step references dough '{ref}' but no such dough "
                    f"exists in the kit registry or user library.",
                    hint=f"discover real flour ids by capability: "
                         f"peel flours --object <o> --namespace <ns>. "
                         f"Never fabricate ids — copy them from listings. ",
                    code=ValidationCode.DOUGH_REF_NOT_FOUND,
                    params={"ref": ref},
                ))

    return errors


def _spread_issues(dough: Dough) -> list[ValidationIssue]:
    """Gate a dough's frozen view's LAYOUT half (``dough.spread``) against the
    surface-agnostic block catalog.

    The block catalog + gate live in the neutral spread kernel
    ``app.spreads`` (which imports nothing from ``app.doughs`` or ``app.memo``),
    so ``app.doughs`` -> ``app.spreads`` is an ordinary downward edge — a normal
    top-level import, no cycle. The old module-load cycle that forced a lazy
    import here is GONE: the gate no longer lives behind ``app.memo``, so the
    reverse ``app.doughs`` -> ``app.memo`` edge no longer exists. Reuses
    ``composition_spec`` as the single block-catalog source of truth rather than
    duplicating it into ``app.doughs``.

    The gate is ``composition_spec`` ONLY (the surface-agnostic block check) —
    never the surface-bound ``validate.validate``, which rejects a
    ``<handle>.<name>`` composition and needs a registry surface a donut lacks.

    We also thread the dough's donut-output shape into the gate so a block role
    that reads a FIELD PATH which does NOT resolve against ``donut.output`` (the
    "empty card" class — a bare ``answer`` role when the output is keyed
    ``{result: …}``) fails here instead of painting blank live. The output's
    top-level keys ARE the return-block keys; each object output's field set
    (for a dotted tail) comes from its ``model:`` / inline ``schema:`` via
    ``drill.output_fields``.
    """
    return_keys = frozenset(dough.return_) if dough.return_ else frozenset()
    output_fields = {
        key: drill.output_fields(out_def)
        for key, out_def in dough.outputs.items()
        if out_def.type == "object"
    }

    errors: list[ValidationIssue] = []
    for msg in composition_spec(
        dough.spread or {}, dough.path,
        return_keys=return_keys, output_fields=output_fields,
    ):
        errors.append(_issue(
            msg,
            hint="the `spread:` render spec must be a "
                 "`{tier: composition, blocks: [{block, roles, knobs}]}` over "
                 "the spread block catalog — fix the flagged block/role/knob",
            code=ValidationCode.INVALID_SPREAD,
            params={"dough": dough.path, "detail": msg},
        ))
    return errors


def _view_ref_issues(dough: Dough, store: "DoughStore") -> list[ValidationIssue]:
    """The reference-shape check for ``default_spread:`` — ONE nominal question at
    save time: does the pointed-at view exist, and does its declared anchor
    match this dough's output shape? (``for.keys`` ⊆ return keys; a ``for.model``
    must be one this dough's outputs declare, when both sides declare one.)

    The render-time structural gate stays as the belt; this catches the pointer
    that never matched BEFORE the first blank card."""
    from app.doughs.definitions.spread import spreads_root_for
    from app.spreads.artifact import store as spread_store

    def _refuse(msg: str, hint: str) -> list[ValidationIssue]:
        return [_issue(msg, hint=hint, code=ValidationCode.SPREAD_REF_INVALID,
                       params={"dough": dough.path, "view": dough.default_spread})]

    doc = spread_store.read_doc(spreads_root_for(store._doughs_dir), dough.default_spread)
    if doc is None:
        return _refuse(
            f"default_spread '{dough.default_spread}' does not exist in the spread tree",
            hint="mint the spread first (mint_spread / app.spreads.artifact.store.save_spread) or "
                 "drop the pointer",
        )
    anchor = doc.get("for") or {}
    keys = anchor.get("keys") or []
    if keys:
        missing = sorted(set(keys) - set(dough.return_ or {}))
        if missing:
            return _refuse(
                f"default_spread '{dough.default_spread}' anchors keys {missing} this "
                f"dough's return: does not produce",
            hint="the view's `for.keys` must all be return keys of this dough — "
                 "pick a matching view or fix the return block",
            )
    model = anchor.get("model") or ""
    if model:
        declared = {o.model for o in dough.outputs.values() if getattr(o, "model", None)}
        if declared and model not in declared:
            return _refuse(
                f"default_spread '{dough.default_spread}' anchors model '{model}' but "
                f"this dough's outputs declare {sorted(declared)}",
                hint="the view's `for.model` must match an output's `model:` — "
                     "pick a matching view or fix the output model",
            )
    return []


def _act_target_inputs(
    dough: Dough, store: "DoughStore | None"
) -> dict[str, TargetInputs] | None:
    """Resolve each press-gesture (``act``/``nav``) target's declared-input facts
    for ``_gate_target_inputs``.

    Two checks ride these facts, and they are NOT the same severity — worth keeping
    straight, because only one of them fixes a silence:

    * **an UNDECLARED key is silent.** ``execution.binding.resolve_inputs`` iterates
      the CALLEE's declared inputs and nothing else, so a key the target does not
      declare is dropped on the floor: the bake succeeds with a default while the
      author believes the row's datum was passed. Identical to the step ``with:``
      failure ``checks.step_with_keys`` refuses — same resolver, same drop, other
      caller.
    * **an UNBOUND required input is already loud.** The same function raises
      ``BakeError(INPUT_REQUIRED)``. Gating it here only moves a certain runtime
      failure to save time, which is still worth doing — a spark author otherwise
      meets it on the first press, per row — but it repairs no silence.

    ``required`` mirrors ``InputDef``'s own semantics (``value`` set → pinned,
    ``default`` set → satisfied), so the "pass only what differs" idiom is not
    false-rejected. Absence really is absence: ``runEffectAct`` POSTs the spark's
    ``inputs`` map and nothing else, so no other channel can supply the key.

    **The false-positive sweep that landed ``step_with_keys`` is NOT available
    here, and saying "0 on 680 doughs" would be a vacuous claim.** Measured on the
    real profile: 680 doughs, ONE carries a spark, and it declares zero ``act``
    interactions — so the scan population is empty and a clean sweep would prove
    only that nothing was examined. The safety argument is provability instead:
    neither direction depends on runtime data (no data shape makes an undeclared
    key arrive; no channel but this map feeds a required input), which is the same
    ground the undeclared-key half of ``step_with_keys`` stood on before its
    population happened to also be measurable.
    """
    if store is None:
        return None
    facts: dict[str, TargetInputs] = {}
    for target in _press_targets(dough):
        callee = store.get_dough(target)
        if callee is None:
            continue  # unresolvable — _spark_issues reports it; no facts to build
        facts[target] = TargetInputs(
            all=frozenset(callee.inputs),
            required=frozenset(
                name
                for name, inp in callee.inputs.items()
                if inp.required and inp.default is None and inp.value is None
            ),
        )
    return facts or None


def _press_targets(dough: "Dough"):
    """Every dough id a press-gesture effect in this spread names, once each — an
    `act` (`act:`) or a `nav` (`nav:`), both of which bake a TARGET dough.

    The trigger maps ride on the blocks, so this walks the containment TREE — a
    map on a block inside a `section` is as real as one at the top level, and a
    top-level-only scan would silently skip it. That is the same lesson the
    composition gate learned when it started walking.
    """
    from app.spreads.spark import anchor as _anchor

    seen: set[str] = set()
    for hit in _anchor.walk_blocks((dough.spread or {}).get("blocks") or []):
        on = hit.block.get("on")
        if not isinstance(on, dict):
            continue
        for trigger in ("press", "contextmenu"):
            eff = on.get(trigger)
            if not isinstance(eff, dict):
                continue
            target = eff.get("act") or eff.get("nav")
            if isinstance(target, str) and target and target not in seen:
                seen.add(target)
                yield target


def _spark_issues(
    dough: Dough, store: "DoughStore | None" = None
) -> list[ValidationIssue]:
    """Gate a dough's frozen view's INTERACTIONS half (``dough.spread``) against the
    surface-agnostic spark interaction catalog.

    Mirrors ``_spread_issues``: the gate + catalog live in the neutral
    ``app.spreads.spark`` kernel (imports nothing from ``app.doughs``/``app.memo``), so
    ``app.doughs`` -> ``app.spreads.spark`` is an ordinary top-level downward edge.

    A spark anchors into the dough's OWN ``spread`` blocks, threaded in here (the
    identical seam ``_spread_issues`` uses for return_keys/output_fields).

    ``target_inputs`` is threaded too, when a ``store`` is passed — the cross-dough
    "an ``act``'s ``inputs`` are the target's real declared inputs" facts. This was
    deferred, and the deferral had a cost: ``_gate_act_inputs`` was WRITTEN and
    unreachable, ``TargetInputs`` had zero construction sites, so the gate read as
    live in both this docstring and ``app/sparks/CLAUDE.md`` while checking nothing
    beyond each value's ``$.<field>`` shape. A gate nobody feeds is the same silence
    it exists to refuse.

    Only ``act`` and ``nav`` interactions name a target (a ``read`` re-calls this
    dough's own source, an ``open`` hands off the row's URL), so only those are
    resolved. An unresolvable target is reported HERE (``DOUGH_REF_NOT_FOUND``) —
    the step-ref pass walks only ``dough.steps`` and never sees interactions — and
    contributes no facts, so the membership half self-skips instead of stacking a
    second issue on it.
    """
    if not (dough.spread or {}).get("blocks"):
        return [_issue(
            "interactions make a layout interactive, but this view has no layout",
            hint="give the view a `layout:` for its `interactions:` to anchor "
                 "into, or drop the `interactions:` from spread/spread.yaml",
            code=ValidationCode.INVALID_SPARK,
            params={"dough": dough.path},
        )]
    spread_blocks = (dough.spread or {}).get("blocks") or []

    errors: list[ValidationIssue] = []
    # An act's TARGET must exist — checked HERE, because nothing else looks:
    # `_iter_dough_refs` walks only `dough.steps`, so the step-ref
    # DOUGH_REF_NOT_FOUND pass never sees `view.interactions`, and
    # `_act_target_inputs` builds no facts for an unresolvable id (its membership
    # gate then self-skips). Without this pass a typo'd target cleared every
    # authoring seam and 404'd on every user press.
    if store is not None:
        for target in _press_targets(dough):
            if store.get_dough(target) is None:
                errors.append(_issue(
                    f"spark press targets dough '{target}' but no such dough "
                    f"exists in the kit registry or user library.",
                    hint="discover real flour ids by capability: "
                         "peel flours --verb <v> --object <o>. "
                         "Never fabricate ids — copy them from listings.",
                    code=ValidationCode.DOUGH_REF_NOT_FOUND,
                    params={"ref": target, "dough": dough.path},
                ))
    # `source_consequence` = the OWNING dough's declared tier — a `read` re-calls
    # THIS dough (its own source), so that tier gates the read side-effect-free
    # check (CQRS).
    # The frozen spread IS the spark_spec input: the trigger maps ride on its
    # blocks, so there is no second document to thread and no way for the two to
    # disagree about which layout the controller belongs to.
    for msg in spark_spec(
        dough.spread or {},
        dough.path,
        target_inputs=_act_target_inputs(dough, store),
        source_consequence=dough.consequence,
    ):
        errors.append(_issue(
            msg,
            hint="a block's `on:` map is trigger -> effect — "
                 "`{press: {act|open, ...}, contextmenu: {...}, refresh: {read}}`. "
                 "Fix the flagged trigger's effect or its fields",
            code=ValidationCode.INVALID_SPARK,
            params={"dough": dough.path, "detail": msg},
        ))
    return errors


def _validate_for_load(
    dough: Dough,
    *,
    all_doughs: dict[str, Dough] | None = None,
) -> list[ValidationIssue]:
    """Boot-time semantic rules + step shape.

      5/6. step-shape (R5/R6) — applies at load too. Boot-time validation
           previously skipped these, which let kit YAML drift past load
           without anyone noticing.
      9.  a fixed dough must not reference a missing custom dough

    ``all_doughs`` is a mapping of canonical id → Dough for cross-ref
    rule 9. Pass None to skip it.
    """
    errors: list[ValidationIssue] = []
    dough_path = dough.path

    errors.extend(checks.step_shapes(dough.steps))
    # The login contract is a boot-time rule too: a login dough missing a rung
    # must fail at kit-load, the way an invalid verb does — not only on save.
    errors.extend(checks.login_contract(dough))

    # Cross-ref rules need the full index.
    if all_doughs is None:
        return errors

    refs = _iter_dough_refs(dough)

    # --- Rule 9: fixed may not reference a missing custom target ---
    if is_fixed(dough_path):
        for ref in refs:
            if not ref.startswith(custom_prefix()):
                continue
            if all_doughs.get(ref) is None:
                errors.append(_issue(
                    f"fixed dough '{dough_path}' references missing custom dough "
                    f"'{ref}'",
                    hint="list user doughs: peel doughs",
                    code=ValidationCode.FIXED_REFS_MISSING_USER,
                    params={"dough": dough_path, "ref": ref},
                ))

    return errors


def _iter_dough_refs(dough: Dough) -> list[str]:
    """Collect every `dough:` reference used as a nested step, including
    refs nested inside each.do blocks.
    """
    refs: list[str] = []

    def _walk(step_list: list[dict[str, Any]]) -> None:
        for raw in step_list:
            if not isinstance(raw, dict):
                continue
            route = raw.get("route")
            if isinstance(route, dict) and route:
                # Routed step: `dough` is a `${handle}` placeholder resolved at
                # bake time, not an id. The real callees are the route targets —
                # existence-check those.
                refs.extend(t for t in route.values() if isinstance(t, str))
            elif isinstance(raw.get("dough"), str):
                refs.append(raw["dough"])
            # `each` steps carry nested sub-steps under `do`.
            sub = raw.get("do")
            if isinstance(sub, list):
                _walk(sub)

    _walk(dough.steps)
    return refs


def _collect_refs(step: Any) -> list[str]:
    """Collect all ${ref} paths from a step."""
    refs: list[str] = []
    if isinstance(step, DoughStep):
        for val in step.with_.values():
            refs.extend(_extract_refs_from_value(val))
    elif isinstance(step, EachStep):
        refs.extend(_extract_refs(step.each))
        # Sub-steps refs are scoped (include as_ item) — skip deep validation
    elif isinstance(step, AllStep):
        refs.extend(_extract_refs(step.all_))
        # Sub-steps refs are scoped (include as_ item) — skip deep validation
    return refs


def _extract_refs(text: str) -> list[str]:
    """Extract ${ref.path} references from a string."""
    return REF_PATTERN.findall(text)


def _extract_refs_from_value(val: Any) -> list[str]:
    """Extract refs from a param value (could be string, dict, list)."""
    if isinstance(val, str):
        return _extract_refs(val)
    if isinstance(val, dict):
        refs = []
        for v in val.values():
            refs.extend(_extract_refs_from_value(v))
        return refs
    if isinstance(val, list):
        refs = []
        for v in val:
            refs.extend(_extract_refs_from_value(v))
        return refs
    return []
