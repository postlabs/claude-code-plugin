"""Selector Validator — code-based action evaluation for the Action Creator plugin.

Validates each selector strategy independently against a live browser snapshot,
compares ref IDs (extract_text) or match counts (extract_list),
and runs full replay_action() for execution test.

Usage:
    python selector_validator.py --cdp-port 9222 --action actions/get_related_keywords.yaml [--params '{"keyword":"노트북"}']

Output: writes {action_name}.eval.yaml to --out-dir (default: same directory as action file).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# Add vendor to path
_VENDOR_DIR = str(Path(__file__).resolve().parent.parent / "vendor")
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vendor.models import SnapshotNode, ActionResult
from vendor.selector import (
    Selector,
    SelectorSet,
    resolve_selector,
    spec_to_selector_set,
    _collect_matches,
    _collect_contains,
    _parse_selector_value,
)
from vendor.snapshot_tree import parse_snapshot_tree, walk_tree
from vendor.action_replay import replay_action
from vendor.template import resolve_templates, resolve_deep


# ── Browser connection ──
# Uses Playwright MCP via npx to connect to a running Chrome instance.
# This avoids depending on the backend's BrowserHandle.


class _SimpleBrowser:
    """Minimal browser wrapper using Playwright MCP stdio adapter."""

    def __init__(self, adapter: Any):
        self._adapter = adapter
        self._session = type('_shim', (), {'adapter': adapter})()
        self._tree: SnapshotNode = SnapshotNode(role="root")
        self._raw_snapshot: str = ""

    def _extract_text(self, result: Any) -> str:
        if result and hasattr(result, "content") and result.content:
            return result.content[0].text or ""
        return ""

    async def snapshot(self) -> SnapshotNode:
        result = await self._adapter.call_tool("browser_snapshot", {})
        self._raw_snapshot = self._extract_text(result)
        self._tree, _ = parse_snapshot_tree(self._raw_snapshot)
        return self._tree

    async def navigate(self, url: str) -> None:
        await self._adapter.call_tool("browser_navigate", {"url": url})

    async def click(self, node: SnapshotNode) -> None:
        await self._adapter.call_tool("browser_click", {"element": node.name, "ref": node.ref})

    async def fill(self, node: SnapshotNode, value: str) -> None:
        await self._adapter.call_tool("browser_fill_form", {"ref": node.ref, "value": value})

    async def press(self, key: str) -> None:
        await self._adapter.call_tool("browser_press_key", {"key": key})

    async def select_option(self, node: SnapshotNode, values: list[str]) -> None:
        await self._adapter.call_tool("browser_select_option", {"ref": node.ref, "values": values})

    async def navigate_back(self) -> None:
        await self._adapter.call_tool("browser_navigate_back", {})

    async def handle_dialog(self, accept: bool = True, prompt_text: str | None = None) -> None:
        tool = "browser_handle_dialog"
        params: dict[str, Any] = {"accept": accept}
        if prompt_text:
            params["promptText"] = prompt_text
        await self._adapter.call_tool(tool, params)

    async def evaluate(self, expression: str) -> str:
        result = await self._adapter.call_tool("browser_evaluate", {"expression": expression})
        return self._extract_text(result)

    async def scroll(self, direction: str = "down", distance: int = 0, steps: int = 1, x: int = 0, y: int = 0) -> None:
        if direction or distance:
            dy = distance if direction == "down" else -distance if direction == "up" else 0
            dx = distance if direction == "right" else -distance if direction == "left" else 0
        else:
            dx, dy = x, y
        await self._adapter.call_tool("browser_evaluate", {
            "function": f"() => window.scrollBy({dx}, {dy})"
        })

    async def wait_for_stable(self, max_checks: int = 10, interval: float = 1.0) -> None:
        """Wait until DOM element count stabilizes (page fully rendered)."""
        prev = 0
        for _ in range(max_checks):
            await asyncio.sleep(interval)
            try:
                text = await self.evaluate("document.querySelectorAll('*').length")
                curr = int(text.strip())
            except Exception:
                continue
            if curr == prev and curr > 50:
                return
            prev = curr

    async def close_tab(self) -> None:
        pass  # Not needed for validation


# ── Strategy-level validation ──


def _count_tree_matches(tree: SnapshotNode, sel: Selector) -> int:
    """Count how many nodes in the tree match a single selector strategy."""
    if sel.strategy in ("role_name", "content"):
        role, name, partial = _parse_selector_value(sel.value)
        if not role:
            return 0
        if partial and name:
            return len(_collect_contains(tree, role, name))
        return len(_collect_matches(tree, role, name))

    if sel.strategy in ("tree_path", "tree_path_index"):
        single = SelectorSet(selectors=[sel])
        node = resolve_selector(tree, single)
        return 1 if node else 0

    if sel.strategy in ("relative", "relative_index", "relative_index_grouped", "landmark_descendant"):
        single = SelectorSet(selectors=[sel])
        node = resolve_selector(tree, single)
        return 1 if node else 0

    # Unknown strategy (e.g., css) — can't count in tree
    return -1


async def _count_css_matches(browser: _SimpleBrowser, css_value: str) -> int:
    """Count matching elements for a CSS selector using browser's DOM."""
    try:
        js = f"document.querySelectorAll({json.dumps(css_value)}).length"
        text = await browser.evaluate(js)
        return int(text.strip())
    except Exception:
        return -1


