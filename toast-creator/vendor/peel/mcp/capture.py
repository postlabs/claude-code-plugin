"""``start_api_capture`` / ``promote_api`` tools — discover a site's data API
during a browse and cache a direct, secret-free call to it.

The API-capture twin of ``promote_web_task`` (browse.py). Where that one caches
the page's DOM reads, this finds the JSON endpoint the page itself called and
caches a direct ``fetch`` to it — far more durable (an API outlives the DOM
that renders it) and faster (one fetch, no page render).

Used as a TWO-CALL bracket around a normal browse, because the agentic browse
is the agent's own MCP loop (no single call wraps it):

    1. start_api_capture()          → capture_id   (before browsing)
    2. browse([...])                → answer        (normal tools; capture is passive)
    3. promote_api(capture_id, answer=<that answer>, ...)   (after)

promote_api stops the capture and finds the captured response whose body
contains the answer — that IS the data API (deterministic answer-correlation,
no endpoint guessing). It emits a ``user.webapi_*`` dough that calls the API
via ``act(eval_js: fetch, credentials:"include")`` — secret-free, the browser
attaches the origin's own cookies; we never read or store a token.

``ok:false`` (nothing captured / no body matched the answer) is a NORMAL
outcome, not an error — a server-rendered page exposes no data API, and the
slow browse stays the path. Fall back to ``promote_web_task`` (DOM cache) then.
"""

import mcp.types as types

import core


TOOLS: list[types.Tool] = [
    types.Tool(
        name="start_api_capture",
        description=(
            "Begin a passive network capture BEFORE a browse you want to mine "
            "for its data API. Returns a `capture_id`; browse with your normal "
            "tools (the capture coexists, read-only), then pass the id to "
            "`promote_api`. Use when a browse worth reusing likely reads from a "
            "JSON/XHR endpoint (most modern sites) — the cached API call is more "
            "durable and faster than a DOM-read cache. Requires the browser up."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="promote_api",
        description=(
            "After a browse that you bracketed with `start_api_capture`, cache "
            "the site's data API as a fast, secret-free dough. Pass the "
            "`capture_id` and the browse's `answer` text — its distinctive "
            "tokens (names, numbers) are matched against the captured response "
            "bodies to pick the data API deterministically (no endpoint "
            "guessing). The emitted `user.webapi_*` dough calls that endpoint "
            "in-page via fetch with the origin's own cookies — no token is read "
            "or stored. Set `query_param` to the URL query parameter carrying "
            "the user's input to make the dough reusable for any query. "
            "`ok:false` (nothing captured / answer not found in any body) is a "
            "NORMAL result — the page may be server-rendered; fall back to "
            "promote_web_task (DOM cache) or the live browse."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "capture_id": {"type": "string", "description": "The id from start_api_capture."},
                "answer": {"type": "string", "description": "The browse's answer text — its tokens are matched against captured response bodies to find the data API."},
                "query_param": {"type": "string", "description": "URL query parameter carrying the user's query (makes the cached dough reusable for any query). Omit for a single-shot cache."},
                "shape_js": {"type": "string", "description": "Optional JS expression over `data` (the parsed JSON) selecting the answer fields; absent, the raw body is returned."},
                "name": {"type": "string", "description": "Optional action name for the cached dough (else derived from the endpoint)."},
            },
            "required": ["capture_id", "answer"],
        },
    ),
]


async def _start_api_capture(args: dict) -> object:
    return await core.post("/webdough/capture-api/start", {})


async def _promote_api(args: dict) -> object:
    if not args.get("capture_id") or not args.get("answer"):
        return {"error": "capture_id and answer are required"}
    body: dict = {}
    for k in ("capture_id", "answer", "query_param", "shape_js", "name"):
        if args.get(k):
            body[k] = args[k]
    return await core.post("/webdough/promote-api", body)


HANDLERS: dict[str, object] = {
    "start_api_capture": _start_api_capture,
    "promote_api": _promote_api,
}
