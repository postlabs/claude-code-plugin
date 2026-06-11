"""Preflight for dough-creator: is the Toast backend up, and where do doughs live?

Stdlib only — runs on any Python 3. Prints a single JSON object:

    {
      "backend_up": true,
      "base_url": "http://127.0.0.1:18587/api/v1",
      "profiles": ["local", "5ca3000af7e4"],
      "active_profile_ambiguous": true,
      "doughs_dirs": {"local": "...\\profiles\\local\\doughs", ...},
      "user_doughs_dirs": {"local": "...\\profiles\\local\\doughs\\user", ...}
    }

GOTCHA (verified 2026-06-11): the backend's ACTIVE profile is process-internal
and NOT exposed by any API. When the user is logged in, the active profile is a
JWT-derived key (e.g. 5ca3000af7e4), NOT "local" — and the kit install API
copies into the ACTIVE profile while sys.path may be registered on another.
When more than one profile exists, `active_profile_ambiguous` is true: write
user doughs into EVERY listed user_doughs_dir, and after a kit install VERIFY
the kit actually binds (kit_lifecycle.py install does this automatically).

Resolution order for the profiles root:
  1. TOAST_PROFILES_DIR env var (explicit override)
  2. %APPDATA%/Toast/profiles   (installed app, current brand)
  3. %APPDATA%/Mojo/profiles    (pre-rebrand installs)

Exit code 0 when the backend is reachable, 1 when it is not (the creator
must stop and tell the user to start Toast).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("PEEL_BASE_URL", "http://127.0.0.1:18587/api/v1")
HEALTH_URL = BASE_URL.rsplit("/api/", 1)[0] + "/health"


def backend_up() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def profiles_root() -> str | None:
    override = os.environ.get("TOAST_PROFILES_DIR")
    if override and os.path.isdir(override):
        return override
    appdata = os.environ.get("APPDATA", "")
    for brand in ("Toast", "Mojo"):
        cand = os.path.join(appdata, brand, "profiles")
        if os.path.isdir(cand):
            return cand
    return None


def main() -> int:
    up = backend_up()
    root = profiles_root()
    profiles = []
    if root:
        profiles = sorted(
            d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d, "doughs"))
        )
    doughs = {p: os.path.join(root, p, "doughs") for p in profiles} if root else {}
    print(json.dumps({
        "backend_up": up,
        "base_url": BASE_URL,
        "profiles": profiles,
        "active_profile_ambiguous": len(profiles) > 1,
        "doughs_dirs": doughs,
        "user_doughs_dirs": {p: os.path.join(d, "user") for p, d in doughs.items()},
    }))
    return 0 if up else 1


if __name__ == "__main__":
    sys.exit(main())