def validate_selectors_against_tree(
    tree: SnapshotNode,
    selector_spec: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate each selector strategy independently against the snapshot tree."""
    selector_set = spec_to_selector_set(selector_spec)
    results: list[dict[str, Any]] = []

    for sel in selector_set.selectors:
        entry: dict[str, Any] = {
            "strategy": sel.strategy,
            "value": sel.value,
            "priority": sel.priority,
        }
        if sel.context_text:
            entry["context_text"] = sel.context_text

        if sel.strategy == "css":
            entry["status"] = "SKIP_TREE"
            entry["ref"] = None
            entry["name"] = None
            entry["role"] = None
            entry["match_count"] = -1  # filled later by browser
        else:
            single = SelectorSet(selectors=[sel])
            node = resolve_selector(tree, single)
            match_count = _count_tree_matches(tree, sel)

            if node:
                entry["status"] = "MATCH"
                entry["ref"] = node.ref
                entry["name"] = node.name[:80] if node.name else ""
                entry["role"] = node.role
                entry["match_count"] = match_count
            else:
                entry["status"] = "NO_MATCH"
                entry["ref"] = None
                entry["name"] = None
                entry["role"] = None
                entry["match_count"] = match_count

        results.append(entry)

    return results


def check_consistency(
    strategy_results: list[dict[str, Any]],
    step_action: str,
    step_limit: int | None = None,
) -> dict[str, Any]:
    """Check consistency across strategies."""
    matched = [r for r in strategy_results if r["status"] == "MATCH"]
    base: dict[str, Any] = {
        "matched_count": len(matched),
        "total_count": len(strategy_results),
    }

    if step_action == "extract_list":
        counts: dict[int, list[str]] = {}
        for r in strategy_results:
            mc = r.get("match_count", -1)
            if mc < 0:
                continue
            label = f"{r['strategy']}(p{r['priority']})"
            counts.setdefault(mc, []).append(label)

        base["consistent"] = len(counts) <= 1
        base["match_counts"] = {str(k): v for k, v in counts.items()}

        if step_limit and counts:
            max_count = max(counts.keys())
            if max_count > step_limit * 2:
                base["consistent"] = False
                base["scope_warning"] = (
                    f"Strategy matches {max_count} elements but limit is {step_limit}. "
                    f"Selector may be unscoped."
                )
        return base

    # Default: ref comparison
    if len(matched) <= 1:
        base["consistent"] = True
        return base

    refs: dict[str, list[str]] = {}
    for r in matched:
        ref = r["ref"] or "none"
        refs.setdefault(ref, []).append(f"{r['strategy']}(p{r['priority']})")

    base["consistent"] = len(refs) == 1
    base["refs"] = refs
    return base


# ── Step-by-step validation ──


async def validate_action(
    browser: _SimpleBrowser,
    action_def: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Validate each step's selectors."""
    steps = action_def.get("steps", [])
    step_results: list[dict[str, Any]] = []

    for i, step in enumerate(steps):
        action = step.get("action", "")
        step_limit = step.get("limit")
        step_entry: dict[str, Any] = {"step": i + 1, "action": action}

        selector_spec = step.get("selector")
        if selector_spec and params:
            selector_spec = _resolve_templates(selector_spec, params)

        if selector_spec:
            tree = await browser.snapshot()
            strategies = validate_selectors_against_tree(tree, selector_spec)

            # Fill CSS match counts via browser DOM
            for s in strategies:
                if s["strategy"] == "css":
                    css_count = await _count_css_matches(browser, s["value"])
                    s["match_count"] = css_count
                    if css_count > 0:
                        s["status"] = "MATCH"
                    elif css_count == 0:
                        s["status"] = "NO_MATCH"

            consistency = check_consistency(strategies, action, step_limit)

            step_entry["selector_validation"] = {
                "strategies": strategies,
                "consistency": consistency,
            }

            resolvable = [s for s in strategies if s["status"] != "SKIP_TREE"]
            any_match = any(s["status"] == "MATCH" for s in strategies)
            all_resolvable_match = all(s["status"] == "MATCH" for s in resolvable) if resolvable else False

            if not any_match:
                step_entry["status"] = "FAIL"
                step_entry["error"] = "No selector strategy matched"
            elif not consistency["consistent"]:
                if "scope_warning" in consistency:
                    step_entry["status"] = "FAIL"
                    step_entry["error"] = consistency["scope_warning"]
                elif "refs" in consistency:
                    step_entry["status"] = "WARN"
                    step_entry["error"] = f"Strategies point to different refs: {consistency['refs']}"
                else:
                    step_entry["status"] = "WARN"
                    step_entry["error"] = f"Match count mismatch: {consistency.get('match_counts', {})}"
            elif not all_resolvable_match:
                failed = [
                    f"{s['strategy']}(p{s['priority']})"
                    for s in resolvable if s["status"] == "NO_MATCH"
                ]
                step_entry["status"] = "WARN"
                step_entry["error"] = f"Fallback strategies broken: {', '.join(failed)}"
            else:
                step_entry["status"] = "PASS"
        else:
            step_entry["status"] = "PASS"

        step_results.append(step_entry)

    return {"step_results": step_results}


# ── Full replay ──


async def run_full_replay(
    browser: _SimpleBrowser,
    action_def: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Run replay_action() and return structured result."""
    result = await replay_action(browser, action_def, params=params)
    output: dict[str, Any] = {"success": result.success}
    if result.error:
        output["error"] = result.error
    if result.data:
        if isinstance(result.data, list):
            output["extracted_count"] = len(result.data)
            output["extracted_sample"] = result.data[:3] if len(result.data) > 3 else result.data
        else:
            output["extracted"] = str(result.data)[:200]
    return output


# ── Utilities ──


def _resolve_templates(spec: Any, params: dict[str, Any]) -> Any:
    return resolve_deep(spec, params)


def build_test_params(action_def: dict[str, Any]) -> dict[str, Any]:
    params_def = action_def.get("params") or {}
    verified_with = action_def.get("verified_with") or {}
    test_params: dict[str, Any] = {}
    for pname, pdef in params_def.items():
        if pname in verified_with:
            test_params[pname] = str(verified_with[pname])
        elif isinstance(pdef, dict) and pdef.get("default") is not None:
            test_params[pname] = str(pdef["default"])
        else:
            test_params[pname] = "test"
    return test_params


# ── Main ──


async def validate_action_file(
    cdp_port: int,
    action_file: Path,
    params_override: dict[str, Any] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Full validation pipeline for a single action YAML file."""
    # Lazy import MCP adapter (requires openai-agents package)
    from agents.mcp import MCPServerStdio, MCPServerStdioParams

    with open(action_file, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if not raw:
        return {"error": "Empty action file"}

    action_name = next(iter(raw))
    action_def = raw[action_name]
    params = params_override or build_test_params(action_def)

    # Connect browser via MCP
    adapter = MCPServerStdio(
        params=MCPServerStdioParams(
            command="npx",
            args=["@playwright/mcp", "--cdp-endpoint", f"http://127.0.0.1:{cdp_port}"],
        )
    )
    await adapter.connect()
    browser = _SimpleBrowser(adapter)

    try:
        # Navigate to entry URL
        url = action_def.get("url", "")
        if url and params:
            url = resolve_templates(url, params)

        if url:
            await browser.navigate(url)
            await browser.wait_for_stable()

        # Step-by-step selector validation
        step_validation = await validate_action(browser, action_def, params)

        # Full replay (navigate again for clean state)
        if url:
            await browser.navigate(url)
            await browser.wait_for_stable()

        replay_result = await run_full_replay(browser, action_def, params)

        # Build result
        result: dict[str, Any] = {
            "action": action_name,
            "validated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "params_used": params,
            "selector_validation": step_validation["step_results"],
            "replay_result": replay_result,
        }

        step_statuses = [s["status"] for s in step_validation["step_results"]]
        has_fail = "FAIL" in step_statuses
        has_warn = "WARN" in step_statuses
        replay_ok = replay_result["success"]

        if has_fail or not replay_ok:
            result["status"] = "FAIL"
        elif has_warn:
            result["status"] = "WARN"
        else:
            result["status"] = "PASS"

        # Write output
        if out_dir is None:
            out_dir = action_file.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{action_name}.eval.yaml"
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(result, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        print(f"[{action_name}] {result['status']} -> {out_path}")
        return result

    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass


async def run_main() -> None:
    parser = argparse.ArgumentParser(description="Selector Validator")
    parser.add_argument("--cdp-port", type=int, default=9222)
    parser.add_argument("--action", type=Path, required=True)
    parser.add_argument("--params", type=str, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    params_override = json.loads(args.params) if args.params else None
    await validate_action_file(args.cdp_port, args.action, params_override, args.out_dir)


if __name__ == "__main__":
    asyncio.run(run_main())
