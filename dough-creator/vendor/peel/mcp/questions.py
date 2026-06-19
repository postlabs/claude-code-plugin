"""``questions`` — the workspace open-questions loop, for the peel MCP shim.

The synthesis pipeline DEFERS the cases it can't decide confidently (an
uncertain person relationship, a conversation it can't categorize, a possible
duplicate) to the user instead of guessing — it queues them as *ambiguities*.
This domain is the user side of that loop: surface the queue, and write the
user's answer back into the workspace.

- ``list_open_questions()``  → the pending decisions, highest-leverage /
  lowest-confidence first. Each carries ``resolve_with`` (the flour that
  applies the answer), ``id`` (the queue item), a one-line ``question``, and
  suggested ``candidate_answers``. UNLIKE ``bake``, this RETURNS the content —
  the agent needs it to actually ask the user.
- ``answer_question(resolve_with, id, answer)`` → apply the user's answer by
  baking the question's ``resolve_with`` flour. Stamps it onto the
  person/conversation (``source=user``, ``confidence=1.0``) and drains it from
  the queue. One tool resolves every kind the queue surfaces: ambiguity
  questions bake their ``…answer_question`` flour with ``{ambiguity_id,
  answer}``, and merge proposals are routed here too — the handler reads the
  ``…apply_merge``/``…dismiss_merge`` ``resolve_with`` and the ``answer`` and
  bakes apply-vs-dismiss by pair id. Callers never special-case merges.
"""

import asyncio
import urllib.parse

import httpx
import mcp.types as types
from httpx_sse import EventSource

import core

_LIST_DOUGH = "advanced.workspace.questions.list_open_questions"


async def _run(dough_id: str, inputs: dict) -> dict:
    """Bake ``dough_id`` to completion and return the raw ``bake_complete`` data
    (``{donut_id, status, output, …}``) — or ``{error}``. Unlike the ``bake``
    tool's thin result, the caller keeps the output (the questions read needs
    it; the answer write checks the status)."""
    body = {"inputs": inputs}
    url = f"/doughs/{urllib.parse.quote(dough_id, safe='')}/bake"
    params = {"locale": core.locale()}
    sid = core.chat_session()
    if sid:
        params["chat_session_id"] = sid
    state: dict = {"complete": None, "bake_id": None}

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

    try:
        await asyncio.wait_for(consume(), timeout=core.bake_timeout())
    except asyncio.TimeoutError:
        return {"error": "timed out", "bake_id": state["bake_id"]}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}", "detail": e.response.text}
    except httpx.HTTPError as e:
        return {"error": "bake stream failed", "detail": str(e)}
    complete = state["complete"]
    if complete is None:
        return {"error": "bake produced no terminal event", "bake_id": state["bake_id"]}
    return complete


# ── Tool catalog ────────────────────────────────────────────────────────

TOOLS: list[types.Tool] = [
    types.Tool(
        name="list_open_questions",
        description=(
            "List the workspace decisions the synthesis pipeline deferred to the "
            "USER — uncertain person relationships, uncategorized conversations, "
            "possible duplicate people. These are things it refused to guess. "
            "Returns the pending items (highest-leverage / lowest-confidence "
            "first); each carries `question` (ask the user this), "
            "`candidate_options` (offer each option's `label`; when the user "
            "picks one, pass that option's `value` as the answer), `resolve_with` "
            "+ `id` (pass both to answer_question), and `source_domain`/"
            "`subject_ref` for context. "
            "Surface these to the user when they ask about their people/tasks/"
            "project, or when they ask what needs their input — do not auto-decide "
            "them yourself; the point is to let the user define them."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "max_per_domain": {
                    "type": "number",
                    "description": "Cap per source domain (default 50).",
                },
            },
        },
    ),
    types.Tool(
        name="answer_question",
        description=(
            "Apply the USER's answer to one open question — the write-back half of "
            "the loop. Pass the `resolve_with` and `id` from a list_open_questions "
            "item plus the `answer` — the `value` of the candidate_option the user "
            "picked (an enum token like `external`, not its display label). Stamps "
            "the answer onto the person/conversation "
            "(source=user) and removes it from the queue. Only call this with an "
            "answer the user actually gave. Handles MERGE proposals too: for a "
            "`merge_proposal` item, the `answer` is whether to merge ('merge' vs "
            "'keep separate') — this routes it to apply_merge / dismiss_merge by "
            "the pair id. One tool resolves every kind of question."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "resolve_with": {"type": "string", "description": "The item's resolve_with flour id."},
                "id": {"type": "string", "description": "The item's id (the queued ambiguity id)."},
                "answer": {"type": "string", "description": "The user's chosen answer."},
            },
            "required": ["resolve_with", "id", "answer"],
        },
    ),
]


# ── Handlers ─────────────────────────────────────────────────────────────

async def list_open_questions(args: dict) -> object:
    res = await _run(_LIST_DOUGH, {"max_per_domain": args.get("max_per_domain") or 50})
    if res.get("error"):
        return res
    if res.get("status") != "done":
        return {"error": "could not read open questions", "status": res.get("status"),
                "detail": res.get("error")}
    out = res.get("output") or {}
    # build_dataset-style return: the flour returns {result: OpenQuestionsView}
    return out.get("result", out)


# Answer values that mean "yes, these are the same person" for a merge proposal
# (the candidate_option value the aggregator emits is "merge"; accept the obvious
# synonyms so a label/value slip never strands a merge).
_MERGE_AFFIRMATIVE = frozenset({"merge", "yes", "same", "same person", "same_person"})


async def answer_question(args: dict) -> object:
    """Apply the user's answer to one open question — uniformly across kinds.

    Two routes, both keyed off the item's ``resolve_with``:
    - ``…answer_question`` (an ambiguity: relationship / category / value) →
      bake it with ``{ambiguity_id, answer}``; ``answer`` is the chosen option's
      VALUE (the canonical token, e.g. ``external``).
    - ``…apply_merge`` (a merge proposal) → ``id`` IS the ``pair_id``; route on
      the answer: an affirmative folds the pair (``apply_merge``), anything else
      keeps them separate (``dismiss_merge``). The caller never has to special-
      case merges — one tool resolves every question the queue surfaces."""
    resolve_with = (args.get("resolve_with") or "").strip()
    qid = (args.get("id") or "").strip()
    answer = args.get("answer")
    if not resolve_with or not qid or answer is None or str(answer).strip() == "":
        return {"error": "resolve_with, id, and answer are all required"}

    if resolve_with.endswith(".apply_merge") or resolve_with.endswith(".dismiss_merge"):
        # Merge proposal: pick apply vs dismiss off the answer; bake by pair_id.
        base = resolve_with.rsplit(".", 1)[0]
        affirmative = str(answer).strip().lower() in _MERGE_AFFIRMATIVE
        flour = f"{base}.apply_merge" if affirmative else f"{base}.dismiss_merge"
        res = await _run(flour, {"pair_id": qid})
    elif resolve_with.endswith(".answer_question"):
        res = await _run(resolve_with, {"ambiguity_id": qid, "answer": str(answer)})
    else:
        return {"error": (
            f"don't know how to resolve {resolve_with!r} — expected a "
            f"'.answer_question' (ambiguity) or '.apply_merge' (merge proposal) flour"
        )}

    if res.get("error"):
        return res
    return {"bake_id": res.get("donut_id"), "status": res.get("status"),
            "note": f"Answer applied to the workspace, rendered in the {core.brand_name()} UI."}


HANDLERS: dict = {
    "list_open_questions": list_open_questions,
    "answer_question": answer_question,
}
