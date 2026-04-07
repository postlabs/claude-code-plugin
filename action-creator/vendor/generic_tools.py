"""Vendored generic tools — provides _collect_text for action_replay.py."""

from __future__ import annotations

from .models import SnapshotNode


def _collect_text(node: SnapshotNode) -> str:
    """Recursively collect all text content from a SnapshotNode tree."""
    parts: list[str] = []
    if node.name:
        parts.append(node.name)
    for child in node.children:
        text = _collect_text(child)
        if text:
            parts.append(text)
    return " ".join(parts)
