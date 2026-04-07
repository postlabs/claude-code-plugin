"""Vendored from: src/backend/app/services/webflow/execution/action_replay.py

Action replay engine for Site Agent.
NOTE: 원본 수정 시 이 vendor 복사본도 동기화 필요.
"""

from __future__ import annotations

import json
from typing import Any

from .models import ActionResult, SnapshotNode
from .selector import resolve_selector_from_spec, spec_to_selector_set


async def replay_action(
    browser: Any,
    action_def: dict[str, Any],
    params: dict[str, Any],
    on_step: Any = None,
) -> ActionResult:
    """Replay a stored action definition.

    Args:
        browser: BrowserHandle instance
        action_def: Action definition with steps and params
        params: Runtime parameter values (e.g. {"query": "alice"})

    Returns:
        ActionResult with success/error status and compressed snapshot.
    """
    steps = action_def.get("steps", [])
    if not steps:
        return ActionResult(success=False, error="action에 steps가 없습니다.")

    extracted_results: list[Any] = []

    from .logger_stub import logger as _logger

    _logger.info("[replay] starting", steps=len(steps),
                 actions=[s.get("action") for s in steps])

    for i, step in enumerate(steps):
        action = step.get("action", "")
        _logger.info("[replay] step", index=i+1, total=len(steps), action=action)

        if on_step:
            await on_step(i, len(steps), action)

        try:
            if action == "click":
                error = await _replay_click(browser, step, params, i)
                if error:
                    return error

            elif action == "fill":
                error = await _replay_fill(browser, step, params, i)
                if error:
                    return error

            elif action == "navigate":
                error = await _replay_navigate(browser, step, params, i)
                if error:
                    return error

            elif action == "extract_list":
                result = await _replay_extract_list(browser, step, params, i)
                if isinstance(result, ActionResult) and not result.success:
                    return result
                extracted_results.append(result)

            elif action == "extract_text":
                result = await _replay_extract_text(browser, step, params, i)
                if isinstance(result, ActionResult) and not result.success:
                    return result
                extracted_results.append(result)

            elif action == "press":
                error = await _replay_press(browser, step, i)
                if error:
                    return error

            elif action == "scroll":
                await _replay_scroll(browser, step)

            elif action == "close_tab":
                await _replay_close_tab(browser, step)

            elif action == "navigate_back":
                await browser.navigate_back()

            elif action == "handle_dialog":
                accept = step.get("accept", True)
                prompt_text = step.get("prompt_text")
                await browser.handle_dialog(accept=accept, prompt_text=prompt_text)

            elif action == "select":
                error = await _replay_select(browser, step, params, i)
                if error:
                    return error

            elif action == "wait":
                await _replay_wait(browser, step, params, i)

            elif action == "select_custom":
                error = await _replay_select_custom(browser, step, params, i)
                if error:
                    return error

            elif action == "evaluate":
                result = await _replay_evaluate(browser, step, params, i)
                if isinstance(result, ActionResult) and not result.success:
                    return result
                if result is not None and not isinstance(result, ActionResult):
                    extracted_results.append(result)

            else:
                return ActionResult(
                    success=False,
                    error=f"step {i + 1}: 알 수 없는 action '{action}'",
                )

        except Exception as e:
            return ActionResult(
                success=False,
                error=f"step {i + 1}/{len(steps)} 실행 실패: {e}",
            )

    # Return extracted data if available, otherwise success with no data
    if extracted_results:
        # Single extract → return directly; multiple → return list
        data = extracted_results[0] if len(extracted_results) == 1 else extracted_results
        return ActionResult(success=True, data=data)
    return ActionResult(success=True)


async def _replay_click(
    browser: Any,
    step: dict[str, Any],
    params: dict[str, Any],
    step_idx: int,
) -> ActionResult | None:
    """Resolve selector and click.

    After clicking, checks if a new tab was opened. If so, switches to
    the new tab so subsequent actions run in the correct context.
    """
    import asyncio
    from .logger_stub import logger

    tabs_before = await _get_tab_list(browser)

    node = await _resolve_step_element(browser, step, step_idx, params=params)
    if isinstance(node, ActionResult):
        return node
    await browser.click(node)

    # Wait for potential popup tab to register (extension 500ms + relay)
    await asyncio.sleep(1)
    tabs_after = await _get_tab_list(browser)

    before_urls = {url for _, url in tabs_before}
    new_tabs = [(idx, url) for idx, url in tabs_after if url not in before_urls]
    if new_tabs:
        new_idx, new_url = new_tabs[-1]
        await browser._session.adapter.call_tool(
            "browser_tabs", {"action": "select", "index": new_idx},
        )
        logger.info("[replay] switched to new tab", index=new_idx, url=new_url[:80])

    return None


