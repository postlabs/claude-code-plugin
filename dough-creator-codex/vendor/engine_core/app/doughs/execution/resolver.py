"""Resolver — ${ref} string interpolation for runtime context.

The resolver is the bridge between the dough schema and runtime execution.
It resolves ${ref} template strings into concrete values and manages the
incremental execution context (inputs + auto-published step outputs).

Reference syntax:
  ${inputs.x}     — input values
  ${output_name}  — step output (auto-published from called dough's
                    declared ``outputs:`` — no ``save:`` field)
  ${item_name}    — each: loop variable (matches the ``as:`` field)
  ${name.field}   — dot-path into a structured value
  ${name.length}  — list/string length

Note: ``when:`` and ``save:`` step fields were removed. Conditional
gating belongs in a flour; output names auto-publish.
"""

from __future__ import annotations

import json
import re
from typing import Any


REF_PATTERN = re.compile(r"\$\{([^}]+)\}")


class Resolver:
    """Resolves ${ref} strings against a context of named values.

    Context is built incrementally: inputs first, then each step's
    declared outputs auto-publish after execution.
    """

    def __init__(self) -> None:
        self._context: dict[str, Any] = {}

    def set(self, name: str, value: Any) -> None:
        """Add a named value (input binding or step output)."""
        self._context[name] = value

    def publish_dict(self, d: dict[str, Any]) -> None:
        """Publish every top-level key of ``d`` into the context.

        This is the auto-publish path: a ``dough:`` step's bake_output is
        a dict whose keys mirror the called dough's declared ``outputs:``.
        Setting each top-level key into the parent scope makes refs like
        ``${load_queue.batches}`` resolve without an explicit ``save:``
        rename. Strict-mode forbids ``save:`` precisely because this
        replaces it.
        """
        for k, v in d.items():
            self._context[k] = v

    def child(self) -> "Resolver":
        """Create a child resolver that inherits this context.

        Used for each: loops — the child gets the parent's context
        plus the loop variable, without polluting the parent.
        """
        child = Resolver()
        child._context = dict(self._context)
        return child

    def snapshot(self) -> dict[str, Any]:
        """Shallow copy of the live context dict — a read accessor for the
        current scope. Resume no longer uses this: it rebuilds scope from the
        donut via ``execution.replay.resolver_from_donut``.
        """
        return dict(self._context)

    # ── Core resolution ─────────────────────────────────────────────

    def resolve(self, template: Any) -> Any:
        """Resolve a ${ref} template.

        If the entire string is a single ${ref}, returns the raw value
        (preserving type — dict, list, int, etc.).
        If the string contains ${ref} mixed with text, returns string
        with interpolated values.
        If template is not a string, returns it as-is.
        """
        if not isinstance(template, str):
            return template

        # Fast path: entire string is a single ${ref}
        if template.startswith("${") and template.endswith("}") and template.count("${") == 1:
            path = template[2:-1].strip()
            return self._lookup(path)

        # Mixed template: interpolate all ${ref} occurrences
        def _replace(match: re.Match) -> str:
            path = match.group(1).strip()
            val = self._lookup(path)
            if val is None:
                return ""
            if isinstance(val, (dict, list)):
                return json.dumps(val, ensure_ascii=False, default=str)
            return str(val)

        return REF_PATTERN.sub(_replace, template)

    def resolve_dict(self, d: dict[str, Any]) -> dict[str, Any]:
        """Resolve all ${ref} strings in a dict (for with: blocks).

        Recursively resolves nested dicts and lists.
        """
        return {k: self._resolve_value(v) for k, v in d.items()}

    def _resolve_value(self, v: Any) -> Any:
        """Recursively resolve a value — dicts, lists, and strings."""
        if isinstance(v, dict):
            return {k: self._resolve_value(val) for k, val in v.items()}
        if isinstance(v, list):
            return [self._resolve_value(item) for item in v]
        return self.resolve(v)

    # ── Internal ────────────────────────────────────────────────────

    def _lookup(self, path: str) -> Any:
        """Navigate a dot-separated path through the context.

        Examples:
          "inputs.query"      → context["inputs"]["query"]
          "search_results"    → context["search_results"]
          "thread.id"         → context["thread"]["id"]
        """
        parts = path.split(".")
        root = parts[0]

        obj = self._context.get(root)
        if obj is None:
            return None

        for part in parts[1:]:
            if obj is None:
                return None
            if isinstance(obj, dict):
                obj = obj.get(part)
            elif isinstance(obj, (list, str)):
                if part.isdigit():
                    idx = int(part)
                    obj = obj[idx] if idx < len(obj) else None
                elif part in ("length", "count"):
                    obj = len(obj)
                else:
                    obj = None
            else:
                obj = getattr(obj, part, None)

        return obj
