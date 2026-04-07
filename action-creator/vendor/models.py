"""Vendored from: src/backend/app/services/webflow/core/models.py

Only includes SnapshotNode and ActionResult — the minimum needed
for selector validation. See source file for full version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


INTERACTIVE_ROLES = frozenset({
    "button", "link", "textbox", "combobox", "checkbox",
    "radio", "slider", "switch", "searchbox", "tab",
    "menuitem", "option", "treeitem",
})


@dataclass
class SnapshotNode:
    """A node in the parsed accessibility snapshot tree."""

    role: str
    name: str = ""
    ref: str = ""
    indent: int = 0
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[SnapshotNode] = field(default_factory=list)

    @property
    def is_interactive(self) -> bool:
        return self.role in INTERACTIVE_ROLES

    @property
    def is_named_generic(self) -> bool:
        return self.role == "generic" and bool(self.name) and not self.children

    @property
    def is_transparent_generic(self) -> bool:
        return self.role == "generic" and not self.name


@dataclass
class ActionResult:
    """Result from executing a pattern function."""

    success: bool
    data: Any = None
    error: str = ""