async def _replay_fill(
    browser: Any,
    step: dict[str, Any],
    params: dict[str, Any],
    step_idx: int,
) -> ActionResult | None:
    """Resolve selector, resolve param value, and fill."""
    node = await _resolve_step_element(browser, step, step_idx)
    if isinstance(node, ActionResult):
        return node

    value = _resolve_param(step.get("value", ""), params)
    if value is None:
        param_name = step.get("value", "")[1:]  # strip $
        return ActionResult(
            success=False,
            error=f"step {step_idx + 1}: 파라미터 '{param_name}' 값이 제공되지 않았습니다.",
        )

    await browser.fill(node, str(value))
    return None


async def _replay_extract_list(
    browser: Any,
    step: dict[str, Any],
    params: dict[str, Any],
    step_idx: int,
) -> Any:
    """Extract structured list data from an element."""
    from .snapshot_tree import walk_tree
    from .generic_tools import _collect_text

    node = await _resolve_step_element(browser, step, step_idx, params=params)
    if isinstance(node, ActionResult):
        return node

    # Lightweight extract_list: flatten children and collect named fields.
    # Does not depend on core.discovery (detect_repeating_groups / score_and_rank)
    # which is unavailable in the vendored subset.
    items = [c for c in node.children if c.role and c.ref]
    rows = []
    for item in items:
        row: dict[str, Any] = {}
        if item.name:
            row["name"] = item.name
        for child in walk_tree(item):
            if child is item:
                continue
            if child.name:
                key = f"{child.role}_{child.ref}" if child.ref else child.role
                row[key] = child.name
        if not row and item.name:
            row["text"] = _collect_text(item)
        if row:
            rows.append(row)

    # Apply limit
    limit = None
    if step.get("limit"):
        limit = _resolve_param(step["limit"], params)
    elif params.get("limit"):
        limit = params["limit"]
    if limit:
        try:
            rows = rows[:int(limit)]
        except (ValueError, TypeError):
            pass

    return rows


async def _replay_extract_text(
    browser: Any,
    step: dict[str, Any],
    params: dict[str, Any],
    step_idx: int,
) -> Any:
    """Extract text content from an element.

    If no selector is present (e.g. generic role drag-select on SPA),
    uses hint_text to find the most specific container node that
    contains the captured text.
    """
    from .generic_tools import _collect_text

    if not step.get("selector"):
        hint = step.get("hint_text", "")
        tree = await browser.snapshot()
        if hint:
            node = _find_text_container(tree, hint)
            if node:
                from .logger_stub import logger
                text = _collect_text(node)
                logger.info("[extract] container found",
                            role=node.role,
                            name=(node.name or "")[:40],
                            text_len=len(text))
                return text
        from .logger_stub import logger
        logger.warning("[extract] no container found, using page root")
        return _collect_text(tree)

    node = await _resolve_step_element(browser, step, step_idx, params=params)
    if isinstance(node, ActionResult):
        return node

    return _collect_text(node)


