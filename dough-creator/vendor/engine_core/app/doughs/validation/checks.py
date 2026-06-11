"""Independent dough-validation checks — split out of ``engine.py``.

Call them module-qualified — ``checks.action``, ``checks.step_shapes``,
``checks.box_completeness`` — the ``checks`` namespace already says
"validation rule", so the function names don't repeat ``validate_``.

Each function here is a pure ``Dough → list[ValidationIssue]`` check with no
state and no entanglement with the save/load ref-resolution engine; they were
lifted out purely for file size. The orchestrating engine in ``engine.py``
calls them (``_validate_for_save`` / ``validate`` / ``validate_yaml``).

The issue vocabulary (``_issue``, ``ValidationCode``) and the ``${ref}``
extractor live in ``engine.py`` and are reached here as ``_v.<name>`` —
the same intentional sibling-reach as ``loading``/``donut_store`` into
``store`` (one logical unit split for size, not a new boundary). A plain
``import app.doughs.validation.engine as _v`` (module object, not ``from`` import)
breaks the cycle: ``engine.py`` imports ``checks`` at its top, and the
module-object binding defers every ``_v.<name>`` access to call time, by which
point ``validation`` is fully initialized.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import app.doughs.validation.engine as _v
from app.doughs.models import DISPLAY_REQUIRED_TYPES, AllStep, Dough, EachStep
from app.doughs.validation.rules import (
    ALLOWED_STEP_KEYS,
    FORBIDDEN_FIELDS,
    FORBIDDEN_STEP_KEYS,
    MODEL_REQUIRED_TYPES,
    is_custom,
)

if TYPE_CHECKING:
    from app.doughs.models import Box
    from app.doughs.validation.engine import ValidationIssue


def step_shapes(steps: list[Any]) -> list["ValidationIssue"]:
    """Forbid inline action keys + deprecated step fields. Recurses into each.do."""
    errors: list[ValidationIssue] = []

    def _walk(step_list: list[Any], path: str = "steps") -> None:
        for i, raw in enumerate(step_list):
            if not isinstance(raw, dict):
                continue
            here = f"{path}[{i}]"

            inline = sorted(FORBIDDEN_STEP_KEYS & raw.keys())
            if inline:
                key = inline[0]
                if key == "agent":
                    hint = (
                        "lift this agent: call into its own flour at "
                        "user/<slug>/dough.yaml (a flour has `action:`, no "
                        "`steps:`), then call it from this composition via "
                        "`- dough: user.<slug>`. User-authored flours may "
                        "only use `action: agent:`."
                    )
                else:
                    hint = (
                        f"`{key}:` inside a step is forbidden. To reach an "
                        f"external system, compose a shipped flour: "
                        f"`peel flours --verb <v>`. Users cannot author "
                        f"`tool:` or `web:` flours."
                    )
                errors.append(_v._issue(
                    f"{here}: inline `{key}:` is forbidden at composition level.",
                    hint=hint,
                    code=_v.ValidationCode.STEP_INLINE_PRIMITIVE_FORBIDDEN,
                    params={"step": here, "key": key},
                ))
            elif len(present := (ALLOWED_STEP_KEYS & raw.keys())) > 1:
                # `dough:`/`each:`/`all:` are mutually exclusive shapes. With
                # `extra="allow"`, a step carrying two of them would silently
                # parse as whichever wins STEP_KEY_MAP order (e.g. `each` over
                # `all`), running the wrong execution policy with no error.
                shapes = ", ".join(f"`{k}:`" for k in sorted(present))
                errors.append(_v._issue(
                    f"{here}: a step declares multiple shapes ({shapes}) — "
                    f"`dough:`, `each:`, and `all:` are mutually exclusive.",
                    hint="split into separate steps, or keep only the one shape "
                         "this step needs.",
                    code=_v.ValidationCode.STEP_MULTIPLE_KEYS,
                    params={"step": here, "keys": shapes},
                ))
            elif not present:
                keys = ", ".join(f"`{k}:`" for k in sorted(raw.keys())) or "<empty>"
                errors.append(_v._issue(
                    f"{here}: unknown step shape (keys: {keys}) — "
                    f"composition steps must contain `dough:`, `each:`, or `all:`.",
                    hint=(
                        "no `if:` / `when:` / `switch:` step exists. For "
                        "conditional logic compose `basic.condition`, "
                        "`basic.gate_if_any`, or `basic.filter`."
                    ),
                    code=_v.ValidationCode.STEP_UNKNOWN_SHAPE,
                    params={"step": here, "keys": keys},
                ))

            for field in sorted(FORBIDDEN_FIELDS & raw.keys()):
                if field == "save":
                    errors.append(_v._issue(
                        f"{here}: field `save:` is removed.",
                        hint="outputs auto-publish from the called dough's "
                             "`outputs:` declaration — delete the `save:` key ",
                        code=_v.ValidationCode.STEP_FIELD_SAVE_REMOVED,
                        params={"step": here},
                    ))
                elif field == "when":
                    errors.append(_v._issue(
                        f"{here}: field `when:` is removed.",
                        hint="push gating into a flour: write a tiny filter/gate "
                             "flour that returns the value or null, and call it "
                             "linearly",
                        code=_v.ValidationCode.STEP_FIELD_WHEN_REMOVED,
                        params={"step": here},
                    ))
                elif field == "on_error":
                    errors.append(_v._issue(
                        f"{here}: field `on_error:` is removed.",
                        hint="for best-effort steps use `optional: true`; "
                             "anything richer belongs inside a flour",
                        code=_v.ValidationCode.STEP_FIELD_ON_ERROR_REMOVED,
                        params={"step": here},
                    ))

            sub = raw.get("do")
            if isinstance(sub, list):
                _walk(sub, path=f"{here}.do")

    _walk(steps)
    return errors


# Vendor-namespaced kits return concrete domain types (GmailMessage,
# OutlookEvent, etc.) so R11 enforces a Pydantic ref on object/list
# outputs. The two infra kits are exempt:
#   - basic.*       — parametric dataflow primitives (filter/map/slice)
#                     genuinely return "whatever you put in"; there's
#                     no fixed model.
#   - advanced.*    — internal infra-kit plumbing whose intermediate
#                     outputs are private to the composition, not part
#                     of a vendor-facing typed surface.
_R11_EXEMPT_PREFIXES: tuple[str, ...] = ("basic.", "advanced.")


def display_types(dough: Dough) -> list["ValidationIssue"]:
    """``display:`` on an output must be compatible with its ``type:``.
    Picking a renderer that doesn't match the value-shape ships a broken UI.
    """
    errors: list[ValidationIssue] = []
    for name, out in dough.outputs.items():
        if out.display is None:
            continue
        allowed = DISPLAY_REQUIRED_TYPES.get(out.display)
        if allowed is None or out.type in allowed:
            continue
        errors.append(_v._issue(
            f"output '{name}' declares display '{out.display}' but type is "
            f"'{out.type}'.",
            hint=(
                f"`display: {out.display}` requires `type:` to be one of "
                f"{', '.join(allowed)}. Either change the type, or pick a "
                f"display that fits the value: `markdown` for strings, "
                f"`data_table` for lists, `raw` accepts anything."
            ),
            code=_v.ValidationCode.OUTPUT_DISPLAY_TYPE_MISMATCH,
            params={
                "name": name,
                "display": out.display,
                "type": out.type,
                "allowed": ", ".join(allowed),
            },
        ))
    return errors


def items_table(
    dough: Dough,
    parsed_steps: list[Any],
    publishers: dict[str, int],
) -> list["ValidationIssue"]:
    """``display: items_table`` requires the output to be sourced from an
    ``each:`` or ``all:`` step — the audit shape needs per-iteration metadata
    that only an iteration step (``each:``/``all:``) records.
    """
    errors: list[ValidationIssue] = []
    for key, ref_expr in dough.return_.items():
        out_def = dough.outputs.get(key)
        if out_def is None or out_def.display != "items_table":
            continue
        refs = _v._extract_refs(ref_expr)
        if not refs:
            continue
        root = refs[0].split(".")[0]
        pub_idx = publishers.get(root)
        pub_step = parsed_steps[pub_idx] if pub_idx is not None else None
        if isinstance(pub_step, (EachStep, AllStep)):
            continue
        errors.append(_v._issue(
            f"output '{key}' declares `display: items_table` but its "
            f"return ref '${{{refs[0]}}}' does not come from an `each:` "
            f"or `all:` step.",
            hint=(
                "`display: items_table` shows per-iteration status "
                "rows, which only an `each:` / `all:` step produces. Either "
                "compose an `each:`/`all:` that publishes this list, or "
                "switch to `display: data_table` for a generic "
                "list-of-records view."
            ),
            code=_v.ValidationCode.OUTPUT_DISPLAY_REQUIRES_EACH,
            params={"name": key, "ref": refs[0]},
        ))
    return errors


def kit_outputs(dough: Dough) -> list["ValidationIssue"]:
    """Kit-shipped flours must declare ``model:`` on every object/list output."""
    if dough.id.startswith(_R11_EXEMPT_PREFIXES) or dough.id in ("basic", "advanced"):
        return []
    errors: list[ValidationIssue] = []
    for name, out in dough.outputs.items():
        if out.type in MODEL_REQUIRED_TYPES and not out.model:
            errors.append(_v._issue(
                f"kit flour '{dough.id}' output '{name}' is type '{out.type}' "
                f"but has no `model:`",
                hint=f"add `model: postlab.<kit>.types:<Model>` to "
                     f"outputs.{name} — kit-shipped flours must declare a "
                     f"Pydantic ref for object/list outputs",
                code=_v.ValidationCode.KIT_FLOUR_OUTPUT_MISSING_MODEL,
                params={"dough": dough.id, "name": name, "type": out.type},
            ))
    return errors


def action(dough: Dough) -> list["ValidationIssue"]:
    """Phase-1 leaf-action checks: `action.to:` keys must be declared outputs.

    Also enforces the role boundary: user-authored flours (`user.<slug>`)
    may declare only `action: agent:`. `tool:` and `web:` are reserved for
    kit-shipped flours — tools wrap Python the user didn't write; web steps
    drive a browser session the user didn't record. Users do reasoning over
    data the dough already holds.
    """
    errors: list[ValidationIssue] = []
    action = dough.action
    if action is None:
        return errors

    if is_custom(dough.id):
        if action.tool:
            errors.append(_v._issue(
                f"user-authored flour '{dough.id}' uses `action: tool:` — "
                f"tool flours are kit-shipped only.",
                hint="users author reasoning over data already in the dough "
                     "(`action: agent:`). To reach an external system "
                     "(API, inbox, file, browser), compose a shipped flour "
                     "via `- dough: <kit_flour_id>` in a dough's `steps:`. "
                     "If no shipped flour covers it, that's a kit gap — "
                     "ask the user to choose a different approach.",
                code=_v.ValidationCode.USER_FLOUR_TOOL_FORBIDDEN,
                params={"dough": dough.id},
            ))
        if action.web:
            errors.append(_v._issue(
                f"user-authored flour '{dough.id}' uses `action: web:` — "
                f"web flours come from the recorder, not the chat creator.",
                hint="record the browser steps via the web dough recorder, "
                     "which emits a `web.<site>.<action>` flour. "
                     "Then compose it from a dough's `steps:`.",
                code=_v.ValidationCode.USER_FLOUR_WEB_FORBIDDEN,
                params={"dough": dough.id},
            ))

    declared = set(dough.outputs.keys())
    to = action.to

    if isinstance(to, str):
        if to and to not in declared:
            errors.append(_v._issue(
                f"action.to: '{to}' is not a declared output "
                f"(declared: {sorted(declared) or 'none'})",
                hint=f"declare '{to}' under top-level `outputs:` with a "
                     f"`type:`, or change `action.to:` to one of the "
                     f"already-declared outputs",
                code=_v.ValidationCode.ACTION_TO_UNDECLARED,
                params={
                    "to": to,
                    "declared": ", ".join(sorted(declared)) or "none",
                },
            ))
        # Agent flours mapping to a single object/list output must declare a
        # shape — either an inline `schema:` OR a Pydantic `model:` ref. That
        # shape is what switches the run to provider-native structured output
        # (the agent runner resolves a `model:` to its JSON schema). Without
        # either, the agent returns free-form text that gets shoved into a
        # structured slot and downstream drills get garbage.
        out = dough.outputs.get(to)
        if action.agent and out is not None and out.type in MODEL_REQUIRED_TYPES and not out.schema_ and not out.model:
            errors.append(_v._issue(
                f"agent flour '{dough.id}' output '{to}' is type '{out.type}' "
                f"but declares no `schema:` or `model:`",
                hint=f"add a Pydantic `model:` ref (preferred) or an inline "
                     f"`schema:` to outputs.{to} so the agent returns structured "
                     f"output; a `string` output needs none.",
                code=_v.ValidationCode.AGENT_OBJECT_OUTPUT_NEEDS_SCHEMA,
                params={"dough": dough.id, "name": to, "type": str(out.type)},
            ))
        # Schema/output type compatibility: the engine handles `list +
        # array-root` transparently (wrap+unwrap), but other combos produce
        # a wrap-then-shape-check chain whose error doesn't point at the
        # real bug (the YAML mismatch). Reject at save time so the creator
        # sees the problem in one shot instead of via runtime failure.
        if action.agent and out is not None and isinstance(out.schema_, dict):
            root = out.schema_.get("type")
            if root is not None:
                ok = (
                    (out.type == "list" and root in ("array", "object"))
                    or (out.type == "object" and root == "object")
                )
                if not ok:
                    if out.type == "list":
                        fix = "set `schema.type: array` (engine wraps for the provider) or `object` for a manual wrap"
                    elif out.type == "object":
                        fix = "set `schema.type: object`"
                    else:
                        fix = "remove the `schema:` block — only list/object outputs use structured output"
                    errors.append(_v._issue(
                        f"agent flour '{dough.id}' output '{to}' declares "
                        f"`type: {out.type}` but its `schema.type` is "
                        f"'{root}' — these can't be bound together",
                        hint=fix,
                        code=_v.ValidationCode.AGENT_SCHEMA_TYPE_MISMATCH,
                        params={"dough": dough.id, "name": to,
                                "out_type": str(out.type), "schema_type": str(root)},
                    ))
    elif isinstance(to, dict):
        for key in to:
            if key not in declared:
                errors.append(_v._issue(
                    f"action.to.{key} is not a declared output "
                    f"(declared: {sorted(declared) or 'none'})",
                    hint=f"declare '{key}' under top-level `outputs:` "
                         f"with a `type:`",
                    code=_v.ValidationCode.ACTION_TO_DICT_KEY_UNDECLARED,
                    params={
                        "key": key,
                        "declared": ", ".join(sorted(declared)) or "none",
                    },
                ))

    return errors


def box_completeness(dough: Dough, box: "Box") -> list["ValidationIssue"]:
    """Require both ``name`` and ``description`` in ``en`` for every
    declared input/output. Only ``en`` is checked — the loader falls
    back locale → en, so other locales stay optional. ``name`` is the
    short form-field label (1–3 word noun phrase); ``description`` is
    the longer behavioral sentence surfaced as the UI tooltip AND
    injected as the agent grounding hint at bake time, so both are
    load-bearing.
    """
    issues: list[ValidationIssue] = []
    en = box.get_locale("en")
    if en is None:
        return issues
    for key in dough.inputs.keys():
        entry = en.inputs.get(key)
        name = (entry.name if entry else "") or ""
        desc = (entry.description if entry else "") or ""
        if not name.strip():
            issues.append(_v._issue(
                f"box.yaml is missing an `en.inputs.{key}.name` label.",
                hint=f"add `{key}: {{name: <short label>}}` under `en.inputs` in box.yaml — 1–3 word noun phrase.",
                code=_v.ValidationCode.BOX_INPUT_LABEL_MISSING,
                params={"key": key},
            ))
        if not desc.strip():
            issues.append(_v._issue(
                f"box.yaml is missing an `en.inputs.{key}.description`.",
                hint=f"add a `description:` under `en.inputs.{key}` in box.yaml — a precise behavioral sentence (UI tooltip + agent grounding hint).",
                code=_v.ValidationCode.BOX_INPUT_DESCRIPTION_MISSING,
                params={"key": key},
            ))
    for key in dough.outputs.keys():
        entry = en.outputs.get(key)
        name = (entry.name if entry else "") or ""
        desc = (entry.description if entry else "") or ""
        if not name.strip():
            issues.append(_v._issue(
                f"box.yaml is missing an `en.outputs.{key}.name` label.",
                hint=f"add `{key}: {{name: <short label>}}` under `en.outputs` in box.yaml — 1–3 word noun phrase describing what's produced.",
                code=_v.ValidationCode.BOX_OUTPUT_LABEL_MISSING,
                params={"key": key},
            ))
        if not desc.strip():
            issues.append(_v._issue(
                f"box.yaml is missing an `en.outputs.{key}.description`.",
                hint=f"add a `description:` under `en.outputs.{key}` in box.yaml — a precise behavioral sentence describing the produced value.",
                code=_v.ValidationCode.BOX_OUTPUT_DESCRIPTION_MISSING,
                params={"key": key},
            ))
    return issues
