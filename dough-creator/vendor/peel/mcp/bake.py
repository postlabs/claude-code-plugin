"""``bake`` domain — execute flours/doughs and recall their donuts.

Owns the bake tool surface: ``bake`` (run to completion, withheld
receipt), ``get_bake_status`` (status + failure refs), ``get_artifact``
(deliberate output retrieval), ``recall`` (latest-or-specific donut).
Module-private ``_bake`` consumes the SSE stream to completion; ``_donut``
and ``_failed_steps_from_donut`` shape the donut projections.
"""

import asyncio
import urllib.parse

import httpx
import mcp.types as types
from httpx_sse import EventSource

import core


async def _bake(dough_id: str, inputs: dict, glaze: dict | None) -> dict:
    """POST the bake, consume the SSE to completion, return a THIN result.

    The full ``output`` carried on ``bake_complete`` is deliberately
    dropped — that's the withheld receipt. Only ``bake_id`` + status +
    failure refs cross back into model context.
    """
    body: dict = {"inputs": inputs}
    if glaze:
        body["glaze"] = glaze
    url = f"/doughs/{urllib.parse.quote(dough_id, safe='')}/bake"
    total = core.bake_timeout()
    state: dict = {"complete": None, "paused": None, "bake_id": None}

    params: dict = {"locale": core.locale()}
    sid = core.chat_session()
    if sid:
        params["chat_session_id"] = sid

    async def consume() -> None:
        timeout = httpx.Timeout(core.STALL_TIMEOUT, connect=10.0)
        async with core.client(timeout) as c:
            async with c.stream(
                "POST", url, params=params, json=body,
                headers={"Accept": "text/event-stream"},
            ) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp,
                    )
                async for sse in EventSource(resp).aiter_sse():
                    data = core.safe_json(sse.data)
                    if isinstance(data, dict) and data.get("donut_id"):
                        state["bake_id"] = data["donut_id"]
                    if sse.event == "bake_complete":
                        state["complete"] = data
                    elif sse.event == "bake_paused":
                        state["paused"] = data

    try:
        await asyncio.wait_for(consume(), timeout=total)
    except asyncio.TimeoutError:
        return {"error": "bake timed out", "bake_id": state["bake_id"],
                "detail": f"exceeded PEEL_BAKE_TIMEOUT={total}s (total)"}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text}
    except httpx.HTTPError as e:
        return {"error": "bake stream failed", "bake_id": state["bake_id"], "detail": str(e)}

    complete, paused, bake_id = state["complete"], state["paused"], state["bake_id"]
    if complete is not None:
        thin: dict = {
            "bake_id": complete.get("donut_id", bake_id),
            "status": complete.get("status", "unknown"),
        }
        # ``failed_steps`` here is correct — it comes off the bake_complete
        # SSE event (bake_events.complete), NOT the persisted Donut.
        for k in ("error", "error_code", "error_params", "failed_steps"):
            if complete.get(k) is not None:
                thin[k] = complete[k]
        thin["note"] = (
            "Result withheld by design — the receipt is rendered in the "
            f"{core.brand_name()} UI from bake_id. Call get_artifact(bake_id) only if you "
            "need an output value to chain into a next step."
        )
        return thin
    if paused is not None:
        return {
            "bake_id": paused.get("donut_id", bake_id),
            "status": "paused",
            "step_key": paused.get("step_key"),
            "note": f"Bake paused for confirmation — the user resumes it in the {core.brand_name()} UI.",
        }
    return {"error": "bake produced no terminal event", "bake_id": bake_id}


async def _donut(bake_id: str) -> object:
    return await core.get(f"/doughs/donuts/{urllib.parse.quote(bake_id, safe='')}")


def _failed_steps_from_donut(donut: dict) -> list[dict]:
    """Project a persisted Donut's failed steps into thin failure refs.

    The Donut model has NO ``failed_steps`` field (that lives only on the
    bake_complete SSE event); failures are recovered from ``steps[]`` where
    ``status == "failed"``.
    """
    out: list[dict] = []
    for s in donut.get("steps") or []:
        if isinstance(s, dict) and s.get("status") == "failed":
            ref = {"step_key": s.get("step_key")}
            for k in ("error", "error_code"):
                if s.get(k) is not None:
                    ref[k] = s[k]
            out.append(ref)
    return out


