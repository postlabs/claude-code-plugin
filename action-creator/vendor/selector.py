"""Vendored from: src/backend/app/services/webflow/core/selector.py

3-Strategy Selector System for Site Agent.
NOTE: 원본 수정 시 이 vendor 복사본도 동기화 필요.

resolve_selector() tries each strategy in priority order (fallback chain).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import SnapshotNode
from .snapshot_tree import walk_tree, find_in_tree, find_all_in_tree


# ── Data models ───────────────────────────────────────────────────


@dataclass
class Selector:
    """A single selector strategy for an element."""

    strategy: str  # "role_name", "content", "tree_path", "relative"
    value: str  # e.g. 'button:"보내기"', 'dialog > button:"확인"'
    priority: int  # 1=role_name/content, 2=tree_path, 3=relative
    unique: bool = True
    ordinal: int = 0  # 0-based index among same-value matches
    match_count: int = 1
    context_text: str = ""  # content strategy: sibling text anchor


@dataclass
class SelectorSet:
    """All selectors for a single element."""

    selectors: list[Selector] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.selectors) == 0

    @property
    def best(self) -> Selector | None:
        if not self.selectors:
            return None
        return min(self.selectors, key=lambda s: s.priority)

    def to_spec(self) -> dict[str, Any]:
        """Serialize to YAML-compatible dict.

        If only a single role_name selector with unique match,
        returns shorthand { role, name } for backward compatibility.
        Otherwise returns full { selectors: [...] } format.
        """
        if not self.selectors:
            return {}

        # Shorthand: single unique role_name → { role, name }
        if (
            len(self.selectors) == 1
            and self.selectors[0].strategy == "role_name"
            and self.selectors[0].unique
        ):
            role, name, _partial = _parse_selector_value(self.selectors[0].value)
            spec: dict[str, Any] = {"role": role}
            if name and _partial:
                spec["name_contains"] = name
            elif name:
                spec["name"] = name
            return spec

        # Full format
        sel_list = []
        for sel in self.selectors:
            entry: dict[str, Any] = {
                "strategy": sel.strategy,
                "value": sel.value,
                "priority": sel.priority,
            }
            if not sel.unique:
                entry["unique"] = False
                entry["ordinal"] = sel.ordinal
                entry["match_count"] = sel.match_count
            if sel.context_text:
                entry["context_text"] = sel.context_text
            sel_list.append(entry)
        return {"selectors": sel_list}


# ── Generic roles to skip in tree path / ancestor walking ────────


_GENERIC_ROLES = frozenset({
    "generic", "none", "presentation", "group",
})

_LANDMARK_ROLES = frozenset({
    "navigation", "main", "banner", "complementary",
    "contentinfo", "form", "region", "search",
})

_ROLE_COMPAT: dict[str, set[str]] = {
    "textbox": {"textbox", "searchbox", "combobox"},
    "combobox": {"combobox", "textbox", "searchbox"},
    "searchbox": {"searchbox", "textbox", "combobox"},
    "button": {"button", "menuitem"},
    "link": {"link", "menuitem"},
    "img": {"img", "image"},
}


def _esc(name: str) -> str:
    return name.replace('\\', '\\\\').replace('"', '\\"')


# ── Generation: build SelectorSet for a node ─────────────────────


def generate_selector_set(
    node: SnapshotNode,
    tree: SnapshotNode,
) -> SelectorSet:
    """Generate a SelectorSet for a node within a tree.

    Produces up to 6 selectors. Each is verified by resolving it back
    against the tree — only selectors that resolve to the same node (ref)
    are kept.
    """
    selectors: list[Selector] = []
    target_ref = node.ref

    def _add_if_valid(sel: Selector | None) -> None:
        """Add selector only if it resolves back to the same node."""
        if not sel:
            return
        if not target_ref:
            # No ref to verify against — keep it
            selectors.append(sel)
            return
        resolved = _try_resolve(tree, sel)
        if resolved and resolved.ref == target_ref:
            selectors.append(sel)

    # 1. role_name
    role_name_sel = _gen_role_name(node, tree)
    _add_if_valid(role_name_sel)

    # 1b. content — only when role_name is non-unique
    if role_name_sel and not role_name_sel.unique:
        _add_if_valid(_gen_content(node, tree))

    # 2a. tree_path (with name)
    _add_if_valid(_gen_tree_path(node, tree))

    # 2b. relative_index_grouped (repeating group detection — best for lists/cards)
    for grouped_sel in _gen_relative_index_grouped(node, tree):
        _add_if_valid(grouped_sel)

    # 2c. relative_index (landmark + flat position — fallback)
    _add_if_valid(_gen_relative_index(node, tree))

    # 2d. tree_path_index (structure + position, no name dependency)
    _add_if_valid(_gen_tree_path_index(node, tree))

    # 3. relative (landmark + name)
    _add_if_valid(_gen_relative(node, tree))

    return SelectorSet(selectors=selectors)


def _gen_role_name(node: SnapshotNode, tree: SnapshotNode) -> Selector | None:
    """Generate role_name selector. Priority 1."""
    if not node.role:
        return None

    # Count matches
    matches = find_all_in_tree(tree, node.role, name=node.name if node.name else None)
    # Exclude root and self-like nodes without ref
    matches = [m for m in matches if m.ref]

    match_count = len(matches)
    unique = match_count <= 1

    # Determine ordinal (position of this node among matches)
    ordinal = 0
    for i, m in enumerate(matches):
        if m.ref == node.ref:
            ordinal = i
            break

    if node.name:
        value = f'{node.role}:"{_esc(node.name)}"'
    else:
        value = node.role

    return Selector(
        strategy="role_name",
        value=value,
        priority=1,
        unique=unique,
        ordinal=ordinal,
        match_count=max(match_count, 1),
    )


def _gen_content(node: SnapshotNode, tree: SnapshotNode) -> Selector | None:
    """Generate content selector using sibling text. Priority 1."""
    context_text = _find_sibling_text(node, tree)
    if not context_text:
        return None

    if node.name:
        value = f'{node.role}:"{_esc(node.name)}"'
    else:
        value = node.role

    return Selector(
        strategy="content",
        value=value,
        priority=1,
        unique=True,  # Assume sibling text distinguishes
        context_text=context_text,
    )


def _gen_tree_path(node: SnapshotNode, tree: SnapshotNode) -> Selector | None:
    """Generate tree_path selector from ancestor chain. Priority 2."""
    ancestors = _get_ancestors(node, tree)
    if not ancestors:
        return None

    # Filter to meaningful (non-generic) ancestors, max 3
    meaningful = [a for a in ancestors if a.role not in _GENERIC_ROLES][:3]
    if not meaningful:
        return None

    # Build path: ancestor > ... > target
    parts: list[str] = []
    for anc in meaningful:
        if anc.name:
            parts.append(f'{anc.role}:"{_esc(anc.name)}"')
        else:
            parts.append(anc.role)

    # Add target
    if node.name:
        parts.append(f'{node.role}:"{_esc(node.name)}"')
    else:
        parts.append(node.role)

    value = " > ".join(parts)

    # Check uniqueness: does this path resolve to exactly one node?
    unique = _verify_tree_path(tree, parts)

    return Selector(
        strategy="tree_path",
        value=value,
        priority=2,
        unique=unique,
    )


def _gen_tree_path_index(node: SnapshotNode, tree: SnapshotNode) -> Selector | None:
    """Generate index-based tree_path selector. Priority 2.

    Uses structural position (sibling index) instead of name.
    Resilient to dynamic name changes (prices, timestamps).

    Includes generic parents with positional index to keep scope narrow:
      main > generic[5] > link[0]
    rather than skipping generics which produces overly broad paths:
      main > link[47]

    Example: dialog > option[0]  (first option inside dialog)
    """
    ancestors = _get_ancestors(node, tree)
    if not ancestors:
        return None

    # Immediate parent — index is always relative to this
    parent = ancestors[0]

    # Sibling index: position among parent's children with same role
    sibling_idx = 0
    for child in parent.children:
        if child is node or (child.ref and child.ref == node.ref):
            break
        if child.role == node.role:
            sibling_idx += 1

    # Build ancestor path: walk up from parent, include generics with index.
    # The path must be resolvable from root — the first (topmost) segment
    # must be findable in root.children. We keep walking up until we reach
    # either a meaningful (non-generic) anchor OR a node that is a direct
    # child of root (which the resolver can find).
    # Build full ancestor path from target up to a root child, then
    # compress by skipping generic[0] segments (only-child-of-role).
    raw_parts: list[tuple[str, bool]] = []  # (segment_str, is_skippable)
    root_child_refs = {c.ref for c in tree.children if c.ref}
    reached_root = False
    for i, anc in enumerate(ancestors):
        if anc.role in _GENERIC_ROLES:
            # Compute index among parent's same-role children
            if i + 1 < len(ancestors):
                grandparent = ancestors[i + 1]
            else:
                grandparent = tree
            gen_idx = 0
            same_role_count = 0
            for child in grandparent.children:
                if child.role == anc.role:
                    if child is anc or (child.ref and child.ref == anc.ref):
                        break
                    gen_idx += 1
                    same_role_count += 1
            same_role_count += 1  # include self
            # Count total same-role siblings to decide if skippable
            total_same = sum(1 for c in grandparent.children if c.role == anc.role)
            is_root_child = anc.ref in root_child_refs
            skippable = (gen_idx == 0 and total_same == 1 and not is_root_child)
            raw_parts.append((f"{anc.role}[{gen_idx}]", skippable))
        else:
            if anc.name:
                raw_parts.append((f'{anc.role}:"{_esc(anc.name)}"', False))
            else:
                raw_parts.append((anc.role, False))

        if anc.ref in root_child_refs:
            reached_root = True
            break

    if not raw_parts:
        return None

    # Compress: drop skippable generic[0] segments, keep at most 5 total
    path_parts = [seg for seg, skip in raw_parts if not skip]
    # If all were skippable, keep at least the root child
    if not path_parts and raw_parts:
        path_parts = [raw_parts[-1][0]]

    # Reverse: ancestors are bottom-up, path should be top-down
    path_parts.reverse()
    path_parts.append(f"{node.role}[{sibling_idx}]")

    value = " > ".join(path_parts)

    return Selector(
        strategy="tree_path_index",
        value=value,
        priority=2,
        unique=True,
    )


def _gen_relative(node: SnapshotNode, tree: SnapshotNode) -> Selector | None:
    """Generate relative selector using nearest landmark. Priority 3."""
    if not node.role:
        return None

    # Find landmarks in tree
    landmarks: list[SnapshotNode] = []
    for n in walk_tree(tree):
        if n.role in _LANDMARK_ROLES and n.name:
            landmarks.append(n)

    if not landmarks:
        return None

    # Pick the landmark that is an ancestor of this node, or the closest one
    anchor = _find_closest_landmark(node, landmarks, tree)
    if not anchor:
        anchor = landmarks[0]

    if node.name:
        value = f'near({anchor.role}:"{_esc(anchor.name)}") > {node.role}:"{_esc(node.name)}"'
    else:
        value = f'near({anchor.role}:"{_esc(anchor.name)}") > {node.role}'

    return Selector(
        strategy="relative",
        value=value,
        priority=3,
        unique=False,
    )


_SECTION_HEADING_ROLES = frozenset({"heading", "strong"})


def _gen_relative_index(node: SnapshotNode, tree: SnapshotNode) -> Selector | None:
    """Generate relative_index selector: nearby heading + positional index. Priority 3.

    Finds the closest heading/landmark that is a sibling or ancestor-sibling
    of the target, then counts same-role elements within that section scope.

    Example: section(heading:"뉴스") > link[0]
    → first link within the section that has heading "뉴스"

    This is resilient to text changes — only depends on section structure
    and position within the section.
    """
    if not node.role:
        return None

    # Walk up to find the section: a parent whose children include
    # both a heading/landmark and the target (or target's ancestor)
    ancestors = _get_ancestors(node, tree)
    if not ancestors:
        return None

    section_parent = None
    section_heading = None

    for depth, anc in enumerate(ancestors):
        # Search direct children + 1 level deeper (grandchildren)
        for child in anc.children:
            if child.role in _SECTION_HEADING_ROLES and child.name:
                section_parent = anc
                section_heading = child
                break
            if child.role in _LANDMARK_ROLES and child.name:
                section_parent = anc
                section_heading = child
                break
            # 1 level deeper: check grandchildren
            for grandchild in child.children:
                if grandchild.role in _SECTION_HEADING_ROLES and grandchild.name:
                    section_parent = anc
                    section_heading = grandchild
                    break
                if grandchild.role in _LANDMARK_ROLES and grandchild.name:
                    section_parent = anc
                    section_heading = grandchild
                    break
            if section_heading:
                break
        if section_heading:
            break
        # Don't go too far up — max 5 levels
        if depth >= 5:
            break

    if not section_parent or not section_heading:
        return None

    # Count same-role nodes with ref under section_parent, before target
    idx = 0
    found = False
    for n in walk_tree(section_parent):
        if n is node or (n.ref and n.ref == node.ref):
            found = True
            break
        if n.role == node.role and n.ref:
            idx += 1

    if not found:
        return None

    heading_part = f'{section_heading.role}:"{_esc(section_heading.name)}"'
    value = f'section({heading_part}) > {node.role}[{idx}]'

    return Selector(
        strategy="relative_index",
        value=value,
        priority=2,
        unique=True,
    )


def _gen_relative_index_grouped(
    node: SnapshotNode, tree: SnapshotNode,
) -> list[Selector]:
    """Generate grouped relative_index selectors using repeating group detection.

    Walks up from target to find repeating containers (siblings with same role
    and similar child counts). Generates one selector per group level found.

    Two anchor modes:
      1. section(heading:"뉴스") > generic[0] > link[0]  — when heading found
      2. group(main > generic[0] > ...) > generic[0] > link[0]  — fallback

    Returns multiple selectors for _add_if_valid to filter.
    """
    if not node.role:
        return []

    ancestors = _get_ancestors(node, tree)
    if not ancestors:
        return []

    # ── Step 1: Find heading anchor (optional) ──
    section_heading = None
    section_parent = None
    for depth, anc in enumerate(ancestors):
        for child in anc.children:
            if child.role in _SECTION_HEADING_ROLES and child.name:
                section_heading = child
                section_parent = anc
                break
            if child.role in _LANDMARK_ROLES and child.name:
                section_heading = child
                section_parent = anc
                break
            for grandchild in child.children:
                if grandchild.role in _SECTION_HEADING_ROLES and grandchild.name:
                    section_heading = grandchild
                    section_parent = anc
                    break
                if grandchild.role in _LANDMARK_ROLES and grandchild.name:
                    section_heading = grandchild
                    section_parent = anc
                    break
            if section_heading:
                break
        if section_heading:
            break
        if depth >= 5:
            break

    # ── Step 2: Find repeating group levels ──
    group_levels: list[tuple[SnapshotNode, SnapshotNode, str, int]] = []

    for depth, anc in enumerate(ancestors):
        if anc is tree:
            break
        # If heading found, don't walk past section_parent
        if section_parent and anc is section_parent:
            break
        if depth > 8:
            break
        if depth + 1 >= len(ancestors):
            break
        container = ancestors[depth + 1]

        if not anc.role:
            continue

        same_role_siblings = [c for c in container.children if c.role == anc.role and c.ref]
        if len(same_role_siblings) < 2:
            continue

        child_counts = [len(c.children) for c in same_role_siblings]
        if not child_counts:
            continue
        median = sorted(child_counts)[len(child_counts) // 2]
        similar = sum(1 for c in child_counts if abs(c - median) <= 2)
        if similar / len(same_role_siblings) < 0.6:
            continue

        group_idx = 0
        for child in container.children:
            if child is anc or (child.ref and child.ref == anc.ref):
                break
            if child.role == anc.role and child.ref:
                group_idx += 1

        group_levels.append((anc, container, anc.role, group_idx))

    if not group_levels:
        return []

    # Build anchor prefix
    # Outermost container = group_levels[-1][1] (bottom-up, last = outermost)
    outermost_container = group_levels[-1][1]
    if section_heading:
        anchor = f'section({section_heading.role}:"{_esc(section_heading.name)}")'
    else:
        # Fallback: tree_path to outermost container
        container_path = _build_tree_path_index(outermost_container, tree)
        if not container_path:
            return []
        anchor = f"group({container_path})"

    # ── Step 3: Generate selectors for each grouping depth ──
    reversed_levels = group_levels[::-1]  # outermost first
    results: list[Selector] = []

    for level_count in range(1, len(reversed_levels) + 1):
        levels = reversed_levels[:level_count]

        innermost = levels[-1][0]
        local_idx = 0
        found = False
        for n in walk_tree(innermost):
            if n is node or (n.ref and n.ref == node.ref):
                found = True
                break
            if n.role == node.role and n.ref:
                local_idx += 1

        if not found:
            continue

        parts = [anchor]
        for _, _, grole, gidx in levels:
            parts.append(f"{grole}[{gidx}]")
        parts.append(f"{node.role}[{local_idx}]")

        value = " > ".join(parts)

        results.append(Selector(
            strategy="relative_index_grouped",
            value=value,
            priority=2,
            unique=True,
        ))

    return results


def _build_tree_path_index(target: SnapshotNode, tree: SnapshotNode) -> str | None:
    """Build a tree_path_index string for a node (for group anchor)."""
    ancestors = _get_ancestors(target, tree)
    if not ancestors:
        return None

    path_parts: list[str] = []
    has_meaningful = False
    for i, anc in enumerate(ancestors):
        if len(path_parts) >= 4 and has_meaningful:
            break
        if anc.role in _GENERIC_ROLES:
            if i + 1 < len(ancestors):
                grandparent = ancestors[i + 1]
                gen_idx = 0
                for child in grandparent.children:
                    if child is anc or (child.ref and child.ref == anc.ref):
                        break
                    if child.role == anc.role:
                        gen_idx += 1
                path_parts.append(f"{anc.role}[{gen_idx}]")
        else:
            has_meaningful = True
            if anc.name:
                path_parts.append(f'{anc.role}:"{_esc(anc.name)}"')
            else:
                path_parts.append(anc.role)

    if not path_parts or not has_meaningful:
        return None

    path_parts.reverse()
    return " > ".join(path_parts)


def _resolve_tree_path_to_node(tree: SnapshotNode, path_str: str) -> SnapshotNode | None:
    """Resolve a tree_path_index string to a node. Used for group(...) anchor."""
    segments = [s.strip() for s in path_str.split(" > ")]
    scope = tree
    for seg in segments:
        seg_m = re.match(r'^(\w+)(?:\[(\d+)\])?(?::"((?:[^"\\]|\\.)*)")?$', seg)
        if not seg_m:
            return None
        seg_role = seg_m.group(1)
        seg_idx = int(seg_m.group(2)) if seg_m.group(2) is not None else None
        seg_name = seg_m.group(3)

        found = None
        idx = 0
        for child in scope.children:
            if child.role != seg_role:
                continue
            if seg_name and child.name != seg_name:
                continue
            if seg_idx is not None:
                if idx == seg_idx:
                    found = child
                    break
                idx += 1
            else:
                found = child
                break
        if not found:
            # Try walking tree for non-direct descendants (landmark roles)
            for n in walk_tree(scope):
                if n.role == seg_role:
                    if seg_name and n.name != seg_name:
                        continue
                    found = n
                    break
        if not found:
            return None
        scope = found
    return scope


def _resolve_relative_index_grouped(
    tree: SnapshotNode, sel: Selector,
) -> SnapshotNode | None:
    """Resolve relative_index_grouped selector.

    Two anchor formats:
      section(heading:"뉴스") > generic[0] > link[0]  — heading anchor
      group(main > generic[0] > ...) > generic[0] > link[0]  — tree_path anchor

    Supports arbitrary depth of group segments.
    """
    parts = [p.strip() for p in sel.value.split(" > ")]
    if len(parts) < 3:
        return None

    # Parse target (last part)
    target_m = re.match(r'^(\w+)\[(\d+)\]$', parts[-1])
    if not target_m:
        return None
    target_role = target_m.group(1)
    target_idx = int(target_m.group(2))

    # ── Determine scope from anchor ──
    scope: SnapshotNode | None = None
    anchor = parts[0]
    group_parts = parts[1:-1]

    group_m = re.match(r'^group\((.+)\)$', anchor)
    section_m = re.match(r'^section\(([^)]+)\)$', anchor)

    if group_m:
        # tree_path anchor — walk the path to find the container directly
        path_str = group_m.group(1)
        scope = _resolve_tree_path_to_node(tree, path_str)
    elif section_m:
        # heading anchor — find heading, then walk up to a scope with repeating group
        heading_role, heading_name, _ = _parse_selector_value(section_m.group(1))
        if not heading_role or not heading_name:
            return None
        heading_node = find_in_tree(tree, heading_role, name=heading_name)
        if not heading_node:
            return None

        first_seg_m = re.match(r'^(\w+)\[(\d+)\]$', group_parts[0]) if group_parts else None
        if not first_seg_m:
            return None
        first_seg_role = first_seg_m.group(1)
        first_seg_idx = int(first_seg_m.group(2))

        for anc in _get_ancestors(heading_node, tree):
            for desc in walk_tree(anc):
                same_role = [c for c in desc.children if c.role == first_seg_role and c.ref]
                if len(same_role) < 2 or len(same_role) <= first_seg_idx:
                    continue
                child_counts = [len(c.children) for c in same_role]
                median = sorted(child_counts)[len(child_counts) // 2]
                similar = sum(1 for c in child_counts if abs(c - median) <= 2)
                if similar / len(same_role) >= 0.6:
                    scope = anc
                    break
            if scope:
                break

    if not scope:
        return None

    # Walk through group segments: each narrows scope.
    group_parts = parts[1:-1]
    for part in group_parts:
        seg_m = re.match(r'^(\w+)\[(\d+)\]$', part)
        if not seg_m:
            return None
        seg_role = seg_m.group(1)
        seg_idx = int(seg_m.group(2))

        # Find the nth node of seg_role that is a direct child of a
        # repeating container (same role ≥2, structurally similar).
        found_child = None
        idx = 0
        seen_parents: set[str] = set()
        for parent_node in walk_tree(scope):
            pid = parent_node.ref or id(parent_node)
            if pid in seen_parents:
                continue
            same_role_siblings = [
                c for c in parent_node.children
                if c.role == seg_role and c.ref
            ]
            if len(same_role_siblings) < 2:
                continue
            # Structural similarity check (must match generator)
            child_counts = [len(c.children) for c in same_role_siblings]
            median = sorted(child_counts)[len(child_counts) // 2]
            similar = sum(1 for c in child_counts if abs(c - median) <= 2)
            if similar / len(same_role_siblings) < 0.6:
                continue
            seen_parents.add(pid)
            # This parent is a valid repeating container
            for child in parent_node.children:
                if child.role == seg_role and child.ref:
                    if idx == seg_idx:
                        found_child = child
                        break
                    idx += 1
            if found_child:
                break
        if not found_child:
            return None
        scope = found_child

    # Final part: target_role[idx] within narrowed scope
    idx = 0
    for n in walk_tree(scope):
        if n.role == target_role and n.ref:
            if idx == target_idx:
                return n
            idx += 1

    return None


# ── Resolution: find node from SelectorSet ───────────────────────


def resolve_selector(
    tree: SnapshotNode,
    selector_set: SelectorSet,
) -> SnapshotNode | None:
    """Resolve a SelectorSet to a SnapshotNode in the tree.

    Tries each selector in priority order. Returns first successful match.
    """
    sorted_sels = sorted(selector_set.selectors, key=lambda s: s.priority)

    for sel in sorted_sels:
        node = _try_resolve(tree, sel)
        if node:
            return node

    return None


def resolve_selector_from_spec(
    tree: SnapshotNode,
    spec: dict[str, Any],
) -> SnapshotNode | None:
    """Resolve an element from a YAML spec dict.

    Supports both:
    - SelectorSet format: { selectors: [...] }
    - Shorthand format: { role: "button", name: "보내기" }

    Fuzzy matching is handled by resolve_selector's _collect_matches.
    """
    selector_set = spec_to_selector_set(spec)
    return resolve_selector(tree, selector_set)


def resolve_in_flat(
    nodes: list[SnapshotNode],
    spec: dict[str, Any],
) -> SnapshotNode | None:
    """Resolve an element spec against a flat node list.

    Wraps nodes in a temporary root so resolve_selector_from_spec works.
    For role-only specs (no name), does direct role matching within the
    flat list — this is safe because the scope is limited to one item's children.
    """
    # Role-only spec: match first node with this role in flat list
    if "role" in spec and "name" not in spec and "name_contains" not in spec and "selectors" not in spec:
        role = spec["role"]
        for n in nodes:
            if n.role == role:
                return n
        return None

    root = SnapshotNode(role="root", children=list(nodes))
    return resolve_selector_from_spec(root, spec)


def spec_to_display(spec: dict[str, Any]) -> tuple[str, str]:
    """Extract display (role, name) from a YAML element spec.

    Works with both shorthand { role, name } and full { selectors: [...] }.
    Used for building LLM prompts where human-readable info is needed.
    """
    if "role" in spec:
        return spec.get("role", ""), spec.get("name", "")
    for sel in spec.get("selectors", []):
        role, name, _ = _parse_selector_value(sel.get("value", ""))
        if role:
            return role, name or ""
    return "", ""


def spec_to_selector_set(spec: dict[str, Any]) -> SelectorSet:
    """Convert a YAML element spec to SelectorSet.

    Handles both formats:
    - Full: { selectors: [{ strategy, value, ... }, ...] }
    - Shorthand: { role, name? }
    """
    if "selectors" in spec:
        selectors = [
            Selector(
                strategy=s.get("strategy", "role_name"),
                value=s.get("value", ""),
                priority=s.get("priority", 1),
                unique=s.get("unique", True),
                ordinal=s.get("ordinal", 0),
                match_count=s.get("match_count", 1),
                context_text=s.get("context_text", ""),
            )
            for s in spec["selectors"]
        ]
        return SelectorSet(selectors=selectors)

    # Shorthand: { role, name } or { role, name_contains }
    role = spec.get("role", "")
    name = spec.get("name")
    name_contains = spec.get("name_contains")

    if not role:
        return SelectorSet()

    if name:
        value = f'{role}:"{_esc(name)}"'
    elif name_contains:
        # Partial match: use ~"text" syntax to signal substring matching
        value = f'{role}:~"{_esc(name_contains)}"'
    else:
        value = role

    return SelectorSet(selectors=[
        Selector(strategy="role_name", value=value, priority=1),
    ])


# ── Internal: resolve strategies ─────────────────────────────────


def _try_resolve(tree: SnapshotNode, sel: Selector) -> SnapshotNode | None:
    """Try a single selector strategy."""
    if sel.strategy == "role_name":
        return _resolve_role_name(tree, sel)
    elif sel.strategy == "content":
        return _resolve_content(tree, sel)
    elif sel.strategy == "tree_path":
        return _resolve_tree_path(tree, sel)
    elif sel.strategy == "tree_path_index":
        return _resolve_tree_path_index(tree, sel)
    elif sel.strategy == "relative":
        return _resolve_relative(tree, sel)
    elif sel.strategy == "relative_index":
        return _resolve_relative_index(tree, sel)
    elif sel.strategy == "relative_index_grouped":
        return _resolve_relative_index_grouped(tree, sel)
    return None


def _resolve_role_name(tree: SnapshotNode, sel: Selector) -> SnapshotNode | None:
    """Resolve role_name selector. Exact match → compat role → partial."""
    role, name, partial = _parse_selector_value(sel.value)
    if not role:
        return None

    # name_contains: go straight to substring matching
    if partial and name:
        matches = _collect_contains(tree, role, name)
        if matches:
            idx = min(sel.ordinal, len(matches) - 1)
            return matches[idx]
        return None

    # Exact match
    matches = _collect_matches(tree, role, name)

    # Compat role fallback
    if not matches:
        compat = _ROLE_COMPAT.get(role)
        if compat:
            for alt_role in compat:
                if alt_role != role:
                    matches = _collect_matches(tree, alt_role, name)
                    if matches:
                        break

    if not matches:
        return None

    # Pick by ordinal
    idx = min(sel.ordinal, len(matches) - 1)
    return matches[idx]


def _resolve_content(tree: SnapshotNode, sel: Selector) -> SnapshotNode | None:
    """Resolve content selector using sibling text disambiguation."""
    role, name, _ = _parse_selector_value(sel.value)
    if not role or not sel.context_text:
        return None

    matches = _collect_matches(tree, role, name)
    if not matches:
        return None

    ct_lower = sel.context_text.lower()
    for match in matches:
        sib_text = _find_sibling_text(match, tree)
        if sib_text and ct_lower in sib_text.lower():
            return match

    # Fallback to ordinal
    idx = min(sel.ordinal, len(matches) - 1)
    return matches[idx]


def _resolve_tree_path(tree: SnapshotNode, sel: Selector) -> SnapshotNode | None:
    """Resolve tree_path selector by walking ancestor chain."""
    parts = [p.strip() for p in sel.value.split(" > ")]
    if not parts:
        return None

    # Parse leaf
    leaf_role, leaf_name, _ = _parse_selector_value(parts[-1])
    if not leaf_role:
        return None

    # Parse ancestors (everything before leaf)
    ancestor_specs = [_parse_selector_value(p)[:2] for p in parts[:-1]]

    # Find all leaf matches
    candidates = _collect_matches(tree, leaf_role, leaf_name)
    if not candidates:
        return None

    # Filter: candidate must have matching ancestors in order
    for candidate in candidates:
        if _has_ancestor_chain(candidate, ancestor_specs, tree):
            return candidate

    return None


def _resolve_tree_path_index(tree: SnapshotNode, sel: Selector) -> SnapshotNode | None:
    """Resolve tree_path_index selector by walking the indexed path.

    Format: 'ancestor > ... > parent_role[N] > target_role[M]'
    Each segment with [N] is resolved by finding the Nth child of that role
    under the current scope. Named segments (role:"name") are resolved normally.

    Example: 'main > generic[5] > link[0]'
    → find main → find 6th generic child → find 1st link child
    """
    parts = [p.strip() for p in sel.value.split(" > ")]
    if not parts:
        return None

    # Start from tree root
    scope = tree

    for part in parts:
        # Parse: role[index] or role:"name" or role
        idx_match = re.match(r'(\w+)\[(\d+)\]$', part)
        if idx_match:
            target_role = idx_match.group(1)
            target_idx = int(idx_match.group(2))
            # Find Nth child with this role under current scope
            found = None
            count = 0
            for child in scope.children:
                if child.role == target_role:
                    if count == target_idx:
                        found = child
                        break
                    count += 1
            if not found:
                return None
            scope = found
        else:
            role, name, _ = _parse_selector_value(part)
            if not role:
                return None
            # Find named/unnamed node in scope's children or subtree
            found = None
            for child in scope.children:
                if child.role == role:
                    if name is None or child.name == name:
                        found = child
                        break
            # Fallback: search subtree
            if not found:
                found = find_in_tree(scope, role, name=name)
            if not found:
                return None
            scope = found

    # scope is now the resolved node
    return scope if scope.ref else None


def _resolve_relative(tree: SnapshotNode, sel: Selector) -> SnapshotNode | None:
    """Resolve relative selector using landmark anchor."""
    # Parse: near(landmark_role:"name") > target_role:"name"
    m = re.match(r'near\(([^)]+)\)\s*>\s*(.+)', sel.value)
    if not m:
        return None

    landmark_part, target_part = m.group(1), m.group(2)
    landmark_role, landmark_name, _ = _parse_selector_value(landmark_part)
    target_role, target_name, _ = _parse_selector_value(target_part)

    if not landmark_role or not target_role:
        return None

    # Find the landmark
    landmark = find_in_tree(tree, landmark_role, name=landmark_name)
    if not landmark:
        return None

    # Find target within or near the landmark
    # First: try inside landmark subtree
    for node in walk_tree(landmark):
        if node.role == target_role:
            if target_name and node.name != target_name:
                continue
            return node

    # Fallback: find target anywhere (landmark just confirms context)
    return find_in_tree(tree, target_role, name=target_name)


def _resolve_relative_index(tree: SnapshotNode, sel: Selector) -> SnapshotNode | None:
    """Resolve relative_index selector: section heading + positional index.

    Format: 'section(heading:"뉴스") > link[0]'
    → find the section containing heading "뉴스", then find the Nth link in it.
    """
    m = re.match(r'section\(([^)]+)\)\s*>\s*(\w+)\[(\d+)\]$', sel.value)
    if not m:
        return None

    heading_part = m.group(1)
    target_role = m.group(2)
    target_idx = int(m.group(3))

    heading_role, heading_name, _ = _parse_selector_value(heading_part)
    if not heading_role or not heading_name:
        return None

    # Find the heading node
    heading_node = find_in_tree(tree, heading_role, name=heading_name)
    if not heading_node:
        return None

    # Find the section scope: walk up from heading until we find an ancestor
    # that contains enough target_role nodes (same logic as generation)
    section = None
    for anc in _get_ancestors(heading_node, tree):
        count = 0
        for n in walk_tree(anc):
            if n.role == target_role and n.ref:
                count += 1
        if count > target_idx:
            section = anc
            break

    if not section:
        return None

    # Count same-role nodes under section to find the indexed one
    idx = 0
    for n in walk_tree(section):
        if n.role == target_role and n.ref:
            if idx == target_idx:
                return n
            idx += 1

    return None

    return None


def _find_section_parent(heading: SnapshotNode, tree: SnapshotNode) -> SnapshotNode | None:
    """Find the section scope that contains this heading.

    Walks up from heading's immediate parent. The section is the first
    ancestor that has more than just the heading subtree — i.e., it also
    contains sibling content nodes (the actual section body).

    For structure like:
      generic (A)           ← this is the section
        generic (B)
          heading "뉴스"
        generic (C)
          link "기사..."    ← content is here

    heading's parent is (B), but the section is (A) which contains both.
    """
    ancestors = _get_ancestors(heading, tree)
    if not ancestors:
        return None

    # Walk up: find the first ancestor with multiple meaningful children
    # (not just the heading's branch)
    for anc in ancestors:
        if len(anc.children) > 1:
            return anc

    return ancestors[-1] if ancestors else None


# ── Internal: tree utilities ─────────────────────────────────────


def _parse_selector_value(value: str) -> tuple[str, str | None, bool]:
    """Parse 'role:"name"', 'role:~"partial"', or 'role' into (role, name, partial).

    Returns (role, name, partial) where:
    - name is None for role-only selectors
    - partial is True for name_contains (~"text") selectors
    """
    value = value.strip()

    # role:~"partial" (name_contains)
    m = re.match(r'(\w+):\s*~"((?:[^"\\]|\\.)*)"', value)
    if m:
        return m.group(1), m.group(2), True

    # role:"name"
    m = re.match(r'(\w+):\s*"((?:[^"\\]|\\.)*)"', value)
    if m:
        return m.group(1), m.group(2), False

    # role only
    m = re.match(r'(\w+)$', value)
    if m:
        return m.group(1), None, False

    return "", None, False


def _collect_matches(
    tree: SnapshotNode,
    role: str,
    name: str | None,
) -> list[SnapshotNode]:
    """Collect all nodes matching role + name (with fuzzy fallback)."""
    # Exact match
    results: list[SnapshotNode] = []
    for node in walk_tree(tree):
        if node.role != role or not node.ref:
            continue
        if name is None:
            if not node.name:
                results.append(node)
        elif name and node.name:
            if node.name == name:
                results.append(node)

    if results:
        return results

    # Fuzzy: partial match (name substring)
    if name:
        for node in walk_tree(tree):
            if node.role != role or not node.ref:
                continue
            if node.name and (name in node.name or node.name in name):
                results.append(node)

    if results:
        return results

    # Fuzzy: token overlap (handles dynamic content like prices, timestamps)
    # "logo KCC 002380 543,000원 +1.68%" vs "logo KCC 002380 545,000원 +2.05%"
    # → 3/5 tokens match → same element
    if name and len(name) > 10:
        name_tokens = set(name.split())
        if len(name_tokens) >= 3:
            for node in walk_tree(tree):
                if node.role != role or not node.ref or not node.name:
                    continue
                node_tokens = set(node.name.split())
                if not node_tokens:
                    continue
                overlap = len(name_tokens & node_tokens)
                threshold = max(2, len(name_tokens) * 0.5)
                if overlap >= threshold:
                    results.append(node)

    return results


def _collect_contains(
    tree: SnapshotNode,
    role: str,
    substring: str,
) -> list[SnapshotNode]:
    """Collect all nodes matching role where name contains substring."""
    results: list[SnapshotNode] = []
    for node in walk_tree(tree):
        if node.role != role or not node.ref:
            continue
        if node.name and substring in node.name:
            results.append(node)
    return results


def _get_ancestors(
    target: SnapshotNode,
    tree: SnapshotNode,
) -> list[SnapshotNode]:
    """Get ancestor chain from tree root to target (excluding root and target).

    Returns ancestors in bottom-up order (immediate parent first).
    """
    path: list[SnapshotNode] = []

    def _find(node: SnapshotNode) -> bool:
        if node is target or (node.ref and node.ref == target.ref):
            return True
        for child in node.children:
            if _find(child):
                path.append(node)
                return True
        return False

    _find(tree)
    # path is now [parent, grandparent, ...] — already bottom-up
    # Remove root node
    if path and path[-1].role == "root":
        path.pop()
    return path


def _find_sibling_text(
    node: SnapshotNode,
    tree: SnapshotNode,
) -> str:
    """Find distinguishing text from sibling nodes.

    Searches:
    1. Direct siblings (same parent)
    2. Children of siblings (one level deeper)
    """
    ancestors = _get_ancestors(node, tree)
    if not ancestors:
        return ""

    parent = ancestors[0]

    # Direct sibling text
    for sibling in parent.children:
        if sibling is node:
            continue
        if sibling.name and len(sibling.name) > 2:
            return sibling.name
        # Children of sibling
        for child in sibling.children:
            if child.name and len(child.name) > 2:
                return child.name

    return ""


def _has_ancestor_chain(
    node: SnapshotNode,
    ancestor_specs: list[tuple[str, str | None]],
    tree: SnapshotNode,
) -> bool:
    """Check if node has the expected ancestors in order (bottom-up)."""
    if not ancestor_specs:
        return True

    ancestors = _get_ancestors(node, tree)
    # ancestor_specs is top-down, ancestors is bottom-up → reverse ancestors
    ancestors_top_down = list(reversed(ancestors))

    spec_idx = 0
    for anc in ancestors_top_down:
        if spec_idx >= len(ancestor_specs):
            break
        expected_role, expected_name = ancestor_specs[spec_idx]
        if anc.role == expected_role:
            if expected_name is None or anc.name == expected_name:
                spec_idx += 1

    return spec_idx >= len(ancestor_specs)


def _find_closest_landmark(
    node: SnapshotNode,
    landmarks: list[SnapshotNode],
    tree: SnapshotNode,
) -> SnapshotNode | None:
    """Find the landmark that is an ancestor of node."""
    ancestors = _get_ancestors(node, tree)
    ancestor_refs = {a.ref for a in ancestors if a.ref}

    for lm in landmarks:
        if lm.ref in ancestor_refs:
            return lm

    return None


def _verify_tree_path(tree: SnapshotNode, parts: list[str]) -> bool:
    """Verify that a tree path resolves to exactly one node."""
    if not parts:
        return False

    leaf_role, leaf_name, _ = _parse_selector_value(parts[-1])
    ancestor_specs = [_parse_selector_value(p)[:2] for p in parts[:-1]]

    candidates = _collect_matches(tree, leaf_role, leaf_name)
    matched = [c for c in candidates if _has_ancestor_chain(c, ancestor_specs, tree)]

    return len(matched) == 1
