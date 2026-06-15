"""``peel`` — the agent-facing MCP shim for the Mojo backend.

A thin, stateless stdio MCP server that the foreign CLI agents (Claude
Code / Codex / Gemini) spawn as a subprocess. It is the *curated* twin of
the broad ``peel.cmd`` shell client: where the shell exposes every
retrieval verb as text for humans/CI, this exposes a small typed tool
surface for the model — the affordance the shell can't give (a tool
result the harness treats as machinery, not narratable prose).

Lives in ``src/backend/peel/`` alongside ``peel.cmd`` (and a future
``peel.sh``), shipped with the binary as DATA (not imported by ``app.*``)
so it can be spawned as a subprocess by file path in both dev and frozen
builds. See ``peel/README.md``.

This module is the THIN entry point: it bootstraps sys.path, imports the
domain modules under ``peel/mcp/`` (core + find/bake/browse/offers),
assembles their ``TOOLS``/``HANDLERS``, and runs the stdio server. All tool
logic lives in those modules.

Design rules (curated MCP subset — conservative on purpose):

  * **Two thin clients of one daemon, not one wrapping the other.** This
    server talks to the FastAPI backend over localhost HTTP directly — it
    does NOT shell out to ``peel.cmd``. Shared logic (schemas, validation,
    the bake receipt) lives in the backend so the two clients can't drift.
  * **Conservative MCP subset only.** Static curated tools, stdio, stable
    schemas, minimal tool results. No dynamic per-dough tool registration,
    no ``_meta`` receipt hiding, no MCP Apps — all unevenly supported today.
  * **Fetch-then-fill for bake's dynamic schema.** ``bake`` stays a stable
    ``(dough_id, input)`` tool; ``dough_spec`` returns the per-dough
    input schema the agent fills in.
  * **Receipt withholding, not labeling.** ``bake`` returns only a thin
    factual payload (``bake_id`` + status). The authoritative receipt is
    the persisted donut, rendered by the Electron UI from the ``bake_id``
    — it is never placed in model context. ``get_artifact`` is the
    deliberate escape hatch when the agent genuinely needs an output value
    to chain into a next step.

Run by bare file path::

    python <...>/peel/mcp_server.py
"""

# Spawned by bare file path → Python puts this file's directory on
# sys.path[0]. Drop it before importing anything else so a future sibling
# module in ``peel/`` (e.g. a ``json.py`` / ``types.py``) can never shadow
# a stdlib import. site-packages stays on the path, so httpx/mcp still
# import fine; only the script's own dir is removed.
import sys
sys.path.pop(0)

import asyncio  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402

import mcp.types as types  # noqa: E402
from mcp.server.lowlevel import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402

# Append the mcp/ subdir to sys.path so the domain modules import by bare
# name (``import core`` etc.). APPENDED, not inserted — it is searched LAST,
# so stdlib always wins on a name clash. This is the README-sanctioned way
# (peel/README.md line 49: load siblings by absolute path, never sys.path[0]).
_MCP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp")
sys.path.append(_MCP_DIR)

import core  # noqa: E402
import find  # noqa: E402
import bake  # noqa: E402
import browse  # noqa: E402
import offers  # noqa: E402
import manual  # noqa: E402


# ── Tool catalog + dispatch table (assembled from the domain modules) ─────
#
# No ``ask_user`` tool: questions go through the ``:::askuser`` marker the CLIs
# emit in prose (or Claude's native AskUserQuestion) — never an MCP tool. See
# app/cli/instructions/OVEN.md → "Ask the user when the request has a real fork".

TOOLS: list[types.Tool] = (
    find.TOOLS + bake.TOOLS + browse.TOOLS + offers.TOOLS + manual.TOOLS
)

HANDLERS: dict = {
    **find.HANDLERS,
    **bake.HANDLERS,
    **browse.HANDLERS,
    **offers.HANDLERS,
    **manual.HANDLERS,
}


async def _call(name: str, args: dict) -> object:
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"unknown tool: {name!r}"}
    return await handler(args)


async def _serve() -> None:
    server = Server("peel")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
        try:
            result = await _call(name, arguments or {})
        except Exception as e:  # never crash the server on one bad call
            core.log(f"tool {name!r} raised: {type(e).__name__}: {e}")
            result = {"error": f"{type(e).__name__}: {e}"}
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2)
        return [types.TextContent(type="text", text=text)]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    core.log(f"serving — base={core.base_url()} locale={core.locale()}")
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
