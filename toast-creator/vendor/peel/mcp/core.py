"""``peel.mcp.core`` — shared config / HTTP / util layer for the peel MCP shim.

Owns the stateless plumbing every domain module (find/bake/browse/offers/ask)
imports: backend base URL + auth headers from spawn env, the async httpx
client + GET/POST helpers, and the stderr logger + safe-JSON parse. Domain
modules ``import core`` and call ``core.get`` / ``core.post`` / ``core.client``
/ ``core.locale`` / etc. — identical bodies to the original ``mcp_server.py``
shared layer, with the leading underscore dropped now that these names are
imported across modules.
"""

import os
import sys
import json

import httpx

# Per-read socket stall guard. The total bake budget is enforced separately
# as an asyncio.wait_for deadline; this just stops a dead connection from
# hanging a single read until the total deadline.
STALL_TIMEOUT = 120.0
GET_TIMEOUT = 30.0


def base_url() -> str:
    return os.environ.get(
        "PEEL_BASE_URL", "http://127.0.0.1:18587/api/v1",
    ).rstrip("/")


def locale() -> str:
    return os.environ.get("PEEL_LOCALE", "en")


def brand_name() -> str:
    """Product display name. Injected by Electron as ``BRAND_NAME`` (from
    ``src/brand.json``) and inherited through the CLI subprocess chain;
    the default keeps standalone runs working."""
    return os.environ.get("BRAND_NAME", "Toast")


def chat_session() -> str | None:
    """The CLI chat session this peel instance belongs to, if any. Injected by
    the session's spawn env (``PEEL_CHAT_SESSION``) and inherited by peel
    as claude's child process. When present it's forwarded on bakes so the
    backend mirrors bake_* progress into that chat stream (BakeBlock)."""
    return os.environ.get("PEEL_CHAT_SESSION") or None


def bake_timeout() -> float:
    try:
        return float(os.environ.get("PEEL_BAKE_TIMEOUT", "600"))
    except ValueError:
        return 600.0


def auth_headers() -> dict[str, str]:
    key = os.environ.get("PEEL_SUBSCRIPTION_KEY")
    return {"x-subscription-key": key} if key else {}


def client(timeout: httpx.Timeout) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url(), headers=auth_headers(), timeout=timeout,
    )


def log(msg: str) -> None:
    # stdout is the MCP protocol channel — logs MUST go to stderr only.
    print(f"[peel-mcp] {msg}", file=sys.stderr, flush=True)


def safe_json(text: str) -> object:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


# ── HTTP helpers ─────────────────────────────────────────────────────────

async def get(path: str, params: dict | None = None) -> object:
    """GET ``{BASE}{path}`` → parsed JSON, or raw text for text/* responses."""
    async with client(httpx.Timeout(GET_TIMEOUT)) as c:
        try:
            r = await c.get(path, params=params)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text}
        except httpx.HTTPError as e:
            return {"error": "backend unreachable", "detail": str(e)}
        if "application/json" in r.headers.get("content-type", ""):
            return r.json()
        return r.text  # PlainTextResponse routes (retrieval listings)


async def post(path: str, body: dict) -> object:
    """POST JSON to ``{BASE}{path}`` → parsed JSON (non-streaming)."""
    async with client(httpx.Timeout(GET_TIMEOUT)) as c:
        try:
            r = await c.post(path, json=body)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text}
        except httpx.HTTPError as e:
            return {"error": "backend unreachable", "detail": str(e)}
        if "application/json" in r.headers.get("content-type", ""):
            return r.json()
        return r.text
