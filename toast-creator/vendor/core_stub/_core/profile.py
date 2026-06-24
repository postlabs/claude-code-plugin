"""Profile path resolution — standalone stub of the real ``_core.profile``.

Same surface as the real module (``set_root``, ``profile_dir``,
``credentials_dir``, ``tokens_path``, ``atomic_write_json``), with ONE
behavioral difference: in the real module ``profile_dir()`` raises
``RuntimeError`` until the kit host injects the active profile dir via
``set_root()``. Standalone there is no host, so ``profile_dir()`` falls
back to the ``TOAST_STORE_DIR`` env var (default ``./.toast_store``),
resolved against cwd and auto-created.

``set_root()`` still works and takes precedence when called — so a
harness that wants an explicit store dir can inject one exactly like
the real host does.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_root: Path | None = None


def set_root(path: Path) -> None:
    """Bind the active profile/store dir. Idempotent, host-compatible."""
    global _root
    _root = Path(path)


def profile_dir() -> Path:
    """Return the active store dir.

    Standalone fallback: ``$TOAST_STORE_DIR`` or ``./.toast_store``,
    resolved and created on first access (the real module never raises
    here once the host has booted; we mirror that by never raising).
    """
    if _root is not None:
        return _root
    root = Path(os.environ.get("TOAST_STORE_DIR", "./.toast_store")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def credentials_dir(kit_id: str) -> Path:
    """Return ``{store}/credentials/{kit_id}/``.

    Like the real helper, does **not** create the directory — callers
    that intend to write ``.mkdir(parents=True, exist_ok=True)`` first.
    """
    return profile_dir() / "credentials" / kit_id


def tokens_path(kit_id: str) -> Path:
    return credentials_dir(kit_id) / "tokens.json"


def atomic_write_json(path: Path, data: Any) -> None:
    """Write ``data`` as JSON via tmp-file + rename (same as real)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    os.replace(tmp, path)


__all__ = [
    "set_root",
    "profile_dir",
    "credentials_dir",
    "tokens_path",
    "atomic_write_json",
]
