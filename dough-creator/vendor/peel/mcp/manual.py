"""``manual`` — reference manuals the agent CONSULTS, for the peel MCP shim.

Domain module: exposes ``TOOLS`` (the mcp.types.Tool defs) and ``HANDLERS``
(tool-name → async handler).

A manual is text on how to operate something correctly — how to read the user's
profile data, how a capability behaves. Manuals are NOT bakeable and never
appear in ``find_doughs`` / ``list_capabilities``; this verb is the only way to
reach them.

- ``manual()``         → the index of available manuals (name + summary).
- ``manual(name=...)`` → that manual's body text. Read it, apply it inline.
"""

import mcp.types as types

import core


TOOLS: list[types.Tool] = [
    types.Tool(
        name="manual",
        description=(
            "Read a reference MANUAL — how to operate something correctly (e.g. how to "
            "read the user's workspace / profile data on disk). Call with NO name to LIST "
            "the available manuals (name + one-line summary); call with a `name` to get "
            "that manual's text, then apply it inline — do not bake it. Manuals are not "
            "in find_doughs and are not bakeable; this is the only way to reach one. "
            "ALWAYS read the relevant manual before improvising over the user's profile "
            "data or an unfamiliar local store."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Manual to read (e.g. 'workspace'). Omit to list all available manuals.",
                },
            },
        },
    ),
]


# ── Handlers ─────────────────────────────────────────────────────────────

async def manual(args: dict) -> object:
    name = (args.get("name") or "").strip()
    if not name:
        return await core.get("/doughs/manual")
    return await core.get(f"/doughs/manual/{name}")


HANDLERS: dict = {
    "manual": manual,
}
