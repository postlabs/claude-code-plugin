"""``browse`` / ``promote_web_task`` / ``promote_web_batch`` tools — the agent's browser-side surface."""

import mcp.types as types

import core


TOOLS: list[types.Tool] = [
    types.Tool(
        name="browse",
        description=(
            "Open URLs in the user's real Chrome and return each page's "
            "accessibility snapshot (read-only gather). Up to 8 URLs in "
            "parallel. Requires the browser to be up."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "max_chars": {"type": "integer", "description": "Per-page snapshot cap (0 = no cap)."},
            },
            "required": ["urls"],
        },
    ),
    types.Tool(
        name="promote_web_task",
        description=(
            "After a web browse worth reusing, cache the page's reads as a fast "
            "extraction dough so the next run skips the live browse. Pass the "
            "`bake_id` the browse returned (preferred — scopes to exactly that "
            "task's reads); a `url` works too. Returns the cached dough id, the "
            "durably-cached `fields`, and any `live_read` fields that have no "
            "stable anchor (those must be read live each time — the cache can't "
            "cover them). Use only when the task is the kind a user would repeat; "
            "one-off lookups aren't worth caching."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "bake_id": {"type": "string", "description": "The browse's bake_id (preferred)."},
                "url": {"type": "string", "description": "The page URL whose reads to cache (fallback)."},
                "name": {"type": "string", "description": "Optional action name for the cached dough."},
            },
        },
    ),
    types.Tool(
        name="promote_web_batch",
        description=(
            "For a REPEATED extraction across many same-structure pages (e.g. "
            "'price from each of these 20 product detail pages'): browse ONE "
            "sample page, then call this with its `bake_id` to template that "
            "page's reads into a url-parameterized extractor PLUS a fan-out dough "
            "that applies it across a url list. Returns `batch_dough_id` — bake it "
            "with `{urls:[...]}` (all the pages) to get one row per page. "
            "`live_read` is the cost signal: empty = every page is deterministic "
            "(no LLM); non-empty = those fields cost one live read PER page, so "
            "the batch isn't free. Use only when the pages truly share structure; "
            "for a single page use promote_web_task instead."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "bake_id": {"type": "string", "description": "The sample page browse's bake_id (preferred)."},
                "url": {"type": "string", "description": "The sample page URL whose reads to template (fallback)."},
                "name": {"type": "string", "description": "Optional action name; the batch dough is named webbatch_<name>."},
            },
        },
    ),
]


async def _browse(args: dict) -> object:
    urls = args.get("urls") or []
    if not urls:
        return {"error": "urls is required"}
    body: dict = {"urls": urls}
    if args.get("max_chars") is not None:
        body["max_chars"] = args["max_chars"]
    return await core.post("/webdough/browse", body)


async def _promote_web_task(args: dict) -> object:
    if not args.get("bake_id") and not args.get("url"):
        return {"error": "pass a bake_id (preferred) or a url"}
    body: dict = {}
    for k in ("bake_id", "url", "name"):
        if args.get(k):
            body[k] = args[k]
    return await core.post("/webdough/promote", body)


async def _promote_web_batch(args: dict) -> object:
    if not args.get("bake_id") and not args.get("url"):
        return {"error": "pass a bake_id (preferred) or a url"}
    body: dict = {}
    for k in ("bake_id", "url", "name"):
        if args.get(k):
            body[k] = args[k]
    return await core.post("/webdough/promote-batch", body)


HANDLERS: dict[str, object] = {
    "browse": _browse,
    "promote_web_task": _promote_web_task,
    "promote_web_batch": _promote_web_batch,
}
