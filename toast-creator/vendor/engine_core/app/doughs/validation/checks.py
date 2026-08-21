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

import json as _json
import re
from typing import TYPE_CHECKING, Any

import app.doughs.validation.engine as _v
from app.policy.tier import ArtifactDescriptor, derive_tier
from app.policy.decide import authorize
from app.doughs.models import DISPLAY_REQUIRED_TYPES, AllStep, DoughStep, Dough, EachStep
from app.doughs.validation.rules import (
    ALLOWED_STEP_KEYS,
    FORBIDDEN_FIELDS,
    FORBIDDEN_STEP_KEYS,
    MODEL_REQUIRED_TYPES,
    custom_root,
    is_custom,
)

if TYPE_CHECKING:
    from app.doughs.definitions.service import DoughStore
    from app.doughs.models import Box
    from app.doughs.validation.engine import ValidationIssue

# What a non-`en` box locale carries. Everything else on `BoxLocale` is
# derived as forbidden rather than listed, so a new slot is refused there the
# day it is added. See `box_completeness`.
NON_EN_ALLOWED = frozenset({"name"})


def non_en_slots() -> tuple[str, ...]:
    """Every ``BoxLocale`` field a non-``en`` locale must not carry."""
    from app.doughs.models.box import BoxLocale

    return tuple(f for f in BoxLocale.model_fields if f not in NON_EN_ALLOWED)


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
                    root = custom_root()
                    hint = (
                        f"lift this agent: call into its own flour at "
                        f"{root}/<slug>/dough.yaml (a flour has `action:`, no "
                        f"`steps:`), then call it from this composition via "
                        f"`- dough: {root}.<slug>`. Authored flours may "
                        f"only use `action: agent:`."
                    )
                else:
                    hint = (
                        f"`{key}:` inside a step is forbidden. To reach an "
                        f"external system, compose a shipped flour: "
                        f"`peel flours --object <o>`. Users cannot author "
                        f"`tool:` flours."
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


# Only these webengine.browser flours consume a tab `handle:` and DRIVE a live
# Page (close_tab/act/run_steps); the read flours take a `snapshot:` (a value),
# so a snapshot ref crossing into a parallel body is harmless. Sharing a DRIVEN
# handle across parallel items clobbers the one Page-per-tab.
_WEB_TAB_PUBLISHERS = frozenset({"webengine.browser.open_tab", "webengine.browser.run_steps"})


def _body_published_bare(do_steps: list[Any]) -> set[str]:
    """Bare ids published by `dough:` steps anywhere in an each/all body (recursing)."""
    names: set[str] = set()
    for raw in do_steps or []:
        if not isinstance(raw, dict):
            continue
        if isinstance(raw.get("dough"), str):
            names.add(_v.bare_dough_path(raw["dough"]))
        if isinstance(raw.get("do"), list):
            names |= _body_published_bare(raw["do"])
    return names


def _body_handle_roots(do_steps: list[Any]) -> set[str]:
    """Roots of every ${ref} bound to a `handle:` with-arg in an each/all body."""
    roots: set[str] = set()
    for raw in do_steps or []:
        if not isinstance(raw, dict):
            continue
        with_ = raw.get("with")
        if isinstance(with_, dict) and isinstance(with_.get("handle"), str):
            for ref in _v._extract_refs(with_["handle"]):
                roots.add(ref.split(".")[0])
        if isinstance(raw.get("do"), list):
            roots |= _body_handle_roots(raw["do"])
    return roots


def parallel_shared_tab(
    dough: Dough,
    parsed_steps: list[Any],
    publishers: dict[str, int],
) -> list["ValidationIssue"]:
    """A browser-tab handle opened OUTSIDE a parallel ``all:`` and threaded into
    its body would clobber one shared Page across concurrent items. Flag it. The
    per-item-tab shape (``open_tab`` INSIDE the body) is safe and not flagged;
    nested-dough bodies (no ``handle:`` arg) are not flagged."""
    errors: list[ValidationIssue] = []
    for idx, step in enumerate(parsed_steps):
        # ★ A ``${ref}`` WIDTH COUNTS AS PARALLEL. Only a literal 1 proves this
        # loop is sequential; a ref is unknown until bake time and the failure
        # it guards — concurrent items clobbering one shared tab — is silent when
        # it happens. Unknown resolves toward the check, not past it.
        if not isinstance(step, AllStep):
            continue
        if isinstance(step.max_parallel, int) and step.max_parallel <= 1:
            continue
        inside = _body_published_bare(step.do)
        for root in _body_handle_roots(step.do):
            if root in inside:
                continue  # handle opened INSIDE the body → per-item tab, safe
            pub_idx = publishers.get(root)
            pub = parsed_steps[pub_idx] if pub_idx is not None else None
            if isinstance(pub, DoughStep) and pub.dough in _WEB_TAB_PUBLISHERS:
                errors.append(_v._issue(
                    f"Step {idx} runs a parallel `all:` (max_parallel "
                    f"{step.max_parallel}) that drives a browser tab handle from "
                    f"'{root}' opened OUTSIDE the loop — concurrent items would "
                    f"clobber the one shared tab.",
                    hint="open the tab INSIDE the `all:` body (one tab per item), "
                         "or use a sequential `each:` to share one tab safely.",
                    code=_v.ValidationCode.ALL_STEP_SHARED_TAB_HANDLE,
                    params={"step": str(idx), "max_parallel": str(step.max_parallel),
                            "root": root},
                ))
                break  # one issue per all: step (dedup across body consumers)
    return errors


def kit_outputs(dough: Dough) -> list["ValidationIssue"]:
    """Kit-shipped flours must declare a shape on every object/list output —
    a Pydantic ``model:`` ref (preferred) OR an inline ``schema:``.

    Agent flours are exempt here: their object-output shape is governed by the
    dedicated ``AGENT_OBJECT_OUTPUT_NEEDS_SCHEMA`` check in ``checks.action``
    (which accepts ``schema:`` OR ``model:`` too). Firing both just double-reports
    the same gap. ``schema:`` counts as a shape because ``drill.py`` drills it and
    it switches structured output on — same as ``model:`` — which is the only
    honest option for a tool that returns a free-form/dynamic-key ``dict``.
    """
    if dough.path.startswith(_R11_EXEMPT_PREFIXES) or dough.path in ("basic", "advanced"):
        return []
    if dough.action is not None and dough.action.agent:
        return []
    errors: list[ValidationIssue] = []
    for name, out in dough.outputs.items():
        if out.type in MODEL_REQUIRED_TYPES and not out.model and not out.schema_:
            errors.append(_v._issue(
                f"kit flour '{dough.path}' output '{name}' is type '{out.type}' "
                f"but has no `model:` or `schema:`",
                hint=f"add a Pydantic ref `model: postlab.<kit>.types:<Model>` "
                     f"(preferred) or an inline `schema:` to outputs.{name} — "
                     f"kit-shipped object/list outputs must declare a shape",
                code=_v.ValidationCode.KIT_FLOUR_OUTPUT_MISSING_MODEL,
                params={"dough": dough.path, "name": name, "type": out.type},
            ))
    return errors


def action(dough: Dough) -> list["ValidationIssue"]:
    """Phase-1 leaf-action checks: `action.to:` keys must be declared outputs.

    Also enforces the role boundary: user-authored flours (`<handle>.<slug>`)
    may declare only `action: agent:`. `tool:` is reserved for kit-shipped
    flours — a tool wraps Python the user didn't write. Users do reasoning
    over data the dough already holds.
    """
    errors: list[ValidationIssue] = []
    action = dough.action
    if action is None:
        return errors

    # The role boundary is an *authorization* decision, relocated to the pure
    # policy leaf (docs_sh/authoring_policy/02-architecture.md). The principal
    # is the artifact's own tier (we validate an at-rest artifact): a <handle>.*
    # flour derives USER, a kit-shipped flour derives THIRD_PARTY/OFFICIAL.
    # `author_tool_flour` requires THIRD_PARTY, so only a USER-tier (<handle>.*)
    # flour is denied — preserving the prior is_custom gate.
    # The emission below (message/hint/ValidationCode) is unchanged; only the
    # allow/deny moved.
    principal = derive_tier(ArtifactDescriptor(id_is_custom=is_custom(dough.path)))
    if action.tool and not authorize(principal, "author_tool_flour").allow:
        errors.append(_v._issue(
            f"user-authored flour '{dough.path}' uses `action: tool:` — "
            f"tool flours are kit-shipped only.",
            hint="users author reasoning over data already in the dough "
                 "(`action: agent:`). To reach an external system "
                 "(API, inbox, file, browser), compose a shipped flour "
                 "via `- dough: <kit_flour_id>` in a dough's `steps:`. "
                 "If no shipped flour covers it, that's a kit gap — "
                 "ask the user to choose a different approach.",
            code=_v.ValidationCode.USER_FLOUR_TOOL_FORBIDDEN,
            params={"dough": dough.path},
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
                f"agent flour '{dough.path}' output '{to}' is type '{out.type}' "
                f"but declares no `schema:` or `model:`",
                hint=f"add a Pydantic `model:` ref (preferred) or an inline "
                     f"`schema:` to outputs.{to} so the agent returns structured "
                     f"output; a `string` output needs none.",
                code=_v.ValidationCode.AGENT_OBJECT_OUTPUT_NEEDS_SCHEMA,
                params={"dough": dough.path, "name": to, "type": str(out.type)},
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
                        f"agent flour '{dough.path}' output '{to}' declares "
                        f"`type: {out.type}` but its `schema.type` is "
                        f"'{root}' — these can't be bound together",
                        hint=fix,
                        code=_v.ValidationCode.AGENT_SCHEMA_TYPE_MISMATCH,
                        params={"dough": dough.path, "name": to,
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
    """Gate a box against the one rule: **a slot exists because something
    reads it, and the agent reads only ``en``.**

    Three directions:

    - ``en`` must label every declared input/output (``name`` +
      ``description``). ``name`` is the form-field label; ``description``
      is the behavioral sentence — the input tooltip, and the only prose
      the agent gets per field through ``query.spec()``.
    - A label for a field the dough does not declare is an unfinished
      rename, checked in EVERY locale.
    - A non-``en`` locale carries ``name`` ONLY (``NON_EN_ALLOWED``). The
      name is unioned across locales into the lexical index
      (``loading.box_locale_names``), so a Korean query can match a dough
      by its Korean name — that is the whole job of a non-``en`` block,
      which is a SEARCH channel and not a display tier. Every other slot
      resolves from ``en``.
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
    # The other two directions. A label for a field that no longer exists reads as
    # documentation and is a rename nobody finished: the UI shows nothing, the
    # agent is grounded on a key it can never be handed, and the stale text
    # survives every check that only walks the dough's own fields. Checked in
    # EVERY locale, because a rename that updated `en` and forgot `ko` is the
    # ordinary way this happens.
    for locale_name in box.locales.keys():
        loc = box.get_locale(locale_name)
        if loc is None:
            continue
        for key in loc.inputs.keys():
            if key not in dough.inputs:
                issues.append(_v._issue(
                    f"box.yaml labels `{locale_name}.inputs.{key}`, which this dough does not declare.",
                    hint=f"remove `{key}` from `{locale_name}.inputs` in box.yaml, or add it to `inputs:` in dough.yaml.",
                    code=_v.ValidationCode.BOX_INPUT_ORPHAN,
                    params={"key": key, "locale": locale_name},
                ))
        for key in loc.outputs.keys():
            if key not in dough.outputs:
                issues.append(_v._issue(
                    f"box.yaml labels `{locale_name}.outputs.{key}`, which this dough does not produce.",
                    hint=f"remove `{key}` from `{locale_name}.outputs` in box.yaml, or add it to `outputs:` in dough.yaml.",
                    code=_v.ValidationCode.BOX_OUTPUT_ORPHAN,
                    params={"key": key, "locale": locale_name},
                ))
        if locale_name == "en":
            continue
        for slot in non_en_slots():
            if getattr(loc, slot, None):
                issues.append(_v._issue(
                    f"box.yaml carries `{locale_name}.{slot}`; a non-`en` locale carries `name` and `about` only.",
                    hint=f"delete `{slot}:` from `{locale_name}:` in box.yaml — every slot but `name`/`about` resolves from `en`.",
                    code=_v.ValidationCode.BOX_NON_EN_SLOT,
                    params={"slot": slot, "locale": locale_name},
                ))
    return issues





def _comment_lines(node, seen: set) -> None:
    """Collect 1-based line numbers of every comment ruamel kept on this tree.

    ruamel hands back BLANK LINES as comment tokens too, so a token only counts
    when its own text actually carries a ``#`` — and one token may span several
    lines, of which only some are comments.
    """
    ca = getattr(node, "ca", None)
    if ca is not None:
        for group in list(ca.items.values()) + [ca.comment]:
            for tok in (group or []):
                for t in (tok if isinstance(tok, list) else [tok]):
                    value = getattr(t, "value", "") or ""
                    mark = getattr(t, "start_mark", None)
                    if "#" not in value or mark is None:
                        continue
                    segments = value.split(chr(10))
                    first = next(i for i, seg in enumerate(segments) if "#" in seg)
                    for offset, segment in enumerate(segments):
                        if "#" in segment:
                            seen.add(mark.line + (offset - first) + 1)
    if isinstance(node, dict):
        for v in node.values():
            _comment_lines(v, seen)
    elif isinstance(node, list):
        for v in node:
            _comment_lines(v, seen)


def no_comments(raw: str, *, filename: str = "dough.yaml") -> list["ValidationIssue"]:
    """A dough, box or spread file carries no commentary.

    These files are read by the UI, by the agent, and by the next author, and a
    comment reaches none of them — it is a note to whoever edited last, which
    then outlives the thing it described. Everything a reader needs is a field:
    ``box.yaml`` carries the prose, ``description`` carries the behaviour.
    Anything that fits in neither belongs in the commit message.

    Decided by the round-trip parser rather than by scanning for ``#``: a hash
    inside a value (a colour, a URL fragment, a Korean sentence) is not a
    comment, and only the parser knows the difference.
    """
    from ruamel.yaml import YAML
    issues: list["ValidationIssue"] = []
    try:
        doc = YAML().load(raw)
    except Exception:  # noqa: BLE001 — unparseable is the schema checks' story
        return issues
    lines: set[int] = set()
    _comment_lines(doc, lines)
    for n in sorted(lines):
        issues.append(_v._issue(
            f"{filename}:{n} carries a comment.",
            hint="delete it — behaviour goes in box.yaml `description`, reasoning goes in the commit message.",
            code=_v.ValidationCode.YAML_COMMENT,
            params={"file": filename, "line": str(n)},
        ))
    return issues


def step_with_keys(
    dough: Dough, store: "DoughStore | None"
) -> list["ValidationIssue"]:
    """A step's ``with:`` may only name inputs the CALLEE declares.

    ``binding.resolve_inputs`` iterates the child's declared ``inputs`` and nothing
    else, so a key the callee does not declare is **silently dropped** — the child
    bakes with a default or an empty value while the parent believes it passed
    something. Both sides succeed; only the result is wrong. That gotcha is recorded
    in ``execution/CLAUDE.md`` and was, until this check, recorded and ungated.

    This is the ``unbound param`` half of the mini-app plan's §3 lint ("every slot
    fed? every param bound? output shape ⊆ slot?"). The other two already exist —
    required roles in ``spreads.validate._gate_blocks``, output-shape in
    ``_field_path_issues`` — and this was the only one of the three with nothing
    behind it, which is also the one §3 lists first.

    Provable from the artifact alone: no data shape makes an undeclared key arrive,
    so there is no legitimate authoring this refuses. Measured before landing —
    every ``with:``/callee pair in a 680-dough profile (199 of them) passes only
    declared keys, so it starts at zero false positives.

    SKIPPED for a routed step (``dough: ${handle}`` names no id to resolve) and when
    the callee does not resolve — ``DOUGH_REF_NOT_FOUND`` already reports that, and a
    second message about the same broken line teaches nothing.

    Says which key to use, not just which is wrong: the message names the closest
    declared input by edit distance when there is one. A refusal that only names the
    defect can cost the feature (mini-app plan §3/§12) — a typo'd key is exactly the
    case where the fix is a single word the author cannot see.
    """
    if store is None:
        return []
    import difflib

    errors: list[ValidationIssue] = []

    def _walk(step_list: list[Any], where: str) -> None:
        for idx, raw in enumerate(step_list or []):
            if not isinstance(raw, dict):
                continue
            at = f"{where}[{idx}]" if where else f"Step {idx}"
            ref = raw.get("dough")
            with_ = raw.get("with")
            if (
                isinstance(ref, str)
                and ref
                and "${" not in ref            # routed step — no id to resolve
                and isinstance(with_, dict)
                and with_
            ):
                callee = store.get_dough(ref)
                if callee is not None:
                    declared = set(callee.inputs)
                    # The other direction: a REQUIRED input the step never passes.
                    # Predicate is `required and default is None` — a declared
                    # default satisfies the callee, so demanding the key anyway
                    # would false-reject the idiomatic "pass only what differs".
                    # `with:` is the ONLY channel (an `each:` body binds `as:` and
                    # still has to pass it), so absence here is genuinely absence.
                    # Measured before landing: of 126 steps whose callee has such an
                    # input, every one passes it — zero false positives.
                    unpassed = sorted(
                        k for k, spec in callee.inputs.items()
                        if getattr(spec, "required", False)
                        and getattr(spec, "default", None) is None
                        and k not in with_
                    )
                    if unpassed:
                        errors.append(_v._issue(
                            f"{at} calls '{ref}' without its required "
                            f"{'inputs' if len(unpassed) > 1 else 'input'} "
                            f"{', '.join(repr(k) for k in unpassed)} — the step will "
                            f"run with nothing bound there.",
                            hint=f"add {', '.join(f'`with.{k}`' for k in unpassed)}. "
                                 f"declared inputs: {sorted(declared)}. ",
                            code=_v.ValidationCode.STEP_WITH_REQUIRED_MISSING,
                            params={
                                "step": at, "ref": ref,
                                "missing": ", ".join(unpassed),
                                "declared": ", ".join(sorted(declared)) or "none",
                            },
                        ))
                    for key in with_:
                        if key in declared:
                            continue
                        near = difflib.get_close_matches(key, sorted(declared), n=1, cutoff=0.7)
                        errors.append(_v._issue(
                            f"{at} passes `with.{key}` but '{ref}' declares no such "
                            f"input — it is DROPPED silently, and the step runs with "
                            f"the default instead.",
                            hint=(f"did you mean `{near[0]}`? " if near else "")
                                 + f"declared inputs: {sorted(declared) or 'none'}. ",
                            code=_v.ValidationCode.STEP_WITH_KEY_UNKNOWN,
                            params={
                                "step": at, "key": key, "ref": ref,
                                "suggest": near[0] if near else "",
                                "declared": ", ".join(sorted(declared)) or "none",
                            },
                        ))
            sub = raw.get("do")
            if isinstance(sub, list):
                _walk(sub, f"{at}.do")

    _walk(dough.steps, "")
    return errors


# A snapshot's aria-ref. Positional, minted per snapshot, and NOT an identity:
# measured on one page across a day the same box was e139, e144, e153, e154,
# e158 and e159 while the render moved between 20 KB and 47 KB.
_ARIA_REF_LITERAL = re.compile(r"^e\d+$")

# The step actions that DRIVE a page inside a `run_steps` list. A read
# (`extract_list`, `evaluate`) that fails and continues costs a column; a drive
# that does it leaves every later step acting on a page that never changed.
_DRIVE_ACTIONS = frozenset({"click", "fill", "press", "select", "select_custom"})


def _literal_refs(value: Any) -> list[str]:
    """Bare aria-refs directly under a `with:` value — string or list of them.

    A `${...}` reference is not one: that is the AGENTIC case, where the ref
    comes from the snapshot the model just read, and it is the only correct way
    to hold one.
    """
    if isinstance(value, str):
        return [value] if _ARIA_REF_LITERAL.match(value.strip()) else []
    if isinstance(value, list):
        return [v.strip() for v in value
                if isinstance(v, str) and _ARIA_REF_LITERAL.match(v.strip())]
    return []


def literal_aria_ref(dough: Dough) -> list["ValidationIssue"]:
    """A saved dough may not address an element by a LITERAL aria-ref.

    ★ THIS IS THE ONE THAT REPORTS SUCCESS WHILE BEING WRONG. A ref that no
    longer resolves fails loudly (``ops: e158 did not resolve on tab``), which is
    the lucky case. Measured on the same page under a different render, the
    pinned ref resolved to the NEIGHBOURING element: the click returned
    ``status: ok`` and the step after it came back with an empty snapshot. So the
    author is told nothing, and the dough drives the wrong node until someone
    reads the output closely.

    Address by selector instead — ``run_steps`` takes a bundle per step and
    resolves it against the live tree at bake time (``role:"name"``,
    ``role:~"partial"``, ``ordinal`` for the Nth match). Verified across ten
    captured renders of one page in ``tests/web/fixtures/selectors.py``.

    Scanned the real profile before shipping this: 636 doughs, ZERO literal
    refs. It rejects nothing anyone has written.
    """
    errors: list[ValidationIssue] = []

    def _walk(steps: list[Any], path: str) -> None:
        for idx, raw in enumerate(steps or []):
            if not isinstance(raw, dict):
                continue
            at = f"{path}[{idx}]" if path else f"Step {idx}"
            with_ = raw.get("with")
            if isinstance(with_, dict):
                for key, value in with_.items():
                    for ref in _literal_refs(value):
                        errors.append(_v._issue(
                            f"{at} passes a literal aria-ref `{key}: {ref}`. A ref "
                            f"is positional and re-minted per snapshot — when it "
                            f"drifts onto a neighbouring element the step still "
                            f"reports ok, so this fails silently rather than "
                            f"loudly.",
                            hint="address by selector: give `run_steps` a "
                                 "`{selectors: [{strategy: role_name, value: "
                                 "'role:\"name\"'}]}` bundle, resolved against the "
                                 "live tree at bake time. A `${...}` ref is fine — "
                                 "that one comes from the snapshot just read.",
                            code=_v.ValidationCode.STEP_LITERAL_ARIA_REF,
                            params={"step": at, "key": key, "ref": ref},
                        ))
            sub = raw.get("do")
            if isinstance(sub, list):
                _walk(sub, f"{at}.do")

    _walk(dough.steps, "")
    return errors


def run_steps_guarded(dough: Dough) -> list["ValidationIssue"]:
    """A `run_steps` drive chain must set `on_error: fail` on at least one step.

    ``_StepBase.on_error`` defaults to ``continue``, which is right for a read
    that may find nothing and wrong for a drive: a click that missed carries on
    into a fill that types into whatever was already on screen, and the list
    finishes reporting success over a page it never moved.

    ★ **The scan population for this one is EMPTY, and saying "0 false positives
    on 636 doughs" would be vacuous** — no dough calls ``run_steps`` yet, so a
    clean sweep proves only that nothing was examined. It ships on provability
    instead, the same ground ``_gate_target_inputs`` stands on: the default is a
    SCHEMA fact, not a data one, so no runtime shape can make an unguarded drive
    chain safe. Requiring one step rather than every step is deliberate — an
    author who set it once has met the default deliberately, and a list with a
    genuinely optional tail step should be able to say so.
    """
    errors: list[ValidationIssue] = []
    for idx, raw in enumerate(dough.steps or []):
        if not isinstance(raw, dict) or raw.get("dough") != "webengine.browser.run_steps":
            continue
        with_ = raw.get("with")
        steps = with_.get("steps") if isinstance(with_, dict) else None
        if not isinstance(steps, list):
            continue  # a `${ref}` step list — nothing to read here
        drives = [s for s in steps
                  if isinstance(s, dict) and s.get("action") in _DRIVE_ACTIONS]
        if not drives or any(s.get("on_error") == "fail" for s in steps
                             if isinstance(s, dict)):
            continue
        errors.append(_v._issue(
            f"Step {idx} runs a {len(drives)}-step drive with no "
            f"`on_error: fail` anywhere — `on_error` defaults to `continue`, so a "
            f"click that missed carries on into the steps after it and the list "
            f"reports success over a page it never moved.",
            hint="set `on_error: fail` on the drive steps (click / fill / press / "
                 "select). Leave it off only where a step is genuinely optional.",
            code=_v.ValidationCode.RUN_STEPS_DRIVE_UNGUARDED,
            params={"step": str(idx), "drives": str(len(drives))},
        ))
    return errors


def web_query_is_applied(dough: Dough) -> list["ValidationIssue"]:
    """A web dough that declares a query must APPLY it before it reads.

    ★ ARRIVAL IS WHERE WEB DOUGHS FAIL, AND IT IS DIAGNOSED LAST. A page that
    never ran the search returns zero rows — indistinguishable from a wrong
    selector, a dead endpoint, or a site with nothing to show — so the reader
    gets re-planned and the arrival never does.

    Every web dough opens a url (55 of 55, measured), and it is for one of two
    things: the url IS the query, built from the inputs; or it is an ENTRY POINT
    that something afterwards applies the query to — typing into a box,
    navigating from inside the page, a child dough that drives. What cannot be
    right is a CONSTANT url followed by a read, with the declared inputs
    referenced nowhere in between: the dough then answers whatever that page
    shows every caller, and reports it as their query's result.

    ★ WHAT THIS DELIBERATELY DOES NOT CHECK is whether the site ACCEPTS a
    constructed arrival — `postlab.naver_com.flight.fares` opens one cold happily while
    `postlab.naver_com.shopping.search` earns a captcha for it, same vendor. That is a
    live fact per service, knowable only by firing it, so it belongs to the read
    path's verdict and not to a static rule. Guessing it here would flag working
    doughs, which is the expensive direction.
    """
    if not dough.steps:
        return []
    required = [
        name for name, spec in (dough.inputs or {}).items()
        if getattr(spec, "required", False) and name not in ("handle", "url")
    ]
    if not required:
        return []

    flat: list[dict] = []

    def _flatten(raw_steps: list) -> None:
        for raw in raw_steps or []:
            if not isinstance(raw, dict):
                continue
            body = raw.get("each") or raw.get("all")
            if isinstance(body, dict):
                _flatten(body.get("do") or [])
                continue
            flat.append(raw)

    _flatten([s if isinstance(s, dict) else getattr(s, "model_dump", dict)()
              for s in dough.steps])

    opened = next((i for i, s in enumerate(flat)
                   if str(s.get("dough") or "").endswith(".open_tab")), None)
    if opened is None:
        return []
    url = str((flat[opened].get("with") or {}).get("url") or "")
    if "${inputs." in url:
        return []  # the url IS the query

    reads = ("read_call", "read_state", "read_records", "extract_")
    first_read = next(
        (i for i, s in enumerate(flat)
         if any(r in str(s.get("dough") or "") for r in reads)),
        len(flat),
    )
    between = _json.dumps(flat[opened + 1:first_read], ensure_ascii=False)
    # A whole-object ${inputs} reference applies every input (it is json-dumped
    # into the step verbatim, then read field-by-field) — the escaped form a
    # write dough uses to survive a quote/apostrophe in its text.
    if "${inputs}" in between:
        return []
    if any("${inputs.%s}" % name in between for name in required):
        return []

    return [_v._issue(
        f"opens a constant url ({url or '—'}) and reads it without applying "
        f"{', '.join(required)} — every caller gets whatever that page shows, "
        f"reported as their result.",
        hint="either build the query into the open_tab url, or drive it in "
             "before the read (type into the search box, navigate from inside "
             "the page, or call a child dough that does). If the page really is "
             "the same for every caller, the inputs are not required.",
        code=_v.ValidationCode.WEB_QUERY_NEVER_APPLIED,
        params={"url": url, "inputs": required},
    )]


# ── Login contract — the four rungs every */login/dough.yaml MUST carry ────────
# A login dough is hand-authored with no shared skeleton, so each re-invents the
# same four rungs and a silently omitted one passes every other test while looking
# exactly like a site block. Enforce the skeleton the way an invalid verb fails a
# kit: a login dough missing any rung is REFUSED.
#
# Each rung is recognised by a SANCTIONED login flour, a recognised guard, OR a
# CONTROL-ADDRESSED submit — a `document.querySelector(<css>).click()` /
# `.submit()` / `.requestSubmit()`. The last one is not a concession: it is what
# the proven doughs actually do (29cm/brandi submit their credential form with
# exactly this), and it is what the login-submit bug demands — address the real
# submit control by CSS, never a substring of visible text. Measured: a CDP
# pointer click (run_steps / click_text) TIMES OUT on naver's login button
# (actionability, 26s over 5 attempts), while the synthetic `.click()` fires its
# handler. What this rung still refuses is a login with NO deliberate submit at
# all — the silent-no-op class. A `.click()` with no querySelector/getElementById
# is a text/ref guess, not a control address, and does not count.
_LOGIN_ARRIVE = {"webengine.browser.open_tab", "webengine.browser.site_login"}
_LOGIN_ADDRESS = {
    "webengine.browser.login_sso", "webengine.browser.site_login",
    "webengine.browser.pick_social", "webengine.browser.click_social",
    "webengine.browser.chrome_fill_password",
    "webengine.browser.identify", "webengine.browser.click_text",
}
_LOGIN_SUBMIT = {
    "webengine.browser.login_sso", "webengine.browser.site_login",
    "webengine.browser.click_social", "webengine.browser.click_text",
}
_LOGIN_AWAIT = {"webengine.browser.await_login", "webengine.browser.verify_session"}
_POLL_LOOP = re.compile(r"for\s*\(|while\s*\(")
# A CONTROL-ADDRESSED submit inside an eval_js: the real submit control is
# selected by CSS/id and clicked/submitted. This is the proven submit shape
# (29cm/brandi), and the fix the login-submit bug requires. The querySelector /
# getElementById requirement is what distinguishes a control address from a text
# or aria-ref guess — a bare `.click()` on an unknown node does not satisfy it.
_CONTROL_SELECT = re.compile(r"querySelector|getElementById")
_CONTROL_SUBMIT = re.compile(r"\.(click|submit|requestSubmit)\s*\(")
# Signed-in guard: a flour that self-guards (no provider button / a fresh-tab
# verify when already signed in) OR a required:false primary click OR an explicit
# short-circuit that reads the session and stops. The MARK is a stop PHRASE, only
# ever written in a guard — never in a plain end-of-run verify (which returns a
# logged_in flag, it does not announce "no login needed").
_LOGIN_GUARD_FLOURS = {
    "webengine.browser.login_sso", "webengine.browser.site_login",
    "webengine.browser.verify_session",
}
_SIGNED_IN_MARK = re.compile(
    r"already signed in|no login needed|already off the login|"
    r"already[- ]?auth|idempotent",
    re.IGNORECASE,
)


def _login_steps(steps: list[Any]):
    """Yield every step dict of a composition, recursing into each/all bodies."""
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        if "dough" in s:
            yield s
        if ("each" in s or "all" in s) and isinstance(s.get("do"), list):
            yield from _login_steps(s["do"])


def login_contract(dough: "Dough") -> list["ValidationIssue"]:
    """Refuse a ``*/login/dough.yaml`` missing any of the five login rungs.

    arrive → address → submit → await → signed-in. Each is satisfied by a
    sanctioned login flour or a recognised guard (not a bespoke eval), so a rung
    cannot be silently omitted or faked with a synthetic click. Non-login doughs
    are skipped.
    """
    if not dough.path.endswith(".login"):
        return []

    flours: set[str] = set()
    run_actions: set[str] = set()
    act_kinds: set[str] = set()
    has_poll = False
    has_reqfalse_click = False
    has_signed_in_shortcircuit = False
    has_control_submit = False
    for step in _login_steps(dough.steps):
        fid = step.get("dough", "")
        flours.add(fid)
        with_ = step.get("with") or {}
        if fid in {"webengine.browser.click_text", "webengine.browser.click_social"} \
                and with_.get("required") is False:
            has_reqfalse_click = True
        if fid == "webengine.browser.run_steps":
            for st in with_.get("steps") or []:
                if isinstance(st, dict) and st.get("action"):
                    run_actions.add(st["action"])
        if fid == "webengine.browser.act":
            kind = with_.get("kind")
            if kind:
                act_kinds.add(kind)
            code = with_.get("code")
            if kind == "eval_js" and isinstance(code, str):
                if _POLL_LOOP.search(code) and "setTimeout" in code:
                    has_poll = True
                if _SIGNED_IN_MARK.search(code):
                    has_signed_in_shortcircuit = True
                if _CONTROL_SELECT.search(code) and _CONTROL_SUBMIT.search(code):
                    has_control_submit = True

    rungs = {
        "arrive": (
            bool(flours & _LOGIN_ARRIVE),
            "open the login page and click through the site "
            "(webengine.browser.open_tab / site_login), never a cold URL straight "
            "at the provider.",
        ),
        "address": (
            bool(flours & _LOGIN_ADDRESS) or "fill" in run_actions,
            "engage the login control — a social button (login_sso / click_text) "
            "or the id/password fields (chrome_fill_password / a run_steps fill).",
        ),
        "submit": (
            bool(flours & _LOGIN_SUBMIT)
            or bool({"click", "press_key", "press"} & run_actions)
            or "press_key" in act_kinds
            or has_control_submit,
            "a DELIBERATE submit that addresses the REAL control — a "
            "`document.querySelector(<css>).click()` / `.submit()` (the proven "
            "shape), a run_steps css= click, a press_key, or a provider flour "
            "(login_sso / site_login / click_social). Never a substring of visible "
            "text: naver's '로그인' matches '로그인 상태 유지', so the click lands on the "
            "checkbox and the form is filled but never pressed.",
        ),
        "await": (
            bool(flours & _LOGIN_AWAIT) or has_poll,
            "wait for the result — webengine.browser.await_login (the nav-tolerant "
            "OAuth-redirect wait) or a polling verify. Reading the session once, "
            "mid-redirect, reports not-signed-in and looks exactly like a block.",
        ),
        "signed_in": (
            bool(flours & _LOGIN_GUARD_FLOURS)
            or has_reqfalse_click
            or has_signed_in_shortcircuit,
            "short-circuit when ALREADY signed in — read the session first and stop "
            "(throw 'already signed in — no login needed'), or use login_sso / "
            "site_login / verify_session / a required:false click. Without it a dough "
            "re-drives a login on a live account, the expensive failure. A page whose "
            "login form persists when signed in (naver, lotteon) needs the explicit "
            "session read; form-presence is not the signal.",
        ),
    }
    issues: list[ValidationIssue] = []
    for rung, (ok, hint) in rungs.items():
        if not ok:
            issues.append(_v._issue(
                f"login dough is missing the `{rung}` rung of the login contract.",
                hint=hint,
                code=_v.ValidationCode.LOGIN_CONTRACT_INCOMPLETE,
                params={"rung": rung},
            ))
    return issues
