"""Reference drilling — validate ``${root.p1[.p2…]}`` paths against a target
dough's declared outputs, but only the levels whose shape is *provable* (a
Pydantic ``model:`` or an inline ``schema:``).

Pure: takes models, returns plain data (issue-param dicts / field sets), no
``ValidationIssue`` coupling. Used by both the save- and load-time validators.
"""

from __future__ import annotations

import functools
from typing import Any

from app.doughs.models import Dough, OutputDef


@functools.lru_cache(maxsize=256)
def _resolve_model_fields(model_ref: str) -> set[str] | None:
    """Return the top-level field names of a Pydantic model referenced as
    ``module.path:ClassName``. Returns ``None`` if the ref is malformed, the
    module won't import, the class doesn't exist, or it isn't a Pydantic
    ``BaseModel``. Callers treat ``None`` as "skip the check".

    Cached because a single dough often drills into the same model multiple
    times across refs.
    """
    if ":" not in model_ref:
        return None
    module_path, class_name = model_ref.rsplit(":", 1)
    try:
        import importlib
        mod = importlib.import_module(module_path)
    except Exception:
        return None
    cls = getattr(mod, class_name, None)
    if cls is None:
        return None
    try:
        from pydantic import BaseModel
    except ImportError:
        return None
    if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
        return None
    return set(cls.model_fields.keys())


# Dot-path segments the resolver treats specially (see resolver._resolve_path):
# `.length`/`.count` on lists/strings, numeric indices on lists. They are never
# object field names, so the drill check must not flag them.
_SPECIAL_DRILL = {"length", "count"}


def output_fields(out_def: OutputDef) -> set[str] | None:
    """Top-level field names of an object output — from its Pydantic ``model:``
    OR its inline ``schema:`` (``properties`` keys). ``None`` when neither is
    declared (can't check) so callers skip rather than false-flag.

    The schema arm is why user-authored doughs (which declare object outputs
    with inline ``schema:``, never ``model:``) finally get drill-checked.
    """
    if out_def.model:
        return _resolve_model_fields(out_def.model)
    schema = out_def.schema_
    if isinstance(schema, dict):
        props = schema.get("properties")
        if isinstance(props, dict):
            return set(props.keys())
    return None


def _field_not_in_output(seg: str, out_def: OutputDef) -> bool:
    """True only when ``seg`` is provably not a field of ``out_def`` (object
    type, known field set, ``seg`` absent). Special tokens / unknowable shapes
    return False so we never flag a drill we can't disprove."""
    if seg in _SPECIAL_DRILL or seg.isdigit():
        return False
    if out_def.type != "object":
        return False
    fields = output_fields(out_def)
    return fields is not None and seg not in fields


def issue(ref_path: str, target: Dough) -> dict[str, Any] | None:
    """Validate ``${root.p1[.p2…]}`` against ``target``'s declared outputs, but
    ONLY the level we can prove: a field drilled into an output whose shape is
    *known*. Returns issue params (``{field, owner, valid}``) on a provable
    miss, else ``None``.

    Deliberately NOT enforced: "the first segment must be a declared output
    handle". Many shipped ``advanced.*`` doughs declare a single opaque
    ``type: object`` output and drill its *inner* fields at the envelope level.
    Mirrors ``execution.scope.publish``'s two shapes:

    - **collision** — ``root`` is itself an output handle; ``${root}`` is that
      handle's value, so ``p1`` is a *field* of ``outputs[root]``.
    - **envelope** — otherwise ``p1`` is a handle; only when it names a *known*
      output do we check ``p2`` against that output's fields.
    """
    parts = ref_path.split(".")
    if len(parts) < 2:
        return None
    root = parts[0]
    outs = target.outputs

    if root in outs:  # collision: ${root} = value of handle `root`
        if _field_not_in_output(parts[1], outs[root]):
            fields = output_fields(outs[root]) or set()
            return {"field": parts[1], "owner": root,
                    "valid": ", ".join(sorted(fields)) or "none"}
        return None

    # envelope: only drill-check when p1 names a known, typed output handle.
    p1 = parts[1]
    if p1 in outs and len(parts) >= 3 and _field_not_in_output(parts[2], outs[p1]):
        fields = output_fields(outs[p1]) or set()
        return {"field": parts[2], "owner": p1,
                "valid": ", ".join(sorted(fields)) or "none"}
    return None


def published_shape(target: Dough, root: str) -> tuple[set[str], str | None]:
    """The top-level field set that a bare ``${root}`` produces, plus an
    optional handle to drill to. Mirrors ``execution.scope.publish``:

    - **collision** (``root`` is a handle) — ``${root}`` is that handle's value,
      so its own object fields; nothing further to drill.
    - **envelope** — ``${root}`` is ``{handle: value}``, so the handle names;
      suggest the lone handle when the dough publishes exactly one.

    Returns ``(set(), None)`` when the shape isn't knowable, so the caller's
    disjoint test simply won't fire.
    """
    outs = target.outputs
    if root in outs:
        fields = output_fields(outs[root]) if outs[root].type == "object" else None
        return (fields or set()), None
    return set(outs.keys()), (next(iter(outs)) if len(outs) == 1 else None)
