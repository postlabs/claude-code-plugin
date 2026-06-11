"""Token I/O primitives — standalone stub of the real ``_core.tokens``.

Behaviorally identical to the real module (file-backed ``tokens.json``
under the store dir's ``credentials/{kit_id}/``), just routed through
the stub ``_core.profile`` so it lands under ``$TOAST_STORE_DIR``
instead of a Toast profile. ``read_tokens`` returns ``None`` when the
file is missing/unparseable — same contract kit code was written
against (call sites raise ``PermissionError`` on missing auth
themselves).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from _core.profile import atomic_write_json, tokens_path

logger = logging.getLogger(__name__)


def read_tokens(kit_id: str) -> dict[str, Any] | None:
    """Read the kit's ``tokens.json``; None if missing or unparseable."""
    path = tokens_path(kit_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[_core.tokens] read failed kit=%s err=%s", kit_id, exc)
        return None


def write_tokens(kit_id: str, data: dict[str, Any]) -> None:
    atomic_write_json(tokens_path(kit_id), data)


def delete_tokens(kit_id: str) -> None:
    path = tokens_path(kit_id)
    try:
        if path.exists():
            path.unlink()
    except Exception as exc:
        logger.warning("[_core.tokens] delete failed kit=%s err=%s", kit_id, exc)


__all__ = ["read_tokens", "write_tokens", "delete_tokens"]