def _find_text_container(
    tree: "SnapshotNode",
    hint: str,
) -> "SnapshotNode | None":
    """Find the most specific container whose text covers the hint.

    Splits hint into lines and finds the smallest container where
    most lines (>=70%) are present — handles whitespace/ordering
    differences between JS textContent and AX tree text.
    """
    from .generic_tools import _collect_text
    from .snapshot_tree import walk_tree

    from .logger_stub import logger

    # Split hint into non-empty lines as match fragments
    fragments = [line.strip() for line in hint.splitlines() if line.strip()]
    if not fragments:
        return None

    # Filter out very short fragments (likely noise)
    fragments = [f for f in fragments if len(f) > 3]
    if not fragments:
        return None

    logger.info("[extract] hint fragments", count=len(fragments),
                fragments=[f[:60] for f in fragments])

    # Also try word-level matching: split into unique words (len>4)
    words = set()
    for f in fragments:
        for w in f.split():
            if len(w) > 4:
                words.add(w)
    logger.info("[extract] hint words", count=len(words),
                samples=list(words)[:10])

    threshold = 0.5
    best: SnapshotNode | None = None
    best_len = float("inf")
    best_score = 0.0

    for node in walk_tree(tree):
        if not node.children:
            continue
        text = _collect_text(node)
        if not text:
            continue

        # Line-level matching
        line_matched = sum(1 for f in fragments if f in text)
        line_ratio = line_matched / len(fragments) if fragments else 0

        # Word-level matching (fallback)
        word_matched = sum(1 for w in words if w in text) if words else 0
        word_ratio = word_matched / len(words) if words else 0

        # Use best of both
        score = max(line_ratio, word_ratio)

        if score < threshold:
            continue
        # Prefer higher score first, then smaller container
        if score > best_score or (score == best_score and len(text) < best_len):
            best = node
            best_len = len(text)
            best_score = score

    if best:
        logger.info("[extract] container match",
                    role=best.role, score=f"{best_score:.0%}",
                    text_len=best_len,
                    name=(best.name or "")[:40])
    else:
        logger.warning("[extract] no container matched",
                       fragments=len(fragments), words=len(words))

    return best


async def _replay_navigate(
    browser: Any,
    step: dict[str, Any],
    params: dict[str, Any],
    step_idx: int,
) -> ActionResult | None:
    """Navigate to URL (with param substitution)."""
    url = _resolve_param(step.get("url", ""), params)
    if not url:
        return ActionResult(
            success=False,
            error=f"step {step_idx + 1}: navigate URL이 없습니다.",
        )
    await browser.navigate(str(url))
    return None


async def _replay_press(
    browser: Any,
    step: dict[str, Any],
    step_idx: int,
) -> ActionResult | None:
    """Press a keyboard key."""
    key = step.get("key", "")
    if not key:
        return ActionResult(
            success=False,
            error=f"step {step_idx + 1}: press key가 없습니다.",
        )
    await browser.press_key(key)
    return None


async def _replay_close_tab(
    browser: Any,
    step: dict[str, Any],
) -> None:
    """Close the current tab and switch back to the previous tab."""
    from .logger_stub import logger

    tabs_before = await _get_tab_list(browser)
    if len(tabs_before) <= 1:
        logger.warning("[replay] close_tab: only 1 tab, nothing to close")
        return

    try:
        await browser.close_tab()
    except Exception as e:
        logger.warning("[replay] close_tab failed", error=str(e))

    # Switch to the last remaining tab
    tabs_after = await _get_tab_list(browser)
    if tabs_after:
        prev_idx = tabs_after[-1][0]
        await browser._session.adapter.call_tool(
            "browser_tabs", {"action": "select", "index": prev_idx},
        )
        logger.info("[replay] close_tab done, switched to tab",
                     index=prev_idx, url=tabs_after[-1][1][:80])

    try:
        await browser.snapshot()
    except Exception:
        pass


async def _replay_scroll(
    browser: Any,
    step: dict[str, Any],
) -> None:
    """Scroll the page, adjusting distance for viewport size difference.

    Uses JS scroll (precise) with a timeout. Falls back to keyboard
    PageDown/PageUp if the page is still loading and JS hangs.
    """
    import asyncio

    direction = step.get("direction", "down")
    distance = step.get("distance", 600)
    recorded_vh = step.get("viewport_height", 0)
    repeat_count = step.get("repeat_count", 1)

    # Try JS scroll with timeout. The scroll itself executes quickly via
    # window.scrollBy, but Playwright's waitForCompletion may hang waiting
    # for network to settle on heavy pages. On timeout the scroll already
    # happened in the browser — just log and continue.
    try:
        async def _js_scroll():
            nonlocal distance
            if recorded_vh and distance:
                try:
                    result = await browser._session.adapter.call_tool(
                        "browser_evaluate",
                        {"function": "() => window.innerHeight"},
                    )
                    current_vh = int(browser._extract_text(result).strip())
                    if current_vh and current_vh != recorded_vh:
                        distance = round(distance * current_vh / recorded_vh)
                except Exception:
                    pass
            await browser.scroll(direction=direction, distance=distance, steps=max(repeat_count, 1))

        await asyncio.wait_for(_js_scroll(), timeout=5.0)
    except asyncio.TimeoutError:
        from .logger_stub import logger
        logger.info("[replay] scroll: JS executed, waitForCompletion timed out (ok)")


