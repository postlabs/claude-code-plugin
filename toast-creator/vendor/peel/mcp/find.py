"""``find`` — retrieval/validation tools for the peel MCP shim.

Domain module: exposes ``TOOLS`` (the mcp.types.Tool defs) and ``HANDLERS``
(tool-name → async handler). Logic moved verbatim from ``mcp_server.py``;
the only edits are the shared-helper renames (``_get`` → ``core.get`` etc.).
"""

import json

import mcp.types as types

import core


# ── Tool catalog ────────────────────────────────────────────────────────

TOOLS: list[types.Tool] = [
    types.Tool(
        name="find_doughs",
        description=(
            "Discover bakeable flours/doughs by capability over the LIVE registry. "
            "Filter by `verb` (closed vocabulary — glossary below), `object`, and/or "
            "`namespace` (exact or prefix). Returns structured rows {id, kind, verb, "
            "object, namespace, display_name, summary, effect (read|write|external_send|"
            "destructive), connected, requires_connection, inputs}; on a UNIQUE match it "
            "inlines the full spec under `specs` so you "
            "can bake directly (find→bake, no separate dough_spec). Map the user's "
            "intent onto a verb. Do NOT put user entities, recipients, account names, "
            "or task content into filters — those are bake inputs, not in the corpus.\n\n"
            "Verbs: list=enumerate a container (no query); get=read a known object or "
            "synthesized context (local/known); fetch=pull from a live external API "
            "(remote); download=binary file/attachment; search=find by criteria from a "
            "source; send=transmit to an external recipient (side-effect); move=relocate "
            "within a system; create=new durable object; update=modify existing; "
            "delete=remove/trash; classify=label each item of content; convert=transform "
            "representation (format/flatten/extract/export); filter=narrow data already "
            "held (no source reach); summarize=shorten content; refresh=re-pull state "
            "(usually expressed as fetch); review=audit/assess and return findings; "
            "connect=manage a kit connection; introspect=self-check (object: self)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "verb": {"type": "array",
                         "items": {"type": "string", "enum": [
                             "list", "get", "fetch", "download", "search",
                             "send", "move", "create", "update", "delete",
                             "classify", "convert", "filter", "summarize",
                             "refresh", "review", "connect", "introspect",
                         ]},
                         "description": "Capability verb(s). Repeatable — OR-matched. See the glossary in this tool's description."},
                "object": {"type": "array", "items": {"type": "string"},
                           "description": "Object filter(s), e.g. message, email, event. Repeatable — OR-matched."},
                "namespace": {"type": "string",
                              "description": "Capability domain, exact or prefix (e.g. 'postlab.google' matches the whole subtree)."},
                "kind": {"type": "string", "enum": ["flour", "dough"],
                         "description": "Optional: flour (one capability) or dough (composition)."},
                "connected": {"type": "boolean",
                              "description": "Optional: only doughs whose required kit is currently connected."},
                "limit": {"type": "integer", "default": 50},
            },
        },
    ),
    types.Tool(
        name="dough_spec",
        description=(
            "Fetch the full input/output contract for one or more flour/dough ids, in "
            "one call. Call it before bake when a dough's inputs aren't already in your "
            "context (find_doughs inlines the spec on a unique match, so you can often "
            "skip this). Returns {id: {inputs, outputs, verb, object, kind, connected, "
            "...}} — the exact keys/types to fill. Copy ids verbatim."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ids": {"type": "array", "items": {"type": "string"}, "minItems": 1,
                        "description": "Flour/dough ids (full dotted paths). Up to 50."},
            },
            "required": ["ids"],
        },
    ),
    types.Tool(
        name="validate_dough",
        description=(
            "Validate a whole authored dough by id (closure, refs, step shapes). "
            "Use while building a dough, before relying on it. Returns the "
            "validation errors (empty if clean)."
        ),
        inputSchema={
            "type": "object",
            "properties": {"dough_id": {"type": "string"}},
            "required": ["dough_id"],
        },
    ),
    types.Tool(
        name="list_capabilities",
        description=(
            "List kit namespaces (with their covered verbs). OPTIONAL — the legal "
            "verbs are already enumerated in find_doughs' schema, and find_doughs "
            "returns namespace facets on a broad query. Use this only to browse "
            "which kit namespaces exist."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Optional namespace filter."},
            },
        },
    ),
]


# ── Handlers ─────────────────────────────────────────────────────────────

async def find_doughs(args: dict) -> object:
    params: dict = {}
    if args.get("verb"):
        params["verb"] = args["verb"]
    if args.get("object"):
        params["object"] = args["object"]
    if args.get("namespace"):
        params["namespace"] = args["namespace"]
    if args.get("kind"):
        params["kind"] = args["kind"]
    if args.get("connected") is not None:
        params["connected"] = args["connected"]
    if args.get("limit"):
        params["limit"] = args["limit"]
    return await core.get("/doughs/retrieval/search", params)


async def dough_spec(args: dict) -> object:
    ids = args.get("ids") or []
    if not ids:
        return {"error": "ids is required"}
    return await core.get("/doughs/retrieval/specs", {"ids": ",".join(ids)})


async def validate_dough(args: dict) -> object:
    dough_id = args.get("dough_id")
    if not dough_id:
        return {"error": "dough_id is required"}
    return await core.post("/doughs/validate", {"id": dough_id})


async def list_capabilities(args: dict) -> object:
    verbs = await core.get("/doughs/retrieval/verbs")
    ns_params = {"keyword": args["keyword"]} if args.get("keyword") else None
    namespaces = await core.get("/doughs/retrieval/namespaces", ns_params)
    verbs_text = verbs if isinstance(verbs, str) else json.dumps(verbs)
    ns_text = namespaces if isinstance(namespaces, str) else json.dumps(namespaces)
    return "== VERBS ==\n" + verbs_text + "\n\n== NAMESPACES ==\n" + ns_text


HANDLERS: dict = {
    "find_doughs": find_doughs,
    "dough_spec": dough_spec,
    "validate_dough": validate_dough,
    "list_capabilities": list_capabilities,
}
