"""Dough definition validation — v2 schema with ${ref} strings.

Two entry points:

- :func:`validate` — validate a parsed :class:`Dough`. ``scope="save"``
  (default) runs pre-write checks; ``scope="load"`` runs boot-time
  checks (cross-ref protection between fixed and custom doughs).
- :func:`validate_yaml` — accept a raw YAML dict, parse to ``Dough``,
  run pre-write checks. Surfaces both ``FORBIDDEN_PRE_PARSE_KEYS``
  rejections (shape-inferred fields) and standard validation issues.

:func:`validate_dough_id` lives in ``id_utils.py`` — it validates an id
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
from app.doughs.definitions.ids import bare_dough_id, last_dough_id_in_steps
from app.doughs.execution.resolver import REF_PATTERN
from app.doughs.models import (
    MAX_PARALLEL_CEILING,
    Dough,
    AllStep, DoughStep, EachStep,
    parse_step,
)
from app.doughs.validation.rules import (
    CLASS_USER_PREFIX,
    FORBIDDEN_PRE_PARSE_KEYS,
    FORBIDDEN_STEP_KEYS,
    is_fixed,
    is_kit_dough,
    is_web_dough,
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
    STEP_INLINE_PRIMITIVE_FORBIDDEN = "step_inline_primitive_forbidden"
    STEP_MULTIPLE_KEYS = "step_multiple_keys"
    STEP_UNKNOWN_SHAPE = "step_unknown_shape"
    STEP_FIELD_SAVE_REMOVED = "step_field_save_removed"
    STEP_FIELD_WHEN_REMOVED = "step_field_when_removed"
    STEP_FIELD_ON_ERROR_REMOVED = "step_field_on_error_removed"
    USER_FLOUR_TOOL_FORBIDDEN = "user_flour_tool_forbidden"
    USER_FLOUR_WEB_FORBIDDEN = "user_flour_web_forbidden"
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
    BOX_INPUT_LABEL_MISSING = "box_input_label_missing"
    BOX_OUTPUT_LABEL_MISSING = "box_output_label_missing"
    BOX_INPUT_DESCRIPTION_MISSING = "box_input_description_missing"
    BOX_OUTPUT_DESCRIPTION_MISSING = "box_output_description_missing"


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
) -> list[ValidationIssue]:
    """Parse a raw YAML dict as a :class:`Dough` and run :func:`validate`.

    Returns ``[]`` when the dict isn't a parseable Dough at all — load-time
    schema errors surface on the next disk write through Pydantic, and
    double-reporting them here just duplicates the noise.

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
                    f"`{key}:` is not a YAML field — it is shape-inferred.",
                    hint=f"delete the `{key}:` line. {hint}",
                    code=ValidationCode.FORBIDDEN_PRE_PARSE_KEY,
                    params={"key": key},
                ))

    try:
        dough = Dough.model_validate(dough_dict)
    except PydanticValidationError:
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
            hint="use `action:` for a flour (single tool/agent/web step) or "
                 "`steps:` for a dough (composition)",
            code=ValidationCode.DOUGH_HAS_BOTH,
        ))
        return errors

    if has_action:
        errors.extend(checks.action(dough))
        if is_kit_dough(dough.id):
            errors.extend(checks.kit_outputs(dough))

    errors.extend(checks.display_types(dough))

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
                         "discover candidates: peel flours --verb <v> ",
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
            if not (1 <= step.max_parallel <= MAX_PARALLEL_CEILING):
                errors.append(_issue(
                    f"AllStep max_parallel={step.max_parallel} is out of range "
                    f"(1..{MAX_PARALLEL_CEILING}).",
                    hint=f"`all:` fans out concurrently — set `max_parallel:` "
                         f"between 1 and {MAX_PARALLEL_CEILING} (omit it for the "
                         f"default), so the bake stays bounded.",
                    code=ValidationCode.ALL_STEP_MAX_PARALLEL_RANGE,
                    params={"value": str(step.max_parallel), "max": str(MAX_PARALLEL_CEILING)},
                ))

    # --- Ref resolution: refs must resolve to inputs.* or an in-scope name ---
    # In-scope names come from two sources:
    #   1. dough auto-publish: a `dough: <ref>` step makes bare(<ref>) available
    #   2. each-body auto-promote: an `each:` body's last `dough:` id
    #      becomes available as a list in the surrounding scope
    available: set[str] = set()
    for name in dough.inputs:
        available.add(f"inputs.{name}")

    # Detect duplicate auto-publish names — collision == write-time error.
    publishers: dict[str, int] = {}

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
            published_name = bare_dough_id(step.dough)
        elif isinstance(step, (EachStep, AllStep)):
            published_name = last_dough_id_in_steps(step.do)

        if published_name:
            if published_name in publishers:
                # Infra kits (advanced.*) ship long compositions that
                # legitimately re-call the same helper (basic.condition,
                # write_fragment per bucket) in sequence — runtime is
                # last-write-wins and each publish is consumed before
                # the next overwrites. Skip the strict collision check
                # for those; keep it for user-authored doughs where the
                # collision is almost always a typo.
                if not dough.id.startswith("advanced."):
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

    errors.extend(checks.items_table(dough, parsed_steps, publishers))

    if store is not None:
        for ref in dict.fromkeys(_iter_dough_refs(dough)):
            if not ref:
                continue
            if not store.dough_exists(ref):
                errors.append(_issue(
                    f"Step references dough '{ref}' but no such dough "
                    f"exists in the kit registry or user library.",
                    hint=f"discover real flour ids by capability: "
                         f"peel flours --verb <v> --object <o>. "
                         f"Never fabricate ids — copy them from listings. ",
                    code=ValidationCode.DOUGH_REF_NOT_FOUND,
                    params={"ref": ref},
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
    dough_id = dough.id

    # Web doughs (web.<site>.<action>) carry `web:` steps plus the
    # web-step-local `save:`/`when:`/`on_error:` fields — all LEGAL at
    # their tier, all FORBIDDEN at composition level (see web_dough.py).
    # They are validated by their own strict schema (WebDough/WebStep)
    # at model_validate time; the composition rules below do not apply.
    # Without this skip every `web:` step trips R5 at load.
    if is_web_dough(dough_id):
        return errors

    errors.extend(checks.step_shapes(dough.steps))

    # Cross-ref rules need the full index.
    if all_doughs is None:
        return errors

    refs = _iter_dough_refs(dough)

    # --- Rule 9: fixed may not reference a missing custom target ---
    if is_fixed(dough_id):
        for ref in refs:
            if not ref.startswith(CLASS_USER_PREFIX):
                continue
            if all_doughs.get(ref) is None:
                errors.append(_issue(
                    f"fixed dough '{dough_id}' references missing custom dough "
                    f"'{ref}'",
                    hint="list user doughs: peel doughs",
                    code=ValidationCode.FIXED_REFS_MISSING_USER,
                    params={"dough": dough_id, "ref": ref},
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
            if isinstance(raw.get("dough"), str):
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
