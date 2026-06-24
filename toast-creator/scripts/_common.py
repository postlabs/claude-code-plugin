"""Shared helpers for the toast-creator scripts — stdlib only.

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
  * ``profiles_root()`` / ``list_profiles()`` — locate the Toast profiles tree
    and the profiles that hold a ``doughs/`` dir (diagnostics).
  * ``resolve_active_profile()`` — authoritatively identify the backend's
    ACTIVE profile by correlating the live dough registry against disk. Shared
    because both ``toast_env`` (report it) and ``kit_lifecycle`` (verify a kit
    landed in it) need the same answer the backend would give.

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
            status = resp.status
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
        return status, json.loads(text)
    except ValueError:
        return status, text


def report(status: int, data) -> int:
    """Print the ``{status, body}`` line; return 0 on 2xx, else 1."""
    print(json.dumps({"status": status, "body": data}, ensure_ascii=False))
    return 0 if 200 <= status < 300 else 1


# --- Active-profile resolution -------------------------------------------
#
# The backend resolves the ACTIVE profile server-side from the logged-in
# session (a JWT-derived key like ``5ca3000af7e4``, bridged into the running
# process at login — see POST /profile/migrate). Verified 2026-06-24: NO API
# exposes that key directly (/profile, /whoami, /settings/profile, /me all 404
# or omit it). dough_publish.py never needs it precisely because the backend
# applies it for every unauthenticated localhost call.
#
# But the active profile is still knowable WITHOUT guessing: the live
# ``GET /doughs`` registry IS the active profile's on-disk content, dough for
# dough. So the profile whose ``doughs/`` tree covers the live id set is the
# active one — the same profile a publish/install lands in. This correlation is
# authoritative (it reads the backend's own truth), unlike "more than one
# profile dir exists → ambiguous", which is a disk-count guess that fires even
# when the backend knows exactly which profile is live.


def profiles_root() -> str | None:
    """Locate the Toast profiles dir: explicit override → Toast → Mojo → None."""
    override = os.environ.get("TOAST_PROFILES_DIR")
    if override and os.path.isdir(override):
        return override
    appdata = os.environ.get("APPDATA", "")
    for brand in ("Toast", "Mojo"):
        cand = os.path.join(appdata, brand, "profiles")
        if os.path.isdir(cand):
            return cand
    return None


def list_profiles(root: str | None) -> list[str]:
    """Profiles under *root* that carry a ``doughs/`` dir (sorted)."""
    if not root:
        return []
    return sorted(
        d for d in os.listdir(root)
        if os.path.isdir(os.path.join(root, d, "doughs"))
    )


def live_dough_ids() -> list[str] | None:
    """The active profile's live dough ids per ``GET /doughs`` (None if down)."""
    status, data = call("GET", "/doughs")
    if status != 200:
        return None
    items = data.get("doughs", []) if isinstance(data, dict) else (
        data if isinstance(data, list) else [])
    return [d["id"] for d in items
            if isinstance(d, dict) and isinstance(d.get("id"), str)]


def resolve_active_profile(
    root: str | None = None,
    profiles: list[str] | None = None,
    ids: list[str] | None = None,
) -> tuple[str | None, dict]:
    """Identify the backend's ACTIVE profile by registry↔disk correlation.

    Returns ``(active_profile | None, evidence)``. ``active_profile`` is the
    profile whose on-disk ``doughs/`` tree uniquely best-covers the live
    registry (an id ``a.b.c`` maps to ``doughs/a/b/c``). It is None ONLY when
    the correlation genuinely cannot decide: backend unreachable, no profiles
    on disk, nothing matches, or a tie. ``evidence`` carries the method,
    per-profile coverage, and the winning match ratio for diagnostics.
    """
    if root is None:
        root = profiles_root()
    if not root:
        return None, {"method": "registry_disk_correlation", "reason": "no_profiles_root"}
    if profiles is None:
        profiles = list_profiles(root)
    if ids is None:
        ids = live_dough_ids()
    if ids is None:
        return None, {"method": "registry_disk_correlation",
                      "reason": "backend_unreachable"}
    if not ids:
        return None, {"method": "registry_disk_correlation", "reason": "empty_registry"}

    coverage = {}
    for p in profiles:
        base = os.path.join(root, p, "doughs")
        coverage[p] = sum(
            1 for i in ids if os.path.isdir(os.path.join(base, *i.split(".")))
        )
    evidence = {"method": "registry_disk_correlation",
                "live_dough_count": len(ids), "coverage": coverage}
    best = max(coverage.values(), default=0)
    winners = [p for p, c in coverage.items() if c == best]
    if best == 0:
        evidence["reason"] = "no_disk_match"
        return None, evidence
    if len(winners) != 1:
        evidence["reason"] = "ambiguous_tie"
        evidence["candidates"] = winners
        return None, evidence
    evidence["match_ratio"] = round(best / len(ids), 4)
    return winners[0], evidence