async def _replay_select(
    browser: Any,
    step: dict[str, Any],
    params: dict[str, Any],
    step_idx: int,
) -> ActionResult | None:
    """Select an option in a dropdown."""
    node = await _resolve_step_element(browser, step, step_idx, params=params)
    if isinstance(node, ActionResult):
        return node
    value = _resolve_param(step.get("value", ""), params)
    await browser.select_option(node, [str(value)] if value else [])
    return None


async def _resolve_step_element(
    browser: Any,
    step: dict[str, Any],
    step_idx: int,
    *,
    params: dict[str, Any] | None = None,
) -> SnapshotNode | ActionResult:
    """Resolve a step's selector to a SnapshotNode.

    Takes a fresh snapshot and resolves using SelectorSet fallback chain.
    Resolves {{param}} templates in selector using params dict.
    Returns the node on success, or an ActionResult error.
    """
    selector_spec = step.get("selector")
    if not selector_spec:
        return ActionResult(
            success=False,
            error=f"step {step_idx + 1}: selector 정보가 없습니다.",
        )

    # Resolve {{param}} templates in selector
    if params:
        selector_spec = _resolve_selector_templates(selector_spec, params)

    # Take fresh snapshot for resolution
    tree = await browser.snapshot()

    node = resolve_selector_from_spec(tree, selector_spec)
    if node:
        return node

    # Retry once — element might need a moment to appear
    import asyncio
    await asyncio.sleep(1)
    tree = await browser.snapshot()
    node = resolve_selector_from_spec(tree, selector_spec)
    if node:
        return node

    # Build human-readable error
    selector_set = spec_to_selector_set(selector_spec)
    best = selector_set.best
    desc = best.value if best else str(selector_spec)
    return ActionResult(
        success=False,
        error=f"step {step_idx + 1}: 요소를 찾을 수 없습니다 ({desc}). "
              "페이지 구조가 변경되었을 수 있습니다.",
    )


_faker_cache = None

def _resolve_param(value: str, params: dict[str, Any]) -> str | None:
    """Resolve a $param reference, a {{ template }}, or return literal value.

    Returns None if a $param is referenced but not provided.
    """
    if isinstance(value, str) and value.startswith("$"):
        param_name = value[1:]
        if param_name in params:
            return str(params[param_name])
        return None

    # Handle {{ template }} variables
    if isinstance(value, str) and "{{" in value:
        import re
        def replacer(m: re.Match) -> str:
            expr = m.group(1).strip()
            if expr.startswith("faker."):
                try:
                    from faker import Faker
                    global _faker_cache
                    if _faker_cache is None:
                        _faker_cache = Faker(['ko_KR', 'en_US'])
                    method = expr[6:]
                    if method.endswith("()"):
                        method = method[:-2]
                    if hasattr(_faker_cache, method):
                        return str(getattr(_faker_cache, method)())
                except ImportError:
                    pass
            elif expr == "date.today":
                from datetime import date
                return date.today().isoformat()
            elif params and expr in params:
                return str(params[expr])
            return m.group(0)

        return re.sub(r"\{\{([^}]+)\}\}", replacer, value)

    return value


async def _get_tab_list(browser: Any) -> list[tuple[int, str]]:
    """Get list of (index, url) for all real browser tabs."""
    import re as _re

    try:
        result = await browser._session.adapter.call_tool(
            "browser_tabs", {"action": "list"},
        )
        text = browser._extract_text(result)
    except Exception:
        return []

    tabs: list[tuple[int, str]] = []
    for line in text.splitlines():
        m = _re.search(r'-\s+(\d+):.*\(([^)]+)\)\s*$', line)
        if not m:
            continue
        tab_url = m.group(2)
        if tab_url.startswith(("chrome-extension://", "chrome://", "devtools://")):
            continue
        if "127.0.0.1:17577" in tab_url or "localhost:17577" in tab_url:
            continue
        tabs.append((int(m.group(1)), tab_url))
    return tabs


