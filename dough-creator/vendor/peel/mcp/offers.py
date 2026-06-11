"""``peel.mcp.offers`` — post-exec / connection offer tools.

Domain module for the ``resolve_schedule``, ``crystallize``, and
``connect_offer`` tools. Exposes exactly two public symbols (``TOOLS`` and
``HANDLERS``); all backend access goes through ``core``.
"""

import mcp.types as types

import core


# ── Tool catalog ────────────────────────────────────────────────────────

TOOLS: list[types.Tool] = [
    types.Tool(
        name="resolve_schedule",
        description=(
            "Resolve a natural-language scheduling request into a structured "
            f"schedule draft the user confirms in the {core.brand_name()} UI. Pass the user's "
            "own phrasing as `prompt`."
        ),
        inputSchema={
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
        },
    ),
    types.Tool(
        name="crystallize",
        description=(
            "Offer to save a gather you JUST ran as a reusable dough — pass the "
            "turn's receipt (the proven trace) and the backend reverse-engineers "
            "a build brief from it. The post-exec 'save this run?' offer."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "receipt": {"type": "object", "additionalProperties": True,
                            "description": "The turn's Receipt (kits/thinking/types.py shape)."},
                "schedule_intent": {"type": "string"},
            },
            "required": ["receipt"],
        },
    ),
    types.Tool(
        name="connect_offer",
        description=(
            "Surface an in-chat Connect chip when a bake needs a kit the user "
            "hasn't connected (OAuth must run in the UI, not your shell). Pass "
            "the missing kit id(s); the user connects, then retry the bake."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kits": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "dough_id": {"type": "string"},
                "reason": {"type": "string", "description": "One line: what the user wanted."},
            },
            "required": ["kits"],
        },
    ),
]


# ── Tool dispatch ────────────────────────────────────────────────────────

async def resolve_schedule(args: dict) -> object:
    prompt = (args.get("prompt") or "").strip()
    if not prompt:
        return {"error": "prompt is required"}
    return await core.post("/oven/schedules/resolve", {"prompt": prompt})


async def crystallize(args: dict) -> object:
    receipt = args.get("receipt")
    if not isinstance(receipt, dict):
        return {"error": "receipt object is required"}
    return await core.post("/oven/crystallize", {
        "receipt": receipt, "schedule_intent": args.get("schedule_intent", ""),
    })


async def connect_offer(args: dict) -> object:
    kits = args.get("kits") or []
    if not kits:
        return {"error": "kits is required"}
    return await core.post("/oven/connect-offer", {
        "kits": kits, "dough_id": args.get("dough_id", ""),
        "reason": args.get("reason", ""),
    })


HANDLERS: dict = {
    "resolve_schedule": resolve_schedule,
    "crystallize": crystallize,
    "connect_offer": connect_offer,
}
