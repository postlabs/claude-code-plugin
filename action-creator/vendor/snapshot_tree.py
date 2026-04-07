"""Vendored from: src/backend/app/services/webflow/core/snapshot_tree.py

Only includes parse_snapshot_tree, walk_tree, find_in_tree, find_all_in_tree.
"""

from __future__ import annotations

import re
from typing import Generator

from .models import SnapshotNode


def _unescape_name(raw: str) -> str:
    if "\\" not in raw:
        return raw
    return re.sub(r"\\(.)", r"\1", raw)


_ATTR_PATTERN = re.compile(r"\[(pressed|disabled|expanded|selected|checked)\]")
_REF_PATTERN = re.compile(r"\[ref=([a-z0-9]+)\]")
_QUOTED_NAME_PATTERN = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _parse_line(line: str) -> SnapshotNode | None:
    stripped = line.strip()
    if not stripped.startswith("-"):
        return None

    indent = (len(line) - len(line.lstrip())) // 2
    content = stripped.lstrip("-").strip()
    if not content:
        return None

    if content.startswith("'") and content.endswith("':"):
        content = content[1:-2] + ":"
    elif content.startswith("'") and content.endswith("'"):
        content = content[1:-1]

    parts = content.split(None, 1)
    role = parts[0].rstrip(":") if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if not role or role.startswith("[") or role.startswith('"'):
        return None

    if role == "/url" and rest:
        url_val = rest.strip().strip('"')
        return SnapshotNode(role=role, name=url_val, indent=indent)

    name = ""
    m = _QUOTED_NAME_PATTERN.search(rest)
    if m:
        name = _unescape_name(m.group(1))

    if not name and ": " in rest:
        name = rest.split(": ", 1)[1].strip()
    if not name and not rest and ": " in content:
        after_colon = content.split(": ", 1)[1].strip()
        after_colon = _REF_PATTERN.sub("", after_colon).strip()
        after_colon = _ATTR_PATTERN.sub("", after_colon).strip()
        if after_colon:
            name = after_colon

    ref = ""
    ref_m = _REF_PATTERN.search(rest)
    if ref_m:
        ref = ref_m.group(1)

    attrs: dict[str, str] = {}
    for attr_m in _ATTR_PATTERN.finditer(rest):
        attrs[attr_m.group(1)] = "true"

    return SnapshotNode(role=role, name=name, ref=ref, indent=indent, attrs=attrs)


def parse_snapshot_tree(raw: str) -> tuple[SnapshotNode, str]:
    """Parse snapshot text into a tree structure."""
    root = SnapshotNode(role="root", name="", indent=-1)
    stack: list[SnapshotNode] = [root]
    page_url = ""
    current_tab_url = ""

    for line in raw.splitlines():
        s = line.strip()

        if s.startswith("- Page URL:"):
            page_url = s.split(": ", 1)[1].strip() if ": " in s else ""
            continue
        if s.startswith("- Page Title:"):
            continue

        if "(current)" in s and "](" in s:
            m = re.search(r'\]\(([^)]+)\)', s)
            if m:
                current_tab_url = m.group(1)

        node = _parse_line(line)
        if node is None:
            continue

        while len(stack) > 1 and stack[-1].indent >= node.indent:
            stack.pop()

        stack[-1].children.append(node)
        stack.append(node)

    if current_tab_url and not current_tab_url.startswith("chrome-extension://"):
        page_url = current_tab_url

    return root, page_url


def walk_tree(node: SnapshotNode) -> Generator[SnapshotNode, None, None]:
    yield node
    for child in node.children:
        yield from walk_tree(child)


def find_in_tree(
    root: SnapshotNode, role: str, name: str | None = None,
) -> SnapshotNode | None:
    for node in walk_tree(root):
        if node.role != role:
            continue
        if name is not None and node.name != name:
            continue
        return node
    return None


def find_all_in_tree(
    root: SnapshotNode, role: str, name: str | None = None,
) -> list[SnapshotNode]:
    results = []
    for node in walk_tree(root):
        if node.role != role:
            continue
        if name is not None and node.name != name:
            continue
        results.append(node)
    return results