def _resolve_selector_templates(
    selector_spec: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Resolve {{param}} templates in a selector spec.

    Example:
        selector: {role: option, name_contains: "{{search_query}}"}
        params: {search_query: "삼성전자"}
        → {role: option, name_contains: "삼성전자"}
    """
    import re

    def replace_templates(obj: Any) -> Any:
        if isinstance(obj, str):
            def replacer(m: re.Match) -> str:
                key = m.group(1)
                return str(params.get(key, m.group(0)))
            return re.sub(r"\{\{(\w+)\}\}", replacer, obj)
        if isinstance(obj, dict):
            return {k: replace_templates(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [replace_templates(v) for v in obj]
        return obj

    return replace_templates(selector_spec)


async def _replay_wait(
    browser: Any,
    step: dict[str, Any],
    params: dict[str, Any],
    step_idx: int,
) -> None:
    """Wait for an element to appear or a fixed timeout."""
    import asyncio

    timeout_ms = step.get("timeout", 5000)
    selector_spec = step.get("selector")

    if not selector_spec:
        await asyncio.sleep(timeout_ms / 1000)
        return

    if params:
        selector_spec = _resolve_selector_templates(selector_spec, params)

    deadline = asyncio.get_event_loop().time() + timeout_ms / 1000
    while asyncio.get_event_loop().time() < deadline:
        tree = await browser.snapshot()
        node = resolve_selector_from_spec(tree, selector_spec)
        if node:
            return
        await asyncio.sleep(0.5)


async def _replay_select_custom(
    browser: Any,
    step: dict[str, Any],
    params: dict[str, Any],
    step_idx: int,
) -> ActionResult | None:
    """Open a custom dropdown trigger, then click the matching option."""
    import asyncio

    trigger_spec = step.get("trigger")
    if not trigger_spec:
        return ActionResult(
            success=False,
            error=f"step {step_idx + 1}: select_custom에 trigger가 없습니다.",
        )

    if params:
        trigger_spec = _resolve_selector_templates(trigger_spec, params)

    tree = await browser.snapshot()
    trigger_node = resolve_selector_from_spec(tree, trigger_spec)
    if not trigger_node:
        selector_set = spec_to_selector_set(trigger_spec)
        best = selector_set.best
        desc = best.value if best else str(trigger_spec)
        return ActionResult(
            success=False,
            error=f"step {step_idx + 1}: trigger 요소를 찾을 수 없습니다 ({desc}).",
        )

    await browser.click(trigger_node)
    await asyncio.sleep(0.5)

    option_text = _resolve_param(step.get("option_text", ""), params)
    if not option_text:
        return ActionResult(
            success=False,
            error=f"step {step_idx + 1}: option_text가 없습니다.",
        )

    tree = await browser.snapshot()
    from .snapshot_tree import walk_tree
    for node in walk_tree(tree):
        if node.role in ("option", "menuitem", "listitem", "link") and node.ref:
            if node.name and option_text in node.name:
                await browser.click(node)
                return None

    return ActionResult(
        success=False,
        error=f"step {step_idx + 1}: 옵션 '{option_text}'을 찾을 수 없습니다.",
    )


async def _replay_evaluate(
    browser: Any,
    step: dict[str, Any],
    params: dict[str, Any],
    step_idx: int,
) -> Any:
    """Execute JavaScript in the browser and return the result."""
    script = step.get("script", "")
    if not script:
        return ActionResult(
            success=False,
            error=f"step {step_idx + 1}: evaluate에 script가 없습니다.",
        )

    # Substitute $param references in script
    for pname, pvalue in params.items():
        script = script.replace(f"${pname}", str(pvalue))

    try:
        result = await browser._session.adapter.call_tool(
            "browser_evaluate",
            {"function": f"() => {{ {script} }}"},
        )
        text = browser._extract_text(result)
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text
    except Exception as e:
        return ActionResult(
            success=False,
            error=f"step {step_idx + 1}: evaluate 실행 실패: {e}",
        )
