"""Shared template resolution for all parameter formats.

Handles three formats that LLMs may generate:
  {{key}}  — Jinja-style (schema standard for URLs)
  {key}    — Python-style (Planner LLM tendency)
  $key     — Shell-style (schema standard for fill values)

All components should use resolve_templates() instead of
implementing their own replacement logic.
"""

from __future__ import annotations

import re
from typing import Any

# Match $key but not $$key (escaped) and not ${key} (already handled by {key})
_DOLLAR_PATTERN = re.compile(r"\$([a-zA-Z_][a-zA-Z0-9_]*)")


def resolve_templates(text: str, params: dict[str, Any]) -> str:
    """Replace all template formats with parameter values."""
    if not params or not isinstance(text, str):
        return text

    for key, val in params.items():
        sval = str(val)
        text = text.replace(f"{{{{{key}}}}}", sval)  # {{key}}
        text = text.replace(f"{{{key}}}", sval)       # {key}

    # $key — word-boundary aware to avoid replacing $keyword in $keywords
    def _dollar_replacer(m: re.Match) -> str:
        name = m.group(1)
        if name in params:
            return str(params[name])
        return m.group(0)

    text = _DOLLAR_PATTERN.sub(_dollar_replacer, text)
    return text


def resolve_deep(obj: Any, params: dict[str, Any]) -> Any:
    """Recursively resolve templates in strings, dicts, and lists."""
    if isinstance(obj, str):
        return resolve_templates(obj, params)
    if isinstance(obj, dict):
        return {k: resolve_deep(v, params) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_deep(item, params) for item in obj]
    return obj