# ── Tool catalog ────────────────────────────────────────────────────────

TOOLS: list[types.Tool] = [
    types.Tool(
        name="bake",
        description=(
            "Execute a flour or dough. Blocks until the bake finishes and "
            "returns a THIN result: {bake_id, status} (plus failure refs on "
            "error). The full result is intentionally withheld from your "
            f"context — it is rendered for the user in the {core.brand_name()} UI from "
            "bake_id. The backend re-validates your input against the live "
            "contract and returns a structured error if it's wrong — fix it "
            "and retry. Use dough_spec (or find_doughs' inlined spec) to learn "
            "the `input` shape."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "dough_id": {"type": "string"},
                "input": {"type": "object", "additionalProperties": True,
                          "description": "Inputs matching the dough's schema (see dough_spec)."},
                "glaze": {"type": "object", "additionalProperties": True,
                          "description": "Optional bake-time agent/model override {provider?, model?}."},
            },
            "required": ["dough_id"],
        },
    ),
    types.Tool(
        name="get_bake_status",
        description=(
            "Look up the status of a prior bake by bake_id (e.g. one started "
            "elsewhere). Returns {bake_id, status, dough_id} and failure refs "
            "— never the output payload."
        ),
        inputSchema={
            "type": "object",
            "properties": {"bake_id": {"type": "string"}},
            "required": ["bake_id"],
        },
    ),
    types.Tool(
        name="get_artifact",
        description=(
            "Deliberately retrieve the OUTPUT of a finished bake by bake_id, "
            "for chaining a value into a next step. This is the one place a "
            "bake result enters your context — use it only when you actually "
            "need the value, not to 'see what happened' (the user already "
            "sees the full receipt in the UI)."
        ),
        inputSchema={
            "type": "object",
            "properties": {"bake_id": {"type": "string"}},
            "required": ["bake_id"],
        },
    ),
    types.Tool(
        name="recall",
        description=(
            "Recall a finished bake's donut — the latest for a dough (pass "
            "dough_id) or a specific one (pass bake_id). Use to inspect a prior "
            "run's output/status when chaining or answering about it."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "dough_id": {"type": "string", "description": "Latest donut for this dough."},
                "bake_id": {"type": "string", "description": "A specific donut id."},
            },
        },
    ),
]


# ── Tool dispatch ────────────────────────────────────────────────────────

async def _bake_call(args: dict) -> object:
    dough_id = args.get("dough_id")
    if not dough_id:
        return {"error": "dough_id is required"}
    return await _bake(dough_id, args.get("input") or {}, args.get("glaze"))


async def _get_bake_status_call(args: dict) -> object:
    bake_id = args.get("bake_id")
    if not bake_id:
        return {"error": "bake_id is required"}
    d = await _donut(bake_id)
    if not isinstance(d, dict) or d.get("error"):
        return d
    out = {"bake_id": bake_id, "status": d.get("status"), "dough_id": d.get("dough_id")}
    for k in ("error", "error_code"):
        if d.get(k) is not None:
            out[k] = d[k]
    failed = _failed_steps_from_donut(d)
    if failed:
        out["failed_steps"] = failed
    return out


async def _get_artifact_call(args: dict) -> object:
    bake_id = args.get("bake_id")
    if not bake_id:
        return {"error": "bake_id is required"}
    d = await _donut(bake_id)
    if not isinstance(d, dict) or d.get("error"):
        return d
    return {"bake_id": bake_id, "status": d.get("status"), "output": d.get("output")}


async def _recall_call(args: dict) -> object:
    bake_id, dough_id = args.get("bake_id"), args.get("dough_id")
    if bake_id:
        return await _donut(bake_id)
    if dough_id:
        return await core.get(f"/doughs/{urllib.parse.quote(dough_id, safe='')}/donuts/latest")
    return {"error": "pass dough_id or bake_id"}


HANDLERS: dict = {
    "bake": _bake_call,
    "get_bake_status": _get_bake_status_call,
    "get_artifact": _get_artifact_call,
    "recall": _recall_call,
}
