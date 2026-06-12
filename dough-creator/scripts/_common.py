"""Shared helpers for the dough-creator scripts — stdlib only.

Sibling import: every script runs as ``python <plugin>/scripts/<name>.py``,
so the scripts dir is ``sys.path[0]`` and ``import _common`` resolves without
any package install. Kept stdlib-only so the standalone-runnable property
holds. Scope is deliberately narrow — the genuinely duplicated pieces:

  * ``utf8_io()``  — make stdout/stderr UTF-8 (console cp949 would otherwise
    crash on UTF-8 error bodies / non-ascii paths).
  * ``BASE_URL``   — the Toast backend API root (``PEEL_BASE_URL`` override).
  * ``call()``     — one HTTP round-trip → ``(status, json-or-text)``.
  * ``report()``   — emit the ``{status, body}`` line, return the exit code.
  * ``PLUGIN_ROOT``— the plugin dir, for resolving vendored trees.

NOT shared here on purpose: the per-script sys.path insertion of vendored
trees (each script owns its own load order) and the ruamel YAML config
(dough_publish tunes flow/width; others don't need YAML at all).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("PEEL_BASE_URL", "http://127.0.0.1:18587/api/v1")


def utf8_io() -> None:
    """Force UTF-8 stdout/stderr — error bodies and paths may carry UTF-8."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict | str]:
    """One HTTP round-trip to the backend. Returns (status, parsed-json-or-text).

    status 0 means the backend was unreachable (body is an ``{"error": ...}``).
    """
    req = urllib.request.Request(
        BASE_URL + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(text)
        except ValueError:
            return e.code, text
    except (urllib.error.URLError, OSError) as e:
        return 0, {"error": f"backend unreachable: {e}"}
    try:
        return 200, json.loads(text)
    except ValueError:
        return 200, text


def report(status: int, data) -> int:
    """Print the ``{status, body}`` line; return 0 on 2xx, else 1."""
    print(json.dumps({"status": status, "body": data}, ensure_ascii=False))
    return 0 if 200 <= status < 300 else 1
